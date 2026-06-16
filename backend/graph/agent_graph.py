from typing import TypedDict, List, Callable, Awaitable, Dict, Any
from langgraph.graph import StateGraph, END
from schemas.responses import SearchResult
from agents.planner import plan
from agents.researcher import research

class GraphState(TypedDict):
    query: str
    task_list: List[str]
    current_task_index: int
    sources: List[SearchResult]
    status: str
    emit: Callable[[Dict[str, Any]], Awaitable[None]]

async def plan_node(state: GraphState) -> GraphState:
    emit = state["emit"]
    await emit({
        "type": "LOG",
        "message": "Breaking down the research goal...",
        "icon": "list"
    })
    
    tasks = await plan(state["query"])
    
    await emit({
        "type": "LOG",
        "message": f"Created {len(tasks)} search tasks.",
        "icon": "check"
    })
    
    return {
        "task_list": tasks,
        "status": "planned"
    }

async def research_node(state: GraphState) -> GraphState:
    emit = state["emit"]
    tasks = state.get("task_list", [])
    all_sources = state.get("sources", [])
    
    for task in tasks:
        new_sources = await research(task, emit)
        all_sources.extend(new_sources)
        
    return {
        "sources": all_sources,
        "status": "completed"
    }

# Build the graph
workflow = StateGraph(GraphState)
workflow.add_node("plan_node", plan_node)
workflow.add_node("research_node", research_node)

workflow.set_entry_point("plan_node")
workflow.add_edge("plan_node", "research_node")
workflow.add_edge("research_node", END)

# Compile graph
app = workflow.compile()

async def run_mission(query: str, emit: Callable[[Dict[str, Any]], Awaitable[None]]) -> GraphState:
    initial_state = {
        "query": query,
        "task_list": [],
        "current_task_index": 0,
        "sources": [],
        "status": "started",
        "emit": emit
    }
    
    # LangGraph returns a dict of the final state
    final_state = await app.ainvoke(initial_state)
    return final_state
