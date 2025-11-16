"""
Trace visualization and graph generation utilities.

This module provides functions to visualize agent execution traces,
display messages, and create graph representations.
"""

from termcolor import colored
from typing import List, Dict, Any, Optional, Set
from langchain_core.messages import BaseMessage

try:
    import networkx as nx
    HAS_NETWORKX = True
except ImportError:
    HAS_NETWORKX = False
    print("Warning: networkx not installed. Install with: pip install networkx")

try:
    from pyvis.network import Network
    HAS_PYVIS = True
except ImportError:
    HAS_PYVIS = False
    print("Warning: pyvis not installed. Install with: pip install pyvis")


def print_message_summary(msg: BaseMessage, highlight_culprit: bool = False):
    """
    Pretty-print a summary of a message object with colored type and content/redirect.
    Handles HumanMessage, AIMessage, ToolMessage.
    
    Args:
        msg: LangChain message object
        highlight_culprit: If True, highlight messages marked as culprits
    """
    msg_type = type(msg).__name__
    content = getattr(msg, 'content', '')
    
    # Check if this is a culprit
    is_culprit = False
    confidence = 0.0
    explanation = ""
    if hasattr(msg, '_culprit_metadata'):
        metadata = msg._culprit_metadata
        is_culprit = metadata.get('is_culprit', False)
        confidence = metadata.get('confidence', 0.0)
        explanation = metadata.get('explanation', '')
    
    # Determine base color
    if msg_type == "HumanMessage":
        tcolor = 'cyan'
        important = content.strip().split("\n")[-1]
    elif msg_type == "AIMessage":
        tcolor = 'green'
        # If tool call(s), show reasoning (if any) + tool call; else, show content
        tool_calls = getattr(msg, 'tool_calls', None)
        if tool_calls and len(tool_calls) > 0:
            tc = tool_calls[0]
            tool_info = f"Tool call: {tc.get('name', '')}({tc.get('args', {})})"
            # Include reasoning content if present
            if content and content.strip():
                important = f"{content.strip()}\n  → {tool_info}"
            else:
                important = tool_info
        else:
            important = content.strip() if content else "(empty)"
    elif msg_type == "ToolMessage":
        tcolor = 'magenta'
        toolname = getattr(msg, "name", "")
        if content.startswith("Observation"):
            important = content.strip()
        else:
            important = f"{toolname}: {content.strip()}"
    else:
        tcolor = 'yellow'
        important = str(content)
    
    # Highlight culprit
    if highlight_culprit and is_culprit:
        # Use red background or bold for culprits
        print(colored(f"[{msg_type:12s}] ", 'red', attrs=["bold", "reverse"]), end='')
        print(colored(f"⚠️ CULPRIT (confidence: {confidence:.2f})", 'red', attrs=["bold"]))
        print(colored(f"   Explanation: {explanation}", 'yellow'))
        print(colored(f"   ", 'white'), end='')
    else:
        print(colored(f"[{msg_type:12s}] ", tcolor, attrs=["bold"]), end='')
    
    print(important)


def create_trace_graph(
    trace_data: Dict[str, Any],
    culprit_ids: Optional[Set[str]] = None
) -> 'nx.DiGraph':
    """
    Create a NetworkX directed graph from trace messages.
    
    Args:
        trace_data: Dict with 'messages' key containing LangChain message objects
        culprit_ids: Set of message IDs that are culprits (for highlighting)
    
    Returns:
        NetworkX DiGraph with nodes for messages and edges for flow
    """
    if not HAS_NETWORKX:
        raise ImportError("networkx is required. Install with: pip install networkx")
    
    G = nx.DiGraph()
    
    if not isinstance(trace_data, dict) or 'messages' not in trace_data:
        return G
    
    messages = trace_data['messages']
    if culprit_ids is None:
        culprit_ids = set()
        # Extract culprit IDs from messages
        for msg in messages:
            if hasattr(msg, '_culprit_metadata') and msg._culprit_metadata.get('is_culprit'):
                msg_id = getattr(msg, 'id', None)
                if msg_id:
                    culprit_ids.add(msg_id)
    
    # Add nodes
    for idx, msg in enumerate(messages):
        if not isinstance(msg, BaseMessage):
            continue
        
        msg_id = getattr(msg, 'id', f'msg_{idx}')
        msg_type = msg.__class__.__name__.replace("Message", "").lower()
        content = getattr(msg, 'content', '') or ''
        
        # Truncate content for display
        if len(content) > 100:
            display_content = content[:100] + "..."
        else:
            display_content = content
        
        # Handle tool calls
        tool_calls = getattr(msg, 'tool_calls', [])
        if tool_calls:
            tool_info = []
            for tc in tool_calls[:2]:  # Limit to 2 tool calls
                tool_name = tc.get('name', 'unknown')
                tool_args = tc.get('args', {})
                tool_info.append(f"{tool_name}({str(tool_args)[:50]})")
            if tool_info:
                tool_str = f"Tool calls: {', '.join(tool_info)}"
                # Include reasoning content if present
                if content and content.strip():
                    # Truncate reasoning if too long
                    reasoning = content.strip()
                    if len(reasoning) > 80:
                        reasoning = reasoning[:80] + "..."
                    display_content = f"{reasoning}\n→ {tool_str}"
                else:
                    display_content = tool_str
        
        # Check if culprit
        is_culprit = msg_id in culprit_ids
        confidence = 0.0
        explanation = ""
        if hasattr(msg, '_culprit_metadata'):
            metadata = msg._culprit_metadata
            is_culprit = metadata.get('is_culprit', False) or is_culprit
            confidence = metadata.get('confidence', 0.0)
            explanation = metadata.get('explanation', '')
        
        # Node attributes
        node_attrs = {
            'type': msg_type,
            'label': f"{msg_type.upper()}\n{display_content}",
            'content': content,
            'is_culprit': is_culprit,
            'confidence': confidence,
            'explanation': explanation,
            'index': idx
        }
        
        G.add_node(msg_id, **node_attrs)
        
        # Add edge from previous message (sequential flow)
        if idx > 0:
            prev_msg = messages[idx - 1]
            if isinstance(prev_msg, BaseMessage):
                prev_id = getattr(prev_msg, 'id', f'msg_{idx-1}')
                G.add_edge(prev_id, msg_id, relation='next')
    
    return G


