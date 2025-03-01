import { useEffect, useState } from 'preact/hooks';
import JsonTreeViewer from './JsonTreeViewer';

// Define the types
interface StreamEntry {
  id: string;
  content_type: string;
  symbol: string;
  content: string;
  timestamp: string;
  session_id?: string;
  metadata?: Record<string, any>;
}

interface StreamViewerProps {
  streamType: 'prompts' | 'analysis' | 'plans' | 'executions';
  apiUrl: string;
}

export default function StreamViewer({ streamType, apiUrl }: StreamViewerProps) {
  const [entries, setEntries] = useState<StreamEntry[]>([]);
  const [isConnected, setIsConnected] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeEntry, setActiveEntry] = useState<StreamEntry | null>(null);
  
  // Connect to WebSocket
  useEffect(() => {
    let ws: WebSocket;
    
    const connectWebSocket = () => {
      setError(null);
      
      // Create WebSocket connection
      const wsUrl = `${apiUrl.replace('http', 'ws')}/ws/${streamType}`;
      ws = new WebSocket(wsUrl);
      
      ws.onopen = () => {
        console.log(`Connected to ${streamType} stream`);
        setIsConnected(true);
        setError(null);
      };
      
      ws.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          
          // Add new entry to the state, ensuring uniqueness by ID
          setEntries((prevEntries) => {
            // Check if entry with this ID already exists
            const exists = prevEntries.some(entry => entry.id === data.id);
            if (exists) {
              return prevEntries;
            }
            
            // Add new entry and sort by timestamp (newest first)
            const newEntries = [...prevEntries, data].sort((a, b) => {
              const dateA = new Date(a.timestamp);
              const dateB = new Date(b.timestamp);
              return dateB.getTime() - dateA.getTime();
            }).slice(0, 100); // Keep only the most recent 100 entries
            
            return newEntries;
          });
        } catch (err) {
          console.error('Failed to parse WebSocket message:', err);
        }
      };
      
      ws.onclose = (event) => {
        setIsConnected(false);
        if (event.code !== 1000) {
          setError(`Connection closed unexpectedly. Code: ${event.code}`);
          // Try to reconnect after a delay
          setTimeout(connectWebSocket, 3000);
        }
      };
      
      ws.onerror = () => {
        setError('WebSocket connection error');
        setIsConnected(false);
      };
    };
    
    // Initialize WebSocket connection
    connectWebSocket();
    
    // Cleanup on unmount
    return () => {
      if (ws) {
        ws.close(1000, 'Component unmounted');
      }
    };
  }, [streamType, apiUrl]);
  
  // Format timestamp for display
  const formatTimestamp = (timestamp: string) => {
    try {
      const date = new Date(timestamp);
      return date.toLocaleTimeString() + ' ' + date.toLocaleDateString();
    } catch (e) {
      return timestamp;
    }
  };
  
  // Handle click on an entry
  const handleEntryClick = (entry: StreamEntry) => {
    setActiveEntry(entry === activeEntry ? null : entry);
  };
  
  return (
    <div className="stream-viewer h-full flex flex-col">
      <div className="connection-status py-2 px-4 border-b">
        {isConnected ? (
          <span className="text-green-600 flex items-center">
            <span className="h-2 w-2 bg-green-600 rounded-full mr-2"></span>
            Connected to {streamType} stream
          </span>
        ) : (
          <span className="text-red-600 flex items-center">
            <span className="h-2 w-2 bg-red-600 rounded-full mr-2"></span>
            Disconnected
            {error && <span className="ml-2 text-sm">({error})</span>}
          </span>
        )}
      </div>
      
      <div className="flex flex-1 overflow-hidden">
        {/* Entries list */}
        <div className="entries-list w-1/3 border-r overflow-y-auto">
          {entries.length === 0 ? (
            <div className="p-4 text-gray-500">No entries available</div>
          ) : (
            <ul>
              {entries.map((entry) => (
                <li 
                  key={entry.id}
                  className={`p-4 border-b cursor-pointer hover:bg-gray-50 transition-colors ${
                    activeEntry?.id === entry.id ? 'bg-primary-50 border-l-4 border-l-primary-500' : ''
                  }`}
                  onClick={() => handleEntryClick(entry)}
                >
                  <div className="flex justify-between items-center">
                    <span className="font-semibold text-primary-800">{entry.symbol}</span>
                    <span className="text-xs text-gray-500">{formatTimestamp(entry.timestamp)}</span>
                  </div>
                  <div className="truncate text-sm text-gray-600 mt-1">
                    {entry.content.length > 100 
                      ? entry.content.substring(0, 100) + '...' 
                      : entry.content}
                  </div>
                  {entry.session_id && (
                    <div className="text-xs text-gray-500 mt-1">
                      Session: {entry.session_id}
                    </div>
                  )}
                </li>
              ))}
            </ul>
          )}
        </div>
        
        {/* Entry content */}
        <div className="entry-content flex-1 overflow-y-auto p-4 bg-gray-50">
          {activeEntry ? (
            <div>
              <div className="mb-4 pb-4 border-b">
                <div className="flex justify-between">
                  <h3 className="text-xl font-bold text-primary-800">{activeEntry.symbol}</h3>
                  <span className="text-sm text-gray-500">{formatTimestamp(activeEntry.timestamp)}</span>
                </div>
                <div className="flex justify-between items-center">
                  <div>
                    {activeEntry.session_id && (
                      <div className="text-sm text-gray-600 mt-1">
                        Session ID: {activeEntry.session_id}
                      </div>
                    )}
                  </div>
                  <div>
                    <button
                      onClick={() => {
                        // Create a full text representation of the entry
                        const entryText = `Symbol: ${activeEntry.symbol}
Timestamp: ${activeEntry.timestamp}
${activeEntry.session_id ? `Session ID: ${activeEntry.session_id}` : ''}
${activeEntry.metadata ? `Metadata: ${JSON.stringify(activeEntry.metadata, null, 2)}` : ''}

Content:
${activeEntry.content}`;
                        navigator.clipboard.writeText(entryText);
                        
                        // Show a temporary tooltip or feedback
                        const button = document.activeElement as HTMLButtonElement;
                        const originalText = button.innerText;
                        button.innerText = 'Copied!';
                        setTimeout(() => { button.innerText = originalText; }, 2000);
                      }}
                      className="text-xs bg-gray-100 hover:bg-gray-200 text-gray-800 px-2 py-1 rounded"
                    >
                      Copy All
                    </button>
                  </div>
                </div>
                {activeEntry.metadata && Object.keys(activeEntry.metadata).length > 0 && (
                  <div className="mt-2 text-sm">
                    <h4 className="font-semibold text-gray-700">Metadata:</h4>
                    <pre className="bg-gray-100 p-2 rounded mt-1 overflow-x-auto text-xs">
                      {JSON.stringify(activeEntry.metadata, null, 2)}
                    </pre>
                  </div>
                )}
              </div>
              
              <div className="content relative">
                {(streamType === 'plans' || streamType === 'executions') ? (
                  // Interactive JSON viewer for plans and executions
                  <div className="relative">
                    <button 
                      onClick={() => navigator.clipboard.writeText(activeEntry.content)}
                      className="absolute top-2 right-2 bg-primary-100 hover:bg-primary-200 text-primary-800 px-2 py-1 rounded text-xs z-10"
                    >
                      Copy JSON
                    </button>
                    <div className="bg-white p-4 rounded border overflow-x-auto">
                      {(() => {
                        try {
                          // Parse JSON for interactive viewer
                          const jsonObj = JSON.parse(activeEntry.content);
                          return (
                            <JsonTreeViewer data={jsonObj} />
                          );
                        } catch (e) {
                          // Fall back to raw content if not valid JSON
                          return (
                            <pre className="whitespace-pre-wrap font-mono text-sm">
                              {activeEntry.content}
                            </pre>
                          );
                        }
                      })()}
                    </div>
                  </div>
                ) : (
                  // Plain text viewer for prompts and analysis
                  <div className="relative">
                    <button 
                      onClick={() => navigator.clipboard.writeText(activeEntry.content)}
                      className="absolute top-2 right-2 bg-primary-100 hover:bg-primary-200 text-primary-800 px-2 py-1 rounded text-xs z-10"
                    >
                      Copy Text
                    </button>
                    <pre className="whitespace-pre-wrap font-mono text-sm bg-white p-4 rounded border overflow-x-auto">
                      {activeEntry.content}
                    </pre>
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="flex items-center justify-center h-full text-gray-500">
              Select an entry to view its content
            </div>
          )}
        </div>
      </div>
    </div>
  );
}