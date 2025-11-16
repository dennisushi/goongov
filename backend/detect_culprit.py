"""
Detect culprit messages in agent execution traces.

This module analyzes trace messages in reverse chronological order to find
the origin of issues reported by users.
"""

import json
import re
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.messages import HumanMessage, AIMessage, ToolMessage, BaseMessage
from langchain_core.prompts import ChatPromptTemplate

# Try to import LLM providers
try:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "core"))
    from react_agent.holistic_ai_bedrock import get_chat_model
    HAS_BEDROCK = True
except ImportError:
    try:
        from langchain_openai import ChatOpenAI
        HAS_BEDROCK = False
    except ImportError:
        HAS_BEDROCK = None


def _extract_llm_from_agent(agent_instance) -> Any:
    """
    Extract the underlying LLM from an Agent instance.
    
    The Agent class wraps a LangGraph agent, so we need to extract the LLM.
    For now, we'll create a new LLM with the same model name.
    """
    # Try to get model name from agent
    if hasattr(agent_instance, 'model_name'):
        model_name = agent_instance.model_name
        try:
            if HAS_BEDROCK:
                return get_chat_model(model_name)
            else:
                return ChatOpenAI(model=model_name, temperature=0)
        except:
            pass
    
    # Fallback: try to access agent.agent and extract LLM from graph nodes
    # This is complex, so for now we'll just create a default LLM
    try:
        if HAS_BEDROCK:
            return get_chat_model("claude-3-5-sonnet")
        else:
            return ChatOpenAI(model="gpt-4", temperature=0)
    except:
        raise ValueError("Could not extract or create LLM from Agent instance")


def format_message_for_analysis(msg: BaseMessage, index: int) -> str:
    """Format a LangChain message object into a readable string for LLM analysis."""
    msg_type = msg.__class__.__name__.replace("Message", "").lower()
    content = getattr(msg, 'content', '') or ''
    
    # Handle tool calls
    tool_calls = getattr(msg, 'tool_calls', [])
    if tool_calls:
        tool_info = []
        for tc in tool_calls:
            tool_name = tc.get('name', 'unknown')
            tool_args = tc.get('args', {})
            tool_info.append(f"{tool_name}({tool_args})")
        content += f" [Tool calls: {', '.join(tool_info)}]"
    
    # Handle additional kwargs
    additional_kwargs = getattr(msg, 'additional_kwargs', {})
    if additional_kwargs.get('tool_calls'):
        tool_info = []
        for tc in additional_kwargs['tool_calls']:
            func = tc.get('function', {})
            tool_name = func.get('name', 'unknown')
            tool_args = func.get('arguments', '{}')
            tool_info.append(f"{tool_name}({tool_args})")
        content += f" [Tool calls: {', '.join(tool_info)}]"
    
    # Build formatted string
    formatted = f"[{msg_type.upper()}]"
    if hasattr(msg, 'name') and msg.name:
        formatted += f" ({msg.name})"
    formatted += f": {content}"
    
    return formatted


