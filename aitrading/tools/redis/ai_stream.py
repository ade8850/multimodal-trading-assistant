import json
import logfire
import os
from typing import Optional, Dict, Any, Literal
from datetime import datetime, UTC
from pydantic import BaseModel, Field


ContentType = Literal["prompt", "analysis", "plan", "execution"]


class AIContent(BaseModel):
    """Base model for AI content stored in Redis streams."""
    
    content_type: ContentType
    symbol: str
    content: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    session_id: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    def to_stream_data(self) -> Dict[str, str]:
        """Convert to a format suitable for Redis stream storage."""
        data = self.model_dump(exclude={"timestamp"})
        # Convert complex types to JSON strings
        data["metadata"] = json.dumps(data["metadata"])
        # Add timestamp as ISO string
        data["timestamp"] = self.timestamp.isoformat()
        
        return {k: str(v) for k, v in data.items() if v is not None}


class AIStreamManager:
    """Manages AI-related content in Redis streams."""
    
    # Stream names for different content types
    STREAMS = {
        "prompt": "ai:prompts",
        "analysis": "ai:analysis",
        "plan": "ai:plans",
        "execution": "ai:executions"
    }
    
    def __init__(self, redis_provider, max_stream_length: Optional[int] = None):
        """Initialize AI stream manager.
        
        Args:
            redis_provider: Redis connection provider
            max_stream_length: Override default max stream length
        """
        self.redis = redis_provider
        self.max_stream_length = max_stream_length or int(
            os.environ.get("AI_STREAM_MAX_LENGTH", "1000")
        )
        self.enabled = self.redis.enabled and os.environ.get("AI_STREAMS_ENABLED", "true").lower() == "true"
    
    def save_content(self, content: AIContent) -> Optional[str]:
        """Save AI content to the appropriate Redis stream.
        
        Args:
            content: AI content object to save
            
        Returns:
            Optional[str]: Message ID if successful, None otherwise
        """
        if not self.enabled:
            logfire.info("AI streams not enabled, content not saved",
                         content_type=content.content_type, 
                         symbol=content.symbol)
            return None
        
        try:
            # Get the appropriate stream name
            stream_name = self.STREAMS.get(content.content_type)
            if not stream_name:
                logfire.error("Unknown content type",
                              content_type=content.content_type)
                return None
            
            # Convert content to stream data format
            stream_data = content.to_stream_data()
            
            # Add to Redis stream
            message_id = self.redis.add_to_stream(
                stream_name=stream_name,
                data=stream_data,
                max_len=self.max_stream_length
            )
            
            if message_id:
                logfire.info("Saved AI content to stream",
                             content_type=content.content_type,
                             symbol=content.symbol,
                             stream=stream_name,
                             message_id=message_id)
            
            return message_id
            
        except Exception as e:
            logfire.error("Failed to save AI content to stream",
                          content_type=content.content_type,
                          symbol=content.symbol,
                          error=str(e))
            return None
    
    def save_prompt(self, symbol: str, prompt: str, session_id: Optional[str] = None, 
                    metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Save a rendered prompt to Redis stream.
        
        Args:
            symbol: Trading symbol the prompt is for
            prompt: The rendered prompt content
            session_id: Optional session identifier
            metadata: Additional metadata
            
        Returns:
            Optional[str]: Message ID if successful, None otherwise
        """
        content = AIContent(
            content_type="prompt",
            symbol=symbol,
            content=prompt,
            session_id=session_id,
            metadata=metadata or {}
        )
        return self.save_content(content)
    
    def save_analysis(self, symbol: str, analysis: str, session_id: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Save market analysis to Redis stream.
        
        Args:
            symbol: Trading symbol the analysis is for
            analysis: The analysis content
            session_id: Optional session identifier
            metadata: Additional metadata
            
        Returns:
            Optional[str]: Message ID if successful, None otherwise
        """
        content = AIContent(
            content_type="analysis",
            symbol=symbol,
            content=analysis,
            session_id=session_id,
            metadata=metadata or {}
        )
        return self.save_content(content)
    
    def save_plan(self, symbol: str, plan: str, session_id: Optional[str] = None,
                  metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Save a trading plan to Redis stream.
        
        Args:
            symbol: Trading symbol the plan is for
            plan: The plan content
            session_id: Optional session identifier
            metadata: Additional metadata
            
        Returns:
            Optional[str]: Message ID if successful, None otherwise
        """
        content = AIContent(
            content_type="plan",
            symbol=symbol,
            content=plan,
            session_id=session_id,
            metadata=metadata or {}
        )
        return self.save_content(content)

    def save_execution(self, symbol: str, execution: str, session_id: Optional[str] = None,
                       metadata: Optional[Dict[str, Any]] = None) -> Optional[str]:
        """Save execution details to Redis stream.
        
        Args:
            symbol: Trading symbol the execution is for
            execution: The execution content
            session_id: Optional session identifier
            metadata: Additional metadata
            
        Returns:
            Optional[str]: Message ID if successful, None otherwise
        """
        content = AIContent(
            content_type="execution",
            symbol=symbol,
            content=execution,
            session_id=session_id,
            metadata=metadata or {}
        )
        return self.save_content(content)