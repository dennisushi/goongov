"""
Flask web server for trace analysis and visualization.

Provides endpoints for analyzing traces and serving the frontend interface.
"""

from flask import Flask, render_template, request, jsonify
try:
    from flask_cors import CORS
    HAS_CORS = True
except ImportError:
    HAS_CORS = False
    print("Warning: flask-cors not installed. Install with: pip install flask-cors")
import json
from typing import Dict, Any
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.detect_culprit import find_issue_origin
from backend.trace_to_graph import create_trace_graph, visualize_graph_html
from backend.llm_utils import Agent
from langchain_core.messages import BaseMessage

app = Flask(__name__, 
            template_folder=Path(__file__).parent.parent / 'frontend' / 'templates',
            static_folder=Path(__file__).parent.parent / 'frontend' / 'static')
if HAS_CORS:
    CORS(app)

# Store traces in memory (in production, use a database)
traces_store: Dict[str, Dict[str, Any]] = {}


def serialize_trace_for_json(trace_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Convert LangChain message objects in trace to JSON-serializable format.
    """
    from langchain_core.messages import BaseMessage
    
    serialized = trace_data.copy()
    if 'messages' in serialized:
        serialized_messages = []
        for msg in serialized['messages']:
            if isinstance(msg, BaseMessage):
                # Convert message to dict
                try:
                    msg_dict = msg.dict() if hasattr(msg, 'dict') else msg.model_dump() if hasattr(msg, 'model_dump') else {}
                    # Ensure ID is present
                    if 'id' not in msg_dict or not msg_dict['id']:
                        msg_dict['id'] = getattr(msg, 'id', f'msg_{len(serialized_messages)}')
                    # Ensure type is present and normalized
                    if 'type' not in msg_dict or not msg_dict['type']:
                        msg_type = msg.__class__.__name__
                        # Convert "HumanMessage" -> "human", "AIMessage" -> "ai", etc.
                        msg_dict['type'] = msg_type.replace('Message', '').lower()
                    # Ensure all fields are JSON serializable
                    if 'tool_calls' in msg_dict and msg_dict['tool_calls']:
                        # Convert tool calls to dict if needed
                        tool_calls = []
                        for tc in msg_dict['tool_calls']:
                            if not isinstance(tc, dict):
                                tc = tc.dict() if hasattr(tc, 'dict') else tc.model_dump() if hasattr(tc, 'model_dump') else str(tc)
                            tool_calls.append(tc)
                        msg_dict['tool_calls'] = tool_calls
                    serialized_messages.append(msg_dict)
                except Exception as e:
                    # Fallback: create simple dict
                    msg_id = getattr(msg, 'id', f'msg_{len(serialized_messages)}')
                    msg_type = msg.__class__.__name__.replace('Message', '').lower()
                    serialized_messages.append({
                        'type': msg_type,
                        'content': getattr(msg, 'content', ''),
                        'id': msg_id,
                        'tool_calls': getattr(msg, 'tool_calls', [])
                    })
            else:
                serialized_messages.append(msg)
        serialized['messages'] = serialized_messages
    return serialized


@app.route('/')
def index():
    """Serve the main frontend page."""
    # Pass current trace if available
    current_trace = app.config.get('current_trace')
    trace_id = app.config.get('current_trace_id')
    
    # Serialize trace for JSON
    if current_trace:
        serialized_trace = serialize_trace_for_json(current_trace)
        trace_json = json.dumps(serialized_trace)
    else:
        trace_json = None
    
    return render_template('index.html', 
                         current_trace=trace_json,
                         trace_id=trace_id)


@app.route('/api/analyze', methods=['POST'])
def analyze_trace():
    """
    Analyze a trace to find culprit messages.
    
    Request body:
    {
        "trace": {...},  # Trace data with messages
        "query": "why did they choose this room",
        "model_name": "claude-3-5-sonnet",  # Optional
        "confidence_threshold": 0.5  # Optional
    }
    
    Returns:
    {
        "culprits": [...],  # List of culprit messages with metadata
        "summary": {...},   # Analysis summary
        "graph_html": "...", # HTML string for graph visualization
        "trace_id": "..."   # ID for retrieving trace later
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
            
        trace_data = data.get('trace')
        user_query = data.get('query', '')
        model_name = data.get('model_name', 'claude-3-5-sonnet')
        confidence_threshold = data.get('confidence_threshold', 0.5)
        
        if not trace_data:
            return jsonify({'error': 'trace data is required'}), 400
        if not user_query:
            return jsonify({'error': 'query is required'}), 400
        
        # Ensure trace_data has the expected structure
        if not isinstance(trace_data, dict):
            return jsonify({'error': 'trace data must be a dictionary'}), 400
        if 'messages' not in trace_data:
            return jsonify({'error': 'trace data must contain a "messages" key'}), 400
        
        # Convert serialized messages back to BaseMessage objects if needed
        # The frontend sends messages as dicts, but find_issue_origin expects BaseMessage objects
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
        messages = trace_data.get('messages', [])
        converted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                # Convert dict back to BaseMessage
                # Handle both 'type' and 'lc_kwargs' formats
                msg_type = msg.get('type', '').lower()
                if not msg_type and 'lc_kwargs' in msg:
                    msg_type = msg['lc_kwargs'].get('type', '').lower()
                
                # Extract content and other fields
                content = msg.get('content', msg.get('lc_kwargs', {}).get('content', ''))
                msg_id = msg.get('id', msg.get('lc_id', None))
                
                # Build kwargs for message constructor
                msg_kwargs = {'content': content}
                if msg_id:
                    msg_kwargs['id'] = msg_id
                
                # Handle tool-specific fields
                if 'tool' in msg_type:
                    name = msg.get('name', msg.get('lc_kwargs', {}).get('name', ''))
                    tool_call_id = msg.get('tool_call_id', msg.get('lc_kwargs', {}).get('tool_call_id', ''))
                    if name:
                        msg_kwargs['name'] = name
                    if tool_call_id:
                        msg_kwargs['tool_call_id'] = tool_call_id
                    converted_messages.append(ToolMessage(**msg_kwargs))
                elif 'ai' in msg_type:
                    # Handle tool_calls for AIMessage
                    tool_calls = msg.get('tool_calls', msg.get('lc_kwargs', {}).get('tool_calls', []))
                    if tool_calls:
                        msg_kwargs['tool_calls'] = tool_calls
                    converted_messages.append(AIMessage(**msg_kwargs))
                elif 'human' in msg_type:
                    converted_messages.append(HumanMessage(**msg_kwargs))
                else:
                    # Unknown type, try to keep as dict or create a generic message
                    converted_messages.append(msg)
            elif isinstance(msg, BaseMessage):
                converted_messages.append(msg)
            else:
                converted_messages.append(msg)
        
        trace_data['messages'] = converted_messages
        
        # Create critic agent
        critic_system_prompt = "You are a helpful critic agent that analyzes agent execution traces."
        critic_agent = Agent(model_name, critic_system_prompt, [])
        
        # Find issue origin (this modifies trace_data in place)
        results, summary = find_issue_origin(
            trace_data,
            user_query,
            critic_agent,
            confidence_threshold=confidence_threshold
        )
        
        # Format culprits for response
        culprits = []
        for msg, confidence, explanation in results:
            # Get message ID - try multiple ways
            msg_id = None
            if hasattr(msg, 'id'):
                msg_id = msg.id
            elif isinstance(msg, dict):
                msg_id = msg.get('id') or msg.get('lc_id')
            
            if not msg_id:
                # Try to find the message in trace_data by content
                for idx, trace_msg in enumerate(trace_data.get('messages', [])):
                    if isinstance(trace_msg, BaseMessage):
                        if trace_msg == msg or (hasattr(trace_msg, 'content') and 
                                               hasattr(msg, 'content') and 
                                               trace_msg.content == msg.content):
                            msg_id = getattr(trace_msg, 'id', f'msg_{idx}')
                            break
                if not msg_id:
                    msg_id = f'culprit_{len(culprits)}'
            
            msg_type = msg.__class__.__name__ if hasattr(msg, '__class__') else 'Unknown'
            if isinstance(msg, dict):
                msg_type = msg.get('type', 'Unknown')
            content = ''
            if hasattr(msg, 'content'):
                content = msg.content[:200] if msg.content else ''
            elif isinstance(msg, dict):
                content = str(msg.get('content', ''))[:200]
            
            culprits.append({
                'id': str(msg_id),
                'type': msg_type,
                'content': content,
                'confidence': confidence,
                'explanation': explanation
            })
        
        # Generate graph HTML
        culprit_ids = set(summary.get('culprit_message_ids', []))
        graph_html_path = visualize_graph_html(
            trace_data,
            output_path=None,  # Generate in memory
            culprit_ids=culprit_ids
        )
        
        # Read graph HTML
        try:
            with open(graph_html_path, 'r') as f:
                graph_html = f.read()
        except:
            graph_html = ""
        
        # Store trace for later retrieval
        import uuid
        trace_id = str(uuid.uuid4())
        traces_store[trace_id] = trace_data
        
        return jsonify({
            'culprits': culprits,
            'summary': summary,
            'graph_html': graph_html,
            'trace_id': trace_id
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in /api/analyze: {error_details}")
        # Return error details (but don't expose full traceback in production)
        return jsonify({
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


@app.route('/api/trace/<trace_id>', methods=['GET'])
def get_trace(trace_id: str):
    """Get stored trace data by ID."""
    if trace_id not in traces_store:
        return jsonify({'error': 'Trace not found'}), 404
    
    return jsonify({'trace': traces_store[trace_id]})


@app.route('/api/graph', methods=['POST'])
def generate_graph():
    """
    Generate graph visualization for a trace.
    
    Request body:
    {
        "trace": {...},
        "culprit_ids": [...]  # Optional list of culprit message IDs
    }
    """
    try:
        data = request.json
        trace_data = data.get('trace')
        culprit_ids = set(data.get('culprit_ids', []))
        
        if not trace_data:
            return jsonify({'error': 'trace data is required'}), 400
        
        # Generate graph HTML
        graph_html_path = visualize_graph_html(
            trace_data,
            output_path=None,
            culprit_ids=culprit_ids
        )
        
        # Read graph HTML
        with open(graph_html_path, 'r') as f:
            graph_html = f.read()
        
        return jsonify({'graph_html': graph_html})
        
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(debug=True, port=5000)

