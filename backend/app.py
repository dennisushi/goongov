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

from backend.detect_culprit import find_issue_origin, failure_analysis
from backend.trace_to_graph import create_trace_graph, visualize_graph_html
from backend.llm_utils import Agent, GovAgent
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
        user_query = data.get('query', '')  # Critic query (about the trace)
        original_user_query = data.get('original_user_query', '')  # Original query that generated the trace
        model_name = data.get('model_name', 'claude-3-5-sonnet')
        confidence_threshold = data.get('confidence_threshold', 0.5)
        use_find_issue_origin = data.get('use_find_issue_origin', True)
        use_failure_analysis = data.get('use_failure_analysis', True)
        
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
        from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, SystemMessage
        messages = trace_data.get('messages', [])
        converted_messages = []
        for msg in messages:
            if isinstance(msg, dict):
                # Convert dict back to BaseMessage
                # Handle both 'type' and 'lc_kwargs' formats
                msg_type = msg.get('type', '').lower()
                if not msg_type and 'lc_kwargs' in msg:
                    msg_type = msg['lc_kwargs'].get('type', '').lower()
                
                # Check lc_id format (LangChain serialization)
                if not msg_type and 'lc_id' in msg:
                    lc_id = msg['lc_id']
                    if isinstance(lc_id, list) and len(lc_id) >= 3:
                        msg_type = lc_id[2].lower()
                
                # Extract content and other fields
                content = msg.get('content', msg.get('lc_kwargs', {}).get('content', ''))
                msg_id = msg.get('id', msg.get('lc_id', None))
                
                # Build kwargs for message constructor
                msg_kwargs = {'content': content}
                if msg_id and not isinstance(msg_id, list):
                    msg_kwargs['id'] = msg_id
                
                # Handle different message types
                if 'system' in msg_type:
                    converted_messages.append(SystemMessage(**msg_kwargs))
                elif 'tool' in msg_type:
                    name = msg.get('name', msg.get('lc_kwargs', {}).get('name', ''))
                    tool_call_id = msg.get('tool_call_id', msg.get('lc_kwargs', {}).get('tool_call_id', ''))
                    if name:
                        msg_kwargs['name'] = name
                    if tool_call_id:
                        msg_kwargs['tool_call_id'] = tool_call_id
                    converted_messages.append(ToolMessage(**msg_kwargs))
                elif 'ai' in msg_type or 'assistant' in msg_type:
                    # Handle tool_calls for AIMessage
                    tool_calls = msg.get('tool_calls', msg.get('lc_kwargs', {}).get('tool_calls', []))
                    if tool_calls:
                        msg_kwargs['tool_calls'] = tool_calls
                    converted_messages.append(AIMessage(**msg_kwargs))
                elif 'human' in msg_type or 'user' in msg_type:
                    converted_messages.append(HumanMessage(**msg_kwargs))
                else:
                    # Unknown type, keep as dict - the helper functions will handle it
                    converted_messages.append(msg)
            elif isinstance(msg, BaseMessage):
                converted_messages.append(msg)
            else:
                converted_messages.append(msg)
        
        trace_data['messages'] = converted_messages
        
        # Extract original user query from trace if not provided
        if not original_user_query:
            for msg in converted_messages:
                if isinstance(msg, HumanMessage) or (isinstance(msg, dict) and msg.get('type', '').lower() == 'human'):
                    original_user_query = msg.content if hasattr(msg, 'content') else msg.get('content', '')
                    # Remove system prompt if present (it's usually at the start)
                    if original_user_query and len(original_user_query) > 500:
                        # Likely contains system prompt, try to extract just the user query
                        lines = original_user_query.split('\n')
                        for line in reversed(lines):
                            if line.strip() and not line.strip().startswith('You are'):
                                original_user_query = line.strip()
                                break
                    break
        
        # Create critic agent
        critic_system_prompt = "You are a helpful critic agent that analyzes agent execution traces."
        critic_agent = Agent(model_name, critic_system_prompt, [])
        
        # Run analyses based on toggles
        culprits_origin = []
        summary_origin = {}
        if use_find_issue_origin:
            culprits_origin, summary_origin = find_issue_origin(
                trace_data,
                user_query,
                critic_agent,
                confidence_threshold=confidence_threshold
            )
        
        failures = []
        summary_failure = {}
        if use_failure_analysis:
            if not original_user_query:
                return jsonify({'error': 'original_user_query is required for failure_analysis. It should be the query that generated the trace.'}), 400
            failures, summary_failure = failure_analysis(
                trace_data,
                original_user_query,
                judge_llm=critic_agent
            )
        
        # Combine results from both methods (if both were run)
        # A node can be both a "responsible node" (from find_issue_origin) and a "failure" (from failure_analysis)
        def combine_results(culprits_origin, failures):
            """Combine responsible nodes and failures, allowing nodes to be both."""
            result_dict = {}
            
            # Process responsible nodes from find_issue_origin
            for msg, confidence, explanation in culprits_origin:
                msg_id = getattr(msg, 'id', None) or id(msg)
                if msg_id not in result_dict:
                    result_dict[msg_id] = {
                        'message': msg,
                        'confidence': confidence,
                        'explanations': [],
                        'sources': [],
                        'is_responsible_node': False,
                        'is_failure': False
                    }
                result_dict[msg_id]['explanations'].append(f"[Culprit Detection] {explanation}")
                if 'Culprit Detection' not in result_dict[msg_id]['sources']:
                    result_dict[msg_id]['sources'].append('Culprit Detection')
                result_dict[msg_id]['confidence'] = max(result_dict[msg_id]['confidence'], confidence)
                result_dict[msg_id]['is_responsible_node'] = True  # All from find_issue_origin are responsible nodes
            
            # Process failures from failure_analysis
            for msg, confidence, explanation in failures:
                msg_id = getattr(msg, 'id', None) or id(msg)
                # Check metadata for is_failure flag
                is_failure = False
                if hasattr(msg, '_culprit_metadata'):
                    metadata = msg._culprit_metadata
                    if isinstance(metadata, dict):
                        is_failure = metadata.get('is_failure', False)
                    else:
                        is_failure = getattr(metadata, 'is_failure', False)
                # Also check explanation for failure indicator
                if '[FAILURE DETECTED]' in explanation:
                    is_failure = True
                
                if msg_id not in result_dict:
                    result_dict[msg_id] = {
                        'message': msg,
                        'confidence': confidence,
                        'explanations': [],
                        'sources': [],
                        'is_responsible_node': False,
                        'is_failure': False
                    }
                result_dict[msg_id]['explanations'].append(f"[Error Detection] {explanation}")
                if 'Error Detection' not in result_dict[msg_id]['sources']:
                    result_dict[msg_id]['sources'].append('Error Detection')
                result_dict[msg_id]['confidence'] = max(result_dict[msg_id]['confidence'], confidence)
                result_dict[msg_id]['is_failure'] = is_failure
            
            combined = []
            for msg_id, data in result_dict.items():
                combined_explanation = " | ".join(data['explanations'])
                combined.append((
                    data['message'], 
                    data['confidence'], 
                    combined_explanation, 
                    data['sources'], 
                    data['is_responsible_node'],
                    data['is_failure']
                ))
            
            # Sort: failures first, then responsible nodes, then by confidence
            combined.sort(key=lambda x: (not x[5], not x[4], -x[1]))  # failures first, then responsible nodes, then confidence
            return combined
        
        # Combine results if both methods were used, otherwise use the single result
        if use_find_issue_origin and use_failure_analysis:
            combined_results = combine_results(culprits_origin, failures)
        elif use_find_issue_origin:
            combined_results = [(msg, conf, exp, ['Culprit Detection'], True, False) for msg, conf, exp in culprits_origin]
        elif use_failure_analysis:
            # Extract failure info from failure analysis results
            combined_results = []
            for msg, conf, exp in failures:
                is_failure = '[FAILURE DETECTED]' in exp
                # Check metadata
                if hasattr(msg, '_culprit_metadata'):
                    metadata = msg._culprit_metadata
                    if isinstance(metadata, dict):
                        is_failure = is_failure or metadata.get('is_failure', False)
                combined_results.append((msg, conf, exp, ['Error Detection'], False, is_failure))
            # Sort: failures first
            combined_results.sort(key=lambda x: (not x[5], -x[1]))
        else:
            combined_results = []
        
        # Combine summaries
        summary = {
            'total_messages_checked': max(
                summary_origin.get('total_messages_checked', 0),
                summary_failure.get('total_messages_checked', 0)
            ),
            'culprits_found': len(combined_results),
            'responsible_nodes_from_origin': len(culprits_origin) if use_find_issue_origin else 0,
            'failures_from_analysis': len(failures) if use_failure_analysis else 0,
            'confidence_threshold': confidence_threshold,
            'culprit_message_ids': list(set(
                (summary_origin.get('culprit_message_ids', []) if use_find_issue_origin else []) +
                (summary_failure.get('failure_message_ids', []) if use_failure_analysis else [])
            )),
            'responsible_component': summary_failure.get('responsible_component') if use_failure_analysis else None,
            'decisive_error_step_index': summary_failure.get('decisive_error_step_index') if use_failure_analysis else None
        }
        
        # Format results for response (responsible nodes and failures)
        culprits = []
        for result in combined_results:
            # Handle different formats: (msg, conf, exp, sources, is_responsible, is_failure)
            if len(result) == 6:
                msg, confidence, explanation, sources, is_responsible_from_result, is_failure_from_result = result
            elif len(result) == 5:
                msg, confidence, explanation, sources, is_responsible_from_result = result
                is_failure_from_result = '[FAILURE DETECTED]' in explanation
            elif len(result) == 4:
                msg, confidence, explanation, sources = result
                is_responsible_from_result = False
                is_failure_from_result = '[FAILURE DETECTED]' in explanation
            else:
                msg, confidence, explanation = result
                is_responsible_from_result = False
                is_failure_from_result = '[FAILURE DETECTED]' in explanation
                # Determine source based on which analysis found it
                if use_find_issue_origin and use_failure_analysis:
                    if is_failure_from_result:
                        sources = ['Error Detection']
                    else:
                        sources = ['Culprit Detection']
                elif use_find_issue_origin:
                    sources = ['Culprit Detection']
                elif use_failure_analysis:
                    sources = ['Error Detection']
                else:
                    sources = ['Unknown']
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
            
            source_label = " | ".join(sources) if isinstance(sources, list) else str(sources)
            
            # Check metadata for flags
            is_responsible = is_responsible_from_result
            is_failure = is_failure_from_result
            responsible_component_from_metadata = None
            
            # Check metadata (it's a dict, not an object with attributes)
            if hasattr(msg, '_culprit_metadata'):
                metadata = msg._culprit_metadata
                if isinstance(metadata, dict):
                    is_responsible = is_responsible or metadata.get('is_responsible_node', False)
                    is_failure = is_failure or metadata.get('is_failure', False)
                    responsible_component_from_metadata = metadata.get('responsible_component')
                else:
                    # Fallback for object-style metadata
                    is_responsible = is_responsible or getattr(metadata, 'is_responsible_node', False)
                    is_failure = is_failure or getattr(metadata, 'is_failure', False)
                    responsible_component_from_metadata = getattr(metadata, 'responsible_component', None)
            
            culprit_data = {
                'id': str(msg_id),
                'type': msg_type,
                'content': content,
                'confidence': confidence,
                'explanation': explanation,
                'sources': source_label,
                'is_responsible_node': is_responsible,  # From find_issue_origin
                'is_failure': is_failure,  # From failure_analysis
                'is_root_cause': is_responsible  # Alias for clarity
            }
            
            if responsible_component_from_metadata:
                culprit_data['responsible_component'] = responsible_component_from_metadata
            
            culprits.append(culprit_data)
        
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


