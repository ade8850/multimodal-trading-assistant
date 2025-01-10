# aitrading/agents/models/base.py

import uuid

def generate_uuid_short(length: int = 8) -> str:
    """Generate a short UUID of specified length."""
    return str(uuid.uuid4())[:length]