def visualize_graph_html(
    trace_data: Dict[str, Any],
    output_path: Optional[str] = "trace_graph.html",
    culprit_ids: Optional[Set[str]] = None,
    height: str = "800px",
    width: str = "100%"
) -> str:
    """
    Create an interactive HTML visualization of the trace graph.
    
    Args:
        trace_data: Dict with 'messages' key containing LangChain message objects
        output_path: Path to save HTML file (if None, uses temp file)
        culprit_ids: Set of message IDs that are culprits
        height: Height of visualization
        width: Width of visualization
    
    Returns:
        Path to saved HTML file
    """
    import tempfile
    import os
    
    if output_path is None:
        # Create temporary file
        fd, output_path = tempfile.mkstemp(suffix='.html', prefix='trace_graph_')
        os.close(fd)
    if not HAS_PYVIS or not HAS_NETWORKX:
        raise ImportError("pyvis and networkx are required for HTML visualization")
    
    G = create_trace_graph(trace_data, culprit_ids)
    
    # Create pyvis network
    net = Network(height=height, width=width, directed=True, bgcolor="#222222", font_color="white")
    
    # Define colors for node types
    node_colors = {
        'human': '#4A90E2',      # Blue
        'ai': '#50C878',         # Green
        'tool': '#FF6B9D',       # Pink
        'unknown': '#CCCCCC'     # Gray
    }
    
    # Add nodes
    for node_id, node_data in G.nodes(data=True):
        node_type = node_data.get('type', 'unknown')
        label = node_data.get('label', node_id)
        is_culprit = node_data.get('is_culprit', False)
        confidence = node_data.get('confidence', 0.0)
        explanation = node_data.get('explanation', '')
        
        # Base color by type
        color = node_colors.get(node_type, '#CCCCCC')
        
        # Override color if culprit
        if is_culprit:
            if confidence >= 0.8:
                color = '#FF4444'  # Red for high confidence
            elif confidence >= 0.6:
                color = '#FF8800'  # Orange for medium confidence
            else:
                color = '#FFAA00'  # Yellow for low confidence
        
        # Node size based on culprit status
        size = 30 if is_culprit else 20
        
        # Tooltip
        title = f"Type: {node_type}\n{label}"
        if is_culprit:
            title += f"\n\n⚠️ CULPRIT\nConfidence: {confidence:.2f}\nExplanation: {explanation}"
        
        # Border for culprits
        border_width = 3 if is_culprit else 1
        border_color = '#FF0000' if is_culprit else '#333333'
        
        net.add_node(
            node_id,
            label=label,
            color=color,
            title=title,
            size=size,
            borderWidth=border_width,
            borderWidthSelected=5,
            font={'size': 12, 'face': 'Arial'}
        )
    
    # Add edges
    for source, target, edge_data in G.edges(data=True):
        net.add_edge(
            source,
            target,
            color='#666666',
            width=2,
            arrows='to'
        )
    
    # Configure physics
    net.set_options("""
    {
      "physics": {
        "enabled": true,
        "hierarchicalRepulsion": {
          "centralGravity": 0.0,
          "springLength": 150,
          "springConstant": 0.01,
          "nodeDistance": 100,
          "damping": 0.09
        },
        "solver": "hierarchicalRepulsion"
      },
      "interaction": {
        "dragNodes": true,
        "dragView": true,
        "zoomView": true
      }
    }
    """)
    
    net.save_graph(output_path)
    return output_path
