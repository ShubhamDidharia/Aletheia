"""
LangGraph state machine for a research mission.

Architecture note — why the gates are their own nodes:
    LangGraph re-executes a node from the top when it resumes from interrupt().
    An interrupt inside the research loop therefore re-runs every Tavily search
    in that node and re-emits every SOURCE_FOUND event, once per user decision.
    So: research_node handles exactly ONE sub-task and never interrupts, and
    gate_node does nothing except interrupt() and apply the decision — making
    re-execution free.
"""
import logging
from typing import TypedDict, List, Dict, Any, Optional

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver
from langgraph.types import Command, interrupt

from schemas.responses import SearchResult, is_stale_year
from agents.planner import plan
from agents.researcher import research
from agents.analyst import detect_conflict
from services.redis_service import save_checkpoint, publish_event

log = logging.getLogger("aletheia.graph")

MAX_ANALYSIS_ROUNDS = 2

# A source as stored in graph state: the JSON form of SearchResult.
Source = Dict[str, Any]


class GraphState(TypedDict, total=False):
    session_id: str
    query: str
    original_query: str
    task_list: List[str]
    completed_steps: List[str]
    sources: List[Source]
    status: str
    pending_gates: List[Dict[str, Any]]
    decisions: List[Dict[str, str]]
    analysis_rounds: int


async def _checkpoint(state: GraphState) -> None:
    await save_checkpoint(state["session_id"], dict(state))


def _sources_payload(sources: List[Source]) -> List[Source]:
    return [
        {
            "title": s["title"],
            "url": s["url"],
            "snippet": (s.get("snippet") or "")[:400],
            "source_type": s.get("source_type", "web"),
            "published_year": s.get("published_year"),
        }
        for s in sources
    ]


# ──────────────────────────────────────────────────────────────────────────────
# Nodes
# ──────────────────────────────────────────────────────────────────────────────
async def plan_node(state: GraphState) -> GraphState:
    session_id = state["session_id"]
    query = state["query"]

    await publish_event(session_id, {
        "type": "STATUS_UPDATE",
        "phase": "planning",
        "description": f"Breaking down: {query}",
    })

    result = await plan(query)

    await publish_event(session_id, {
        "type": "LOG",
        "message": f"Created {len(result.tasks)} search tasks: "
                   + "; ".join(result.tasks),
        "icon": "list",
    })

    gates = list(state.get("pending_gates", []))

    # Ambiguity junction 1 — scope. Only asked once per mission.
    already_asked = any(d["gate_id"] == "scope" for d in state.get("decisions", []))
    if result.is_broad and not already_asked:
        gates.append({
            "id": "scope",
            "question": (
                f'"{query}" is broad. Should I narrow the focus to '
                f"{result.narrow_suggestion}, or research it as-is?"
            ),
            "options": [f"Narrow to: {result.narrow_suggestion}", "Keep the broad scope"],
            "actions": ["narrow", "keep_broad"],
            "payload": {"narrow_suggestion": result.narrow_suggestion},
        })

    new_state: GraphState = {
        **state,
        "task_list": result.tasks,
        "completed_steps": [],
        "pending_gates": gates,
        "status": "planned",
    }
    await _checkpoint(new_state)
    return new_state


async def research_node(state: GraphState) -> GraphState:
    """Executes exactly ONE outstanding sub-task, then checkpoints."""
    session_id = state["session_id"]
    completed = list(state.get("completed_steps", []))
    sources = list(state.get("sources", []))

    remaining = [t for t in state.get("task_list", []) if t not in completed]
    if not remaining:
        return {**state, "status": "researched"}

    task = remaining[0]
    index = len(completed) + 1
    total = len(state.get("task_list", []))

    await publish_event(session_id, {
        "type": "STATUS_UPDATE",
        "phase": "researching",
        "description": f"Task {index} of {total}",
    })

    # research() dedupes against these before it publishes SOURCE_FOUND, so the
    # UI never shows the same evidence card twice.
    known_urls = {s["url"] for s in sources}
    new_sources = await research(task, session_id, known_urls)
    sources.extend(s.model_dump(mode="json") for s in new_sources)

    completed.append(task)

    new_state: GraphState = {
        **state,
        "sources": sources,
        "completed_steps": completed,
        "status": "running",
    }
    await _checkpoint(new_state)
    return new_state


