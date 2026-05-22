from typing import Any, Dict, Optional
from pydantic import BaseModel

class WSMessage(BaseModel):
    event: str          # e.g., 'progress', 'token', 'error', 'complete'
    task_id: str
    payload: Dict[str, Any]

class WSProgressPayload(BaseModel):
    status: str         # e.g., 'extracting', 'embedding', 'generating', 'done'
    percentage: int
    message: str
    details: Optional[str] = None

class WSTokenPayload(BaseModel):
    token: str
    is_final: bool = False
    index: int
