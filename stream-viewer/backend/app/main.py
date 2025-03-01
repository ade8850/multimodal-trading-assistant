import asyncio
import json
from typing import List, Dict, Any
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware

from .redis_client import RedisStreamClient
from .models import StreamType, StreamResponse, HealthResponse

# Initialize FastAPI app
app = FastAPI(
    title="AI Stream Viewer API",
    description="API for accessing and streaming AI content from Redis streams",
    version="1.0.0"
)

# Add CORS middleware to allow cross-origin requests from frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, restrict this to your frontend domain
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Redis client
redis_client = RedisStreamClient()

# Dependency to get Redis client
async def get_redis_client():
    """Get Redis client, connecting if necessary."""
    if not redis_client.client:
        await redis_client.connect()
    return redis_client

@app.on_event("startup")
async def startup_event():
    """Connect to Redis on startup."""
    await redis_client.connect()

@app.on_event("shutdown")
async def shutdown_event():
    """Close Redis connection on shutdown."""
    await redis_client.close()

@app.get("/health", response_model=HealthResponse)
async def health_check(redis: RedisStreamClient = Depends(get_redis_client)):
    """Health check endpoint."""
    is_connected = await redis.connect()
    return HealthResponse(
        status="ok",
        redis_connected=is_connected,
        stream_types=list(redis.STREAM_KEYS.keys())
    )

@app.get("/streams/{stream_type}", response_model=StreamResponse)
async def get_stream_entries(
    stream_type: StreamType,
    count: int = 50,
    redis: RedisStreamClient = Depends(get_redis_client)
):
    """Get the latest entries from a specific stream."""
    try:
        # Get entries and ensure they are sorted by timestamp (newest first)
        entries = await redis.get_stream_entries(stream_type, count)
        
        # Sort by timestamp descending (newest first)
        if entries:
            entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
        return StreamResponse(
            stream_type=stream_type,
            entries=entries
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error retrieving stream entries: {str(e)}")

@app.websocket("/ws/{stream_type}")
async def websocket_endpoint(websocket: WebSocket, stream_type: StreamType):
    """WebSocket endpoint for streaming real-time updates."""
    await websocket.accept()
    
    try:
        # First send the current entries, sorted by timestamp (newest first)
        redis = await get_redis_client()
        entries = await redis.get_stream_entries(stream_type, count=50)
        
        # Sort entries by timestamp (newest first)
        if entries:
            entries.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
            
        for entry in entries:
            await websocket.send_text(json.dumps(entry))
        
        # Define callback to send new entries to the WebSocket client
        async def on_new_entry(entry: Dict[str, Any]):
            await websocket.send_text(json.dumps(entry))
        
        # Start listening for new entries
        # Use "0" as the last ID to get all entries 
        listening_task = asyncio.create_task(
            redis.listen_to_stream(stream_type, on_new_entry, last_id="0")
        )
        
        # Keep the connection open until the client disconnects
        try:
            while True:
                # Periodically check if the client is still connected
                await websocket.receive_text()
        except WebSocketDisconnect:
            # Cancel the listening task when the client disconnects
            listening_task.cancel()
            
    except Exception as e:
        print(f"WebSocket error: {str(e)}")
        # Close the WebSocket if not already closed
        if not websocket.client_state.DISCONNECTED:
            await websocket.close(code=1011, reason=f"Server error: {str(e)}")

# If running directly with uvicorn
if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)