async def analyze_node(state: GraphState) -> GraphState:
    """Inspects the gathered evidence and queues any ambiguity gates it finds."""
    session_id = state["session_id"]
    sources: List[Source] = list(state.get("sources", []))
    gates = list(state.get("pending_gates", []))
    decided = {d["gate_id"] for d in state.get("decisions", [])}

    await publish_event(session_id, {
        "type": "STATUS_UPDATE",
        "phase": "analyzing",
        "description": f"Cross-referencing {len(sources)} sources...",
    })

    # Ambiguity junction 2 — recency. Only meaningful when the user has a real
    # choice: some sources are stale AND some are current.
    stale = [s for s in sources if is_stale_year(s.get("published_year"))]
    fresh = [s for s in sources if not is_stale_year(s.get("published_year"))]
    if "recency" not in decided and len(stale) >= 2 and fresh:
        years = sorted({s["published_year"] for s in stale if s.get("published_year")})
        await publish_event(session_id, {
            "type": "LOG",
            "message": f"{len(stale)} of {len(sources)} sources are older than 3 years "
                       f"({', '.join(str(y) for y in years)}).",
            "icon": "compare",
        })
        gates.append({
            "id": "recency",
            "question": (
                f"{len(stale)} of {len(sources)} sources are more than 3 years old "
                f"({', '.join(str(y) for y in years)}). Include them for historical "
                f"context, or stick to recent data?"
            ),
            "options": ["Include historical context", "Stick to recent data"],
            "actions": ["keep", "discard"],
        })

    # Ambiguity junction 3 — genuine factual contradiction between two sources.
    if "conflict" not in decided:
        hydrated = [SearchResult(**s) for s in sources]
        report = await detect_conflict(state.get("original_query", state["query"]), hydrated)
        if report.has_conflict:
            await publish_event(session_id, {
                "type": "LOG",
                "message": f"Contradiction found on {report.topic}.",
                "icon": "compare",
            })
            gates.append({
                "id": "conflict",
                "question": (
                    f"Sources disagree on {report.topic}. "
                    f'One says "{report.claim_a}" while another says "{report.claim_b}". '
                    f"Should I search for a tie-breaking source, or flag both?"
                ),
                "options": ["Search for a tie-breaker", "Flag both and continue"],
                "actions": ["tie_break", "flag_both"],
                "payload": {"topic": report.topic},
            })

    new_state: GraphState = {
        **state,
        "pending_gates": gates,
        "analysis_rounds": state.get("analysis_rounds", 0) + 1,
        "status": "analyzed",
    }
    await _checkpoint(new_state)
    return new_state


async def gate_node(state: GraphState) -> GraphState:
    """
    Handles ONE ambiguity gate. Nothing above the interrupt() call may have a
    side effect — LangGraph re-runs this node from the top on resume.
    """
    gates = list(state.get("pending_gates", []))
    if not gates:
        return state

    gate = gates[0]

    # ---- execution pauses here; everything below runs only after resume ----
    raw_choice = interrupt({
        "gate_id": gate["id"],
        "question": gate["question"],
        "options": gate["options"],
    })

    session_id = state["session_id"]
    action = _resolve_action(gate, raw_choice)
    label = _label_for(gate, action)

    await publish_event(session_id, {
        "type": "LOG",
        "message": f"You chose: {label}",
        "icon": "check",
    })

    new_state: GraphState = {
        **state,
        "pending_gates": gates[1:],
        "decisions": list(state.get("decisions", [])) + [
            {"gate_id": gate["id"], "action": action, "label": label}
        ],
    }

    new_state = await _apply_decision(new_state, gate, action)
    await _checkpoint(new_state)
    return new_state


def _resolve_action(gate: Dict[str, Any], raw_choice: Any) -> str:
    """Map the user's reply back to an action. Accepts the label or the action id."""
    actions: List[str] = gate["actions"]
    choice = str(raw_choice).strip()

    if choice in actions:
        return choice
    for i, option in enumerate(gate["options"]):
        if choice.lower() == option.lower():
            return actions[i]

    log.warning("Unrecognised choice %r for gate %s; defaulting to %r",
                raw_choice, gate["id"], actions[0])
    return actions[0]


def _label_for(gate: Dict[str, Any], action: str) -> str:
    try:
        return gate["options"][gate["actions"].index(action)]
    except (ValueError, IndexError):
        return action


async def _apply_decision(state: GraphState, gate: Dict[str, Any], action: str) -> GraphState:
    """Make the user's choice actually change what the agent does."""
    session_id = state["session_id"]

    if action == "narrow":
        narrowed = f'{state.get("original_query", state["query"])} ({gate["payload"]["narrow_suggestion"]})'
        await publish_event(session_id, {
            "type": "LOG",
            "message": f"Re-planning with narrowed scope: {narrowed}",
            "icon": "list",
        })
        # Clearing task_list routes the graph back through the planner.
        return {**state, "query": narrowed, "task_list": [], "completed_steps": []}

    if action == "discard":
        kept = [s for s in state.get("sources", []) if not is_stale_year(s.get("published_year"))]
        removed = len(state.get("sources", [])) - len(kept)
        await publish_event(session_id, {
            "type": "LOG",
            "message": f"Discarded {removed} outdated source(s).",
            "icon": "check",
        })
        await publish_event(session_id, {
            "type": "SOURCES_SYNC",
            "sources": _sources_payload(kept),
        })
        return {**state, "sources": kept}

    if action == "tie_break":
        topic = gate.get("payload", {}).get("topic", state["query"])
        tie_task = f"authoritative source resolving conflicting reports about {topic}"
        await publish_event(session_id, {
            "type": "LOG",
            "message": f"Searching for a tie-breaker on {topic}.",
            "icon": "search",
        })
        return {**state, "task_list": list(state.get("task_list", [])) + [tie_task]}

    # keep / keep_broad / flag_both need no state change.
    return state