def find_issue_origin(
    trace_data: Dict[str, Any],
    user_question: str,
    llm_model: Any,
    max_messages_to_check: int = 20,
    confidence_threshold: float = 0.5
) -> Tuple[List[Tuple[BaseMessage, float, str]], Dict[str, Any]]:
    """
    Analyze trace messages in reverse order to find the origin of an issue.
    
    Args:
        trace_data: Dict with 'messages' key containing LangChain message objects
        user_question: The user's question about an issue (e.g., "why did they choose this room")
        llm_model: Agent instance or LLM model
        max_messages_to_check: Maximum number of messages to check (starting from most recent)
        confidence_threshold: Minimum confidence score (0-1) to consider a message relevant
    
    Returns:
        Tuple of:
        - List of tuples: (message, confidence_score, explanation) sorted by confidence
        - Summary dict with analysis results
    """
    # Extract LLM from agent if needed
    if hasattr(llm_model, 'agent') or hasattr(llm_model, 'model_name'):
        # It's an Agent instance
        llm = _extract_llm_from_agent(llm_model)
    else:
        # Assume it's already an LLM
        llm = llm_model
    
    # Extract messages from trace data
    if not isinstance(trace_data, dict) or 'messages' not in trace_data:
        raise ValueError("trace_data must be a dict with 'messages' key")
    
    messages = trace_data['messages']
    if not messages:
        return [], {}
    
    # Filter to only BaseMessage objects and reverse order (most recent first)
    message_list = [msg for msg in messages if isinstance(msg, BaseMessage)]
    message_list = list(reversed(message_list))[:max_messages_to_check]
    
    if not message_list:
        return [], {}
    
    # Create evaluation prompt
    evaluation_prompt = ChatPromptTemplate.from_messages([
        ("system", """You are an expert at analyzing agent execution traces to find the root cause of issues.

Your task is to evaluate whether a specific message in an execution trace is the origin or cause of a user-reported issue.

For each message, provide:
1. A confidence score from 0.0 to 1.0 indicating how likely this message is the origin of the issue
2. A brief explanation (1-2 sentences) of why this message is or isn't relevant

Consider:
- Does this message contain the decision, action, or information that led to the issue?
- Is this message where the problematic choice was made?
- Does this message show incorrect reasoning or data that caused the problem?

Respond ONLY with valid JSON in this exact format:
{{"confidence": 0.0-1.0, "explanation": "brief explanation"}}"""),
        ("human", """User Question: {user_question}

Message to evaluate:
{message_content}

Context: This is message {message_index} of {total_messages} (evaluating in reverse chronological order, most recent first).

Provide your evaluation as JSON with 'confidence' and 'explanation' fields.""")
    ])
    
    results = []
    culprit_message_ids = set()
    
    # Evaluate each message
    for idx, msg in enumerate(message_list):
        message_content = format_message_for_analysis(msg, idx)
        msg_id = getattr(msg, 'id', f'msg_{idx}')
        
        try:
            # Get LLM evaluation
            chain = evaluation_prompt | llm
            response = chain.invoke({
                "user_question": user_question,
                "message_content": message_content,
                "message_index": idx + 1,
                "total_messages": len(message_list)
            })
            
            # Parse response
            response_text = response.content if hasattr(response, "content") else str(response)
            
            # Try to extract JSON from response
            json_match = re.search(r'\{[^{}]*"confidence"[^{}]*\}', response_text, re.DOTALL)
            if json_match:
                try:
                    eval_result = json.loads(json_match.group())
                    confidence = float(eval_result.get("confidence", 0.0))
                    explanation = eval_result.get("explanation", "No explanation provided")
                except:
                    # Fallback: try to extract confidence from text
                    conf_match = re.search(r'confidence["\s:]+([0-9.]+)', response_text, re.IGNORECASE)
                    confidence = float(conf_match.group(1)) if conf_match else 0.0
                    explanation = response_text[:200]
            else:
                # Fallback parsing
                conf_match = re.search(r'confidence["\s:]+([0-9.]+)', response_text, re.IGNORECASE)
                confidence = float(conf_match.group(1)) if conf_match else 0.0
                explanation = response_text[:200]
            
            # Mark message as culprit if above threshold
            is_culprit = confidence >= confidence_threshold
            if is_culprit:
                culprit_message_ids.add(msg_id)
                results.append((msg, confidence, explanation))
            
            # Add metadata to message object
            msg._culprit_metadata = {
                'is_culprit': is_culprit,
                'confidence': confidence,
                'explanation': explanation
            }
                
        except Exception as e:
            print(f"Error evaluating message {idx + 1}: {e}")
            # Mark as not culprit on error
            msg._culprit_metadata = {
                'is_culprit': False,
                'confidence': 0.0,
                'explanation': f"Error during evaluation: {str(e)}"
            }
            continue
    
    # Sort by confidence (highest first)
    results.sort(key=lambda x: x[1], reverse=True)
    
    # Create summary
    summary = {
        'total_messages_checked': len(message_list),
        'culprits_found': len(results),
        'confidence_threshold': confidence_threshold,
        'culprit_message_ids': list(culprit_message_ids)
    }
    
    return results, summary
