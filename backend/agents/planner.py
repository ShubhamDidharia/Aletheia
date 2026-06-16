import os
from google import genai
from pydantic import BaseModel, TypeAdapter
from typing import List
from schemas.responses import TaskList
import json

async def plan(query: str) -> List[str]:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        print("Warning: GEMINI_API_KEY is not set.")
        # Fallback tasks if no API key
        return [f"Search for {query}"]

    client = genai.Client(api_key=api_key)
    
    prompt = f"""You are an expert research planner. Break down the user's research query into 3 to 4 concrete, independently-searchable sub-tasks. 
Make each sub-task a specific search query that would yield good results.

User Query: {query}
"""

    try:
        response = await client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
            config={
                'response_mime_type': 'application/json',
                'response_schema': TaskList,
            },
        )
        # Parse the JSON response back into our TaskList model
        task_list = TaskList.model_validate_json(response.text)
        return task_list.tasks
    except Exception as e:
        print(f"Error calling Gemini API: {e}")
        # Return fallback on error so the mission doesn't crash completely
        return [f"Search for {query}"]
