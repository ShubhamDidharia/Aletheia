from typing import Callable, Awaitable, List, Dict, Any
from schemas.responses import SearchResult
from services.tavily import search

async def research(task: str, emit: Callable[[Dict[str, Any]], Awaitable[None]]) -> List[SearchResult]:
    await emit({
        "type": "LOG",
        "message": f"Searching for '{task}'...",
        "icon": "search"
    })
    
    raw_results = await search(task)
    valid_results = []
    
    for item in raw_results:
        try:
            # Pydantic validation drops malformed items automatically
            result = SearchResult(
                title=item.get("title", ""),
                url=item.get("url", ""),
                snippet=item.get("content", "")
            )
            valid_results.append(result)
            
            # Emit the valid source
            await emit({
                "type": "SOURCE_FOUND",
                "title": result.title,
                "url": str(result.url),
                "snippet": result.snippet,
                "source_type": "web"
            })
        except Exception as e:
            # Silently drop malformed results as per requirements
            print(f"Dropped malformed search result: {e}")
            continue
            
    return valid_results
