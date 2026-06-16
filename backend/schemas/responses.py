from pydantic import BaseModel, HttpUrl
from typing import List


class SearchResult(BaseModel):
    title: str
    url: HttpUrl
    snippet: str


class TaskList(BaseModel):
    tasks: List[str]
