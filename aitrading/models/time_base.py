"""Base model for time-aware entities."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, field_validator
import pytz
import logfire

class TimeBasedModel(BaseModel):
    """Base model for time-aware entities providing standardized time management."""
    
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    @field_validator('created_at')
    def ensure_timezone(cls, v: Optional[datetime]) -> Optional[datetime]:
        """Ensure all datetime fields are UTC."""
        if v is not None and v.tzinfo is None:
            return v.replace(tzinfo=pytz.UTC)
        return v

    @property
    def age_seconds(self) -> float:
        """Get age of entity in seconds."""
        now = datetime.now(pytz.UTC)
        if not self.created_at:
            return 0.0
        return (now - self.created_at).total_seconds()
    
    @property
    def age_minutes(self) -> float:
        """Get age of entity in minutes."""
        return self.age_seconds / 60
    
    @property
    def age_hours(self) -> float:
        """Get age of entity in hours."""
        return self.age_minutes / 60

    @classmethod
    def from_timestamp(cls, timestamp: int, **kwargs) -> "TimeBasedModel":
        """Create instance from Unix timestamp (milliseconds)."""
        try:
            logfire.debug("Converting timestamp", 
                       raw_timestamp=timestamp,
                       kwargs=kwargs)
            
            # Usa datetime.fromtimestamp con timestamp preciso al millisecondo
            seconds = timestamp // 1000  # Parte intera dei secondi
            microseconds = (timestamp % 1000) * 1000  # Converti millisecondi in microsecondi
            dt = datetime.fromtimestamp(seconds, pytz.UTC).replace(microsecond=microseconds)
            
            logfire.debug("Converted timestamp", 
                       original=timestamp,
                       converted_dt=dt.isoformat())
            
            return cls(created_at=dt, **kwargs)
            
        except Exception as e:
            logfire.error("Error converting timestamp",
                       timestamp=timestamp,
                       error=str(e))
            # Fallback to current time
            return cls(created_at=datetime.now(pytz.UTC), **kwargs)

    @classmethod
    def from_iso(cls, iso_string: str, **kwargs) -> "TimeBasedModel":
        """Create instance from ISO format string."""
        dt = datetime.fromisoformat(iso_string.replace('Z', '+00:00'))
        return cls(created_at=dt, **kwargs)