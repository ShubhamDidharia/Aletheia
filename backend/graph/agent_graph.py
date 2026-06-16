from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END
from schemas.responses import SearchResult
from agents.planner import plan
from agents.researcher import research
from services.redis_service import save_checkpoint, publish_event

class GraphState(TypedDict):
    session_id: str
    query: str
    task_list: List[str]
    completed_steps: List[str]
    sources: List[SearchResult]
    status: str

async def plan_node(state: GraphState) -> GraphState:
    session_id = state["session_id"]
    await publish_event(session_id, {
        "type": "LOG",
        "message": "Breaking down the research goal...",
        "icon": "list"
    })
    
    tasks = await plan(state["query"])
    
    await publish_event(session_id, {
        "type": "LOG",
        "message": f"Created {len(tasks)} search tasks.",
        "icon": "check"
    })
    
    new_state = {
        **state,
        "task_list": tasks,
        "status": "planned"
    }
    
    # Checkpoint after plan
    await save_checkpoint(session_id, _serialize_state(new_state))
    return new_state

async def research_node(state: GraphState) -> GraphState:
    session_id = state["session_id"]
    tasks = state.get("task_list", [])
    completed = state.get("completed_steps", [])
    all_sources = state.get("sources", [])
    
    # We will do sub-tasks that are not yet completed
    for task in tasks:
        if task in completed:
            continue
            
        new_sources = await research(task, session_id)
        all_sources.extend(new_sources)
        completed.append(task)
        
        # Checkpoint after each task
        new_state = {
            **state,
            "sources": all_sources,
            "completed_steps": completed,
            "status": "running"
        }
        await save_checkpoint(session_id, _serialize_state(new_state))
        
    final_state = {
        **state,
        "sources": all_sources,
        "completed_steps": completed,
        "status": "completed"
    }
    await save_checkpoint(session_id, _serialize_state(final_state))
    return final_state

def _serialize_state(state: GraphState) -> Dict[str, Any]:
    # Convert SearchResult objects to dicts for JSON serialization
    serialized = dict(state)
    serialized["sources"] = [
        s.model_dump() if hasattr(s, 'model_dump') else s 
        for s in state.get("sources", [])
    ]
    return serialized

def _deserialize_state(state_dict: Dict[str, Any]) -> GraphState:
    # Rehydrate SearchResult objects
    deserialized = dict(state_dict)
    if "sources" in deserialized:
        deserialized["sources"] = [
            SearchResult(**s) if isinstance(s, dict) else s 
            for s in deserialized["sources"]
        ]
    return deserialized

# Build the graph
workflow = StateGraph(GraphState)
workflow.add_node("plan_node", plan_node)
workflow.add_node("research_node", research_node)

# Conditional edge logic to skip planner if we have tasks
def should_plan(state: GraphState) -> str:
    if state.get("task_list"):
        return "research_node"
    return "plan_node"

workflow.set_conditional_entry_point(
    should_plan,
    {
        "plan_node": "plan_node",
        "research_node": "research_node"
    }
)
workflow.add_edge("plan_node", "research_node")
workflow.add_edge("research_node", END)

# Compile graph
app = workflow.compile()

async def run_mission(session_id: str, query: str, checkpoint: Optional[Dict[str, Any]] = None) -> GraphState:
    if checkpoint:
        initial_state = _deserialize_state(checkpoint)
    else:
        initial_state = {
            "session_id": session_id,
            "query": query,
            "task_list": [],
            "completed_steps": [],
            "sources": [],
            "status": "started"
        }
    
    # LangGraph returns a dict of the final state
    final_state = await app.ainvoke(initial_state)
    return final_state