@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint to verify server is running."""
    return jsonify({'status': 'ok', 'message': 'Server is running'})


@app.route('/api/generate-trace', methods=['POST'])
def generate_trace():
    """
    Generate an execution trace by running the agent with a user query.
    
    Request body:
    {
        "user_query": "I would like to book the community center for a 30-person event on December 10th.",
        "model_name": "claude-3-5-sonnet"  # Optional, defaults to claude-3-5-sonnet
    }
    
    Returns:
    {
        "trace": {...},  # Trace data with messages
        "trace_id": "..."  # ID for retrieving trace later
    }
    """
    try:
        data = request.json
        if not data:
            return jsonify({'error': 'Request body is required'}), 400
        
        user_query = data.get('user_query', '').strip()
        model_name = data.get('model_name', 'claude-3-5-sonnet')
        
        if not user_query:
            return jsonify({'error': 'user_query is required'}), 400
        
        # Create GovAgent and run the query
        print(f"Generating trace for query: {user_query}")
        gov_agent = GovAgent(model_name)
        result = gov_agent.invoke(user_query)
        
        # Ensure result has the expected structure
        if not isinstance(result, dict):
            return jsonify({'error': 'Agent returned unexpected format'}), 500
        
        if 'messages' not in result:
            return jsonify({'error': 'Agent result missing messages'}), 500
        
        # Serialize trace for storage and response
        serialized_trace = serialize_trace_for_json(result)
        
        # Store trace for later retrieval
        import uuid
        trace_id = str(uuid.uuid4())
        traces_store[trace_id] = result  # Store original with BaseMessage objects
        
        # Store original user query in trace metadata
        if 'metadata' not in serialized_trace:
            serialized_trace['metadata'] = {}
        serialized_trace['metadata']['original_user_query'] = user_query
        
        return jsonify({
            'trace': serialized_trace,
            'trace_id': trace_id,
            'original_user_query': user_query
        })
        
    except Exception as e:
        import traceback
        error_details = traceback.format_exc()
        print(f"Error in /api/generate-trace: {error_details}")
        return jsonify({
            'error': str(e),
            'error_type': type(e).__name__
        }), 500


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

