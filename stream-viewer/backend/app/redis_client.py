import os
import json
import asyncio
import redis.asyncio as redis
from typing import Dict, List, Optional, Callable, Any

class RedisStreamClient:
    """Async Redis client for accessing AI stream data."""
    
    # Stream key mapping
    STREAM_KEYS = {
        "prompts": "trading:ai:prompts",
        "analysis": "trading:ai:analysis",
        "plans": "trading:ai:plans",
        "executions": "trading:ai:executions"
    }
    
    def __init__(self):
        """Initialize Redis client with environment variables."""
        self.redis_url = self._get_redis_url()
        self.connection_pool = None
        self.client = None
        
    def _get_redis_url(self) -> str:
        """Construct Redis URL from environment variables."""
        host = os.getenv("REDIS_HOST", "localhost")
        port = os.getenv("REDIS_PORT", "6379")
        db = os.getenv("REDIS_DB", "0")
        password = os.getenv("REDIS_PASSWORD", "")
        
        # Construct URL with password if provided
        if password:
            return f"redis://:{password}@{host}:{port}/{db}"
        else:
            return f"redis://{host}:{port}/{db}"
    
    async def connect(self):
        """Establish connection to Redis."""
        if not self.connection_pool:
            self.connection_pool = redis.ConnectionPool.from_url(self.redis_url)
        
        if not self.client:
            self.client = redis.Redis.from_pool(self.connection_pool)
            
        # Test connection
        try:
            await self.client.ping()
            return True
        except Exception as e:
            print(f"Redis connection error: {str(e)}")
            return False
    
    async def close(self):
        """Close Redis connection."""
        if self.client:
            await self.client.close()
            self.client = None
    
    async def get_stream_entries(self, stream_type: str, count: int = 50) -> List[Dict]:
        """Get the latest entries from a stream.
        
        Args:
            stream_type: Type of stream ('prompts', 'analysis', 'plans', 'executions')
            count: Maximum number of entries to retrieve
            
        Returns:
            List of stream entries as dictionaries
        """
        if not self.client:
            await self.connect()
        
        stream_key = self.STREAM_KEYS.get(stream_type)
        if not stream_key:
            raise ValueError(f"Invalid stream type: {stream_type}")
        
        try:
            # Get the latest entries from the stream
            entries = await self.client.xrevrange(stream_key, count=count)
            
            # Process and convert entries
            results = []
            for entry_id, fields in entries:
                # Convert bytes to strings in fields
                data = {k.decode('utf-8'): v.decode('utf-8') for k, v in fields.items()}
                
                # Parse metadata if present
                if 'metadata' in data:
                    try:
                        data['metadata'] = json.loads(data['metadata'])
                    except:
                        pass  # Keep as string if not valid JSON
                
                # Add entry ID
                data['id'] = entry_id.decode('utf-8')
                results.append(data)
            
            return results
            
        except Exception as e:
            print(f"Error retrieving stream entries: {str(e)}")
            return []
    
    async def listen_to_stream(self, stream_type: str, callback: Callable[[Dict], Any], last_id: str = "$"):
        """Listen for new entries on a stream and call the callback for each new entry.
        
        Args:
            stream_type: Type of stream to listen to
            callback: Function to call with each new entry
            last_id: ID to start listening from ('$' means only new entries)
        """
        if not self.client:
            await self.connect()
            
        stream_key = self.STREAM_KEYS.get(stream_type)
        if not stream_key:
            raise ValueError(f"Invalid stream type: {stream_type}")
            
        try:
            # Create a dictionary mapping the stream name to the last ID
            streams = {stream_key: last_id}
            
            while True:
                # Wait for new messages
                response = await self.client.xread(streams, count=1, block=5000)
                
                if response:
                    # Process new messages
                    for stream_name, messages in response:
                        for message_id, fields in messages:
                            # Update the last ID for the next iteration
                            streams[stream_name] = message_id
                            
                            # Convert bytes to strings
                            data = {k.decode('utf-8'): v.decode('utf-8') for k, v in fields.items()}
                            
                            # Parse metadata if present
                            if 'metadata' in data:
                                try:
                                    data['metadata'] = json.loads(data['metadata'])
                                except:
                                    pass
                                    
                            # Add message ID
                            data['id'] = message_id.decode('utf-8')
                            
                            # Call the callback with the processed message
                            await callback(data)
                
                # Small delay to prevent CPU spinning
                await asyncio.sleep(0.01)
                
        except Exception as e:
            print(f"Error listening to stream: {str(e)}")
            # Re-raise to allow proper handling
            raise