async def finalize_node(state: GraphState) -> GraphState:
    new_state: GraphState = {**state, "status": "completed"}
    await _checkpoint(new_state)
    return new_state


# ──────────────────────────────────────────────────────────────────────────────
# Routing
# ──────────────────────────────────────────────────────────────────────────────
def _has_remaining_tasks(state: GraphState) -> bool:
    completed = set(state.get("completed_steps", []))
    return any(t not in completed for t in state.get("task_list", []))


def _next_after_work(state: GraphState) -> str:
    """Where to go once gates are drained: more research, more analysis, or done."""
    if not state.get("task_list"):
        return "plan_node"
    if _has_remaining_tasks(state):
        return "research_node"
    if state.get("analysis_rounds", 0) < MAX_ANALYSIS_ROUNDS:
        return "analyze_node"
    return "finalize_node"


def route_entry(state: GraphState) -> str:
    if not state.get("task_list"):
        return "plan_node"
    if _has_remaining_tasks(state):
        return "research_node"
    return "analyze_node"


def route_after_plan(state: GraphState) -> str:
    return "gate_node" if state.get("pending_gates") else "research_node"


def route_after_research(state: GraphState) -> str:
    if _has_remaining_tasks(state):
        return "research_node"
    return "analyze_node"


def route_after_analyze(state: GraphState) -> str:
    return "gate_node" if state.get("pending_gates") else "finalize_node"


def route_after_gate(state: GraphState) -> str:
    if state.get("pending_gates"):
        return "gate_node"
    return _next_after_work(state)


# ──────────────────────────────────────────────────────────────────────────────
# Graph
# ──────────────────────────────────────────────────────────────────────────────
workflow = StateGraph(GraphState)
workflow.add_node("plan_node", plan_node)
workflow.add_node("research_node", research_node)
workflow.add_node("analyze_node", analyze_node)
workflow.add_node("gate_node", gate_node)
workflow.add_node("finalize_node", finalize_node)

workflow.set_conditional_entry_point(route_entry, {
    "plan_node": "plan_node",
    "research_node": "research_node",
    "analyze_node": "analyze_node",
})
workflow.add_conditional_edges("plan_node", route_after_plan, {
    "gate_node": "gate_node",
    "research_node": "research_node",
})
workflow.add_conditional_edges("research_node", route_after_research, {
    "research_node": "research_node",
    "analyze_node": "analyze_node",
})
workflow.add_conditional_edges("analyze_node", route_after_analyze, {
    "gate_node": "gate_node",
    "finalize_node": "finalize_node",
})
workflow.add_conditional_edges("gate_node", route_after_gate, {
    "gate_node": "gate_node",
    "plan_node": "plan_node",
    "research_node": "research_node",
    "analyze_node": "analyze_node",
    "finalize_node": "finalize_node",
})
workflow.add_edge("finalize_node", END)

checkpointer = MemorySaver()
app = workflow.compile(checkpointer=checkpointer)


def _config(session_id: str) -> Dict[str, Any]:
    # recursion_limit must accommodate: plan + N research + analyze + gates,
    # plus a full re-plan cycle if the user narrows the scope.
    return {"configurable": {"thread_id": session_id}, "recursion_limit": 50}


async def get_pending_interrupt(session_id: str) -> Optional[Dict[str, Any]]:
    """
    Returns the interrupt payload if this thread is paused waiting on the user.

    Used on reconnect so a refreshed browser re-attaches to the live pause
    instead of restarting the mission.
    """
    snapshot = await app.aget_state(_config(session_id))
    if snapshot is None or not snapshot.next:
        return None
    for task in snapshot.tasks:
        for intr in getattr(task, "interrupts", ()) or ():
            value = getattr(intr, "value", None)
            if isinstance(value, dict):
                return value
    return None


async def has_thread(session_id: str) -> bool:
    snapshot = await app.aget_state(_config(session_id))
    return bool(snapshot and (snapshot.next or snapshot.values))


async def run_mission(
    session_id: str,
    query: str,
    checkpoint: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if checkpoint:
        initial_state = dict(checkpoint)
        initial_state["session_id"] = session_id
    else:
        initial_state = {
            "session_id": session_id,
            "query": query,
            "original_query": query,
            "task_list": [],
            "completed_steps": [],
            "sources": [],
            "pending_gates": [],
            "decisions": [],
            "analysis_rounds": 0,
            "status": "started",
        }

    return await app.ainvoke(initial_state, config=_config(session_id))


async def resume_mission(session_id: str, choice: str) -> Dict[str, Any]:
    return await app.ainvoke(Command(resume=choice), config=_config(session_id))
