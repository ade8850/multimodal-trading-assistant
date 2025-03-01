from typing import Dict, List, Optional, Any, Literal
from pydantic import BaseModel, Field
from datetime import datetime

# Define valid stream types
StreamType = Literal["prompts", "analysis", "plans", "executions"]

class StreamEntry(BaseModel):
    """Model representing an entry from a Redis stream."""
    id: str
    content_type: StreamType
    symbol: str
    content: str
    timestamp: str
    session_id: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None

class StreamResponse(BaseModel):
    """Response model for stream data API endpoints."""
    stream_type: StreamType
    entries: List[StreamEntry]
    
class HealthResponse(BaseModel):
    """Response model for health check endpoint."""
    status: str
    redis_connected: bool
    stream_types: List[str]
    timestamp: datetime = Field(default_factory=datetime.now)