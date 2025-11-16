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


def _get_message_type(msg) -> str:
    """Helper to get message type from either BaseMessage object or dict."""
    if isinstance(msg, dict):
        # Try multiple ways to get the type
        msg_type = msg.get('type', '').lower()
        
        # Check lc_kwargs
        if not msg_type and 'lc_kwargs' in msg:
            msg_type = msg['lc_kwargs'].get('type', '').lower()
        
        # Check lc_id (LangChain serialization format)
        if not msg_type and 'lc_id' in msg:
            lc_id = msg['lc_id']
            if isinstance(lc_id, list) and len(lc_id) > 0:
                # lc_id format: ["langchain", "messages", "ai", "Message"]
                if len(lc_id) >= 3:
                    msg_type = lc_id[2].lower()
        
        # Try to infer from class name in __class__ field
        if not msg_type or msg_type == 'unknown':
            class_info = msg.get('__class__', {})
            if isinstance(class_info, dict):
                class_name = class_info.get('name', '')
            else:
                class_name = str(class_info)
            
            if 'System' in class_name or 'system' in class_name:
                msg_type = 'system'
            elif 'Human' in class_name or 'human' in class_name:
                msg_type = 'human'
            elif 'AI' in class_name or 'ai' in class_name:
                msg_type = 'ai'
            elif 'Tool' in class_name or 'tool' in class_name:
                msg_type = 'tool'
        
        # Normalize the type
        if msg_type:
            msg_type = msg_type.replace('message', '').replace('_', '').lower()
            # Map common variations
            if msg_type in ['human', 'h']:
                return 'human'
            elif msg_type in ['ai', 'assistant', 'a']:
                return 'ai'
            elif msg_type in ['tool', 't']:
                return 'tool'
            elif msg_type in ['system', 's']:
                return 'system'
        
        # If still unknown, try to infer from presence of tool-specific fields
        if 'name' in msg or 'tool_call_id' in msg:
            return 'tool'
        if 'tool_calls' in msg:
            return 'ai'
        
        return 'unknown'
    else:
        # BaseMessage object
        return getattr(msg, 'type', 'unknown')


def _get_message_content(msg) -> str:
    """Helper to get message content from either BaseMessage object or dict."""
    if isinstance(msg, dict):
        return msg.get('content', msg.get('lc_kwargs', {}).get('content', ''))
    else:
        return getattr(msg, 'content', '')


def _get_message_name(msg) -> str:
    """Helper to get message name (for tool messages) from either BaseMessage object or dict."""
    if isinstance(msg, dict):
        return msg.get('name', msg.get('lc_kwargs', {}).get('name', ''))
    else:
        return getattr(msg, 'name', '')


def _get_message_tool_calls(msg) -> list:
    """Helper to get tool calls from either BaseMessage object or dict."""
    if isinstance(msg, dict):
        return msg.get('tool_calls', msg.get('lc_kwargs', {}).get('tool_calls', []))
    else:
        return getattr(msg, 'tool_calls', [])


def format_message_for_analysis(msg: BaseMessage, index: int) -> str:
    """Format a LangChain message object into a readable string for LLM analysis."""
    # Handle both BaseMessage objects and dicts
    if isinstance(msg, dict):
        msg_type = _get_message_type(msg)
        content = _get_message_content(msg)
        name = _get_message_name(msg)
        tool_calls = _get_message_tool_calls(msg)
    else:
        msg_type = msg.__class__.__name__.replace("Message", "").lower()
        content = getattr(msg, 'content', '') or ''
        name = getattr(msg, 'name', None)
        tool_calls = getattr(msg, 'tool_calls', [])
    
    # Handle tool calls
    if tool_calls:
        tool_info = []
        for tc in tool_calls:
            if isinstance(tc, dict):
                tool_name = tc.get('name', 'unknown')
                tool_args = tc.get('args', {})
            else:
                tool_name = getattr(tc, 'name', 'unknown')
                tool_args = getattr(tc, 'args', {})
            tool_info.append(f"{tool_name}({tool_args})")
        content += f" [Tool calls: {', '.join(tool_info)}]"
    
    # Handle additional kwargs (for BaseMessage objects)
    if not isinstance(msg, dict):
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
    if name:
        formatted += f" ({name})"
    formatted += f": {content}"
    
    return formatted


def find_issue_origin(
    trace_data: Dict[str, Any],
    user_question: str,
    llm_model: Any,
    max_messages_to_check: int = 20,
    confidence_threshold: float = 0.5,
    use_component_focus: bool = True
) -> Tuple[List[Tuple[BaseMessage, float, str]], Dict[str, Any]]:
    """
    Analyze trace messages to find the origin of an issue.
    Improved version that uses component identification for better focus.
    
    Args:
        trace_data: Dict with 'messages' key containing LangChain message objects
        user_question: The user's question about an issue (e.g., "why did they choose this room")
        llm_model: Agent instance or LLM model
        max_messages_to_check: Maximum number of messages to check (starting from most recent)
        confidence_threshold: Minimum confidence score (0-1) to consider a message relevant
        use_component_focus: If True, first identifies relevant components to focus analysis
    
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
    
    # Filter to only BaseMessage objects
    message_list = [msg for msg in messages if isinstance(msg, BaseMessage)]
    
    if not message_list:
        return [], {}
    
    # Step 1: Optionally identify relevant components to focus analysis
    relevant_components = None
    if use_component_focus and len(message_list) > 3:
        print("--- Identifying relevant components for focused analysis ---")
        try:
            # Extract original query from first HumanMessage to help with component identification
            original_query = ""
            for msg in message_list:
                if _get_message_type(msg) == 'human':
                    original_query = _get_message_content(msg)
                    # Clean up if it contains system prompt
                    if original_query and len(original_query) > 500:
                        lines = original_query.split('\n')
                        for line in reversed(lines):
                            if line.strip() and not line.strip().startswith('You are'):
                                original_query = line.strip()
                                break
                    break
            
            # Identify components that might be relevant to the user's question
            component_prompt = ChatPromptTemplate.from_messages([
                ("system", """You are analyzing an agent execution trace to identify which components might be relevant to answering a user's question.

The agent has two types of components:
1. 'Orchestrator': The AI's own reasoning (its 'Thought' steps and 'Final Answer').
2. 'Tools': The functions it calls (e.g., `check_calendar`, `check_room_rules`, `assign_task`).

Based on the user's question, identify which components are most likely to contain relevant information.
Respond with a comma-separated list of component names, or 'all' if all components are relevant.
Examples: "Orchestrator, check_room_rules" or "all"
"""),
                ("human", """User Question: {user_question}
Original Query: {original_query}

Which components are most relevant to answering this question? Respond with component names separated by commas, or 'all'.""")
            ])
            
            component_chain = component_prompt | llm
            component_response = component_chain.invoke({
                "user_question": user_question,
                "original_query": original_query
            })
            
            component_text = component_response.content.strip().lower()
            if component_text != 'all':
                relevant_components = [c.strip() for c in component_text.split(',')]
                print(f"Focusing analysis on components: {relevant_components}")
            else:
                print("Analyzing all components")
        except Exception as e:
            print(f"Component identification failed, analyzing all messages: {e}")
            relevant_components = None
    
    # Step 2: Filter messages to focus on relevant ones
    # Reverse order (most recent first) for analysis
    message_list_reversed = list(reversed(message_list))
    
    # If we have relevant components, prioritize messages from those components
    if relevant_components:
        prioritized_messages = []
        other_messages = []
        
        for msg in message_list_reversed:
            is_relevant = False
            msg_component = None
            
            # Determine which component this message belongs to
            msg_type = _get_message_type(msg)
            if msg_type == 'ai':
                msg_component = 'Orchestrator'
            elif msg_type == 'tool':
                msg_component = _get_message_name(msg)
            
            # Check if it's in our relevant components
            if msg_component and msg_component in relevant_components:
                is_relevant = True
            
            if is_relevant:
                prioritized_messages.append(msg)
            else:
                other_messages.append(msg)
        
        # Combine: relevant first, then others, up to max_messages_to_check
        message_list_reversed = prioritized_messages + other_messages
    
    message_list_reversed = message_list_reversed[:max_messages_to_check]
    
    if not message_list_reversed:
        return [], {}
    
    # Step 3: Create evaluation prompt with better context (similar to failure_analysis)
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
- What component does this message belong to (Orchestrator or a specific Tool)?

Respond ONLY with valid JSON in this exact format:
{{"confidence": 0.0-1.0, "explanation": "brief explanation", "component": "component_name"}}"""),
        ("human", """User Question: {user_question}

Execution Trace Context:
{execution_context}

Message to evaluate (Step {message_index}):
{message_content}

This is message {message_index} of {total_messages} (evaluating in reverse chronological order, most recent first).

Provide your evaluation as JSON with 'confidence', 'explanation', and 'component' fields.""")
    ])
    
    results = []
    culprit_message_ids = set()
    component_counts = {}
    
    # Build execution context (similar to format_log_for_prompt but for context)
    full_context = format_log_for_prompt(message_list)
    
    # Evaluate each message with better context
    for idx, msg in enumerate(message_list_reversed):
        # Find original index in full message list for context
        try:
            original_idx = message_list.index(msg)
        except ValueError:
            # If msg is not in list (shouldn't happen), use current index
            original_idx = idx
        message_content = format_message_for_analysis(msg, original_idx)
        msg_id = getattr(msg, 'id', None) if not isinstance(msg, dict) else msg.get('id', f'msg_{original_idx}')
        if not msg_id:
            msg_id = f'msg_{original_idx}'
        
        # Determine component for this message
        msg_type = _get_message_type(msg)
        msg_component = None
        if msg_type == 'ai':
            msg_component = 'Orchestrator'
        elif msg_type == 'tool':
            msg_component = _get_message_name(msg)
        
        try:
            # Get LLM evaluation with full context
            chain = evaluation_prompt | llm
            response = chain.invoke({
                "user_question": user_question,
                "execution_context": full_context,
                "message_content": message_content,
                "message_index": idx + 1,
                "total_messages": len(message_list_reversed)
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
                    identified_component = eval_result.get("component", msg_component or "Unknown")
                except:
                    # Fallback: try to extract confidence from text
                    conf_match = re.search(r'confidence["\s:]+([0-9.]+)', response_text, re.IGNORECASE)
                    confidence = float(conf_match.group(1)) if conf_match else 0.0
                    explanation = response_text[:200]
                    identified_component = msg_component or "Unknown"
            else:
                # Fallback parsing
                conf_match = re.search(r'confidence["\s:]+([0-9.]+)', response_text, re.IGNORECASE)
                confidence = float(conf_match.group(1)) if conf_match else 0.0
                explanation = response_text[:200]
                identified_component = msg_component or "Unknown"
            
            # Track component counts
            if identified_component:
                component_counts[identified_component] = component_counts.get(identified_component, 0) + 1
            
            # Enhance explanation with component info if not already present
            if identified_component and identified_component not in explanation:
                explanation = f"[{identified_component}] {explanation}"
            
            # Mark message as culprit if above threshold
            is_culprit = confidence >= confidence_threshold
            if is_culprit:
                culprit_message_ids.add(msg_id)
                results.append((msg, confidence, explanation))
            
            # Add metadata to message object (handle both dicts and BaseMessage objects)
            if isinstance(msg, dict):
                msg['_culprit_metadata'] = {
                    'is_culprit': is_culprit,
                    'confidence': confidence,
                    'explanation': explanation,
                    'component': identified_component
                }
            else:
                msg._culprit_metadata = {
                    'is_culprit': is_culprit,
                    'confidence': confidence,
                    'explanation': explanation,
                    'component': identified_component
                }
                
        except Exception as e:
            print(f"Error evaluating message {idx + 1}: {e}")
            # Mark as not culprit on error
            metadata = {
                'is_culprit': False,
                'confidence': 0.0,
                'explanation': f"Error during evaluation: {str(e)}",
                'component': msg_component or "Unknown"
            }
            if isinstance(msg, dict):
                msg['_culprit_metadata'] = metadata
            else:
                msg._culprit_metadata = metadata
            continue
    
    # Sort by confidence (highest first)
    results.sort(key=lambda x: x[1], reverse=True)
    
    # Identify most common component in culprits
    culprit_components = {}
    for msg, confidence, explanation in results:
        component = getattr(msg, '_culprit_metadata', {}).get('component', 'Unknown')
        culprit_components[component] = culprit_components.get(component, 0) + 1
    
    primary_component = max(culprit_components.items(), key=lambda x: x[1])[0] if culprit_components else None
    
    # Create summary
    summary = {
        'total_messages_checked': len(message_list_reversed),
        'culprits_found': len(results),
        'confidence_threshold': confidence_threshold,
        'culprit_message_ids': list(culprit_message_ids),
        'primary_component': primary_component,
        'component_breakdown': culprit_components,
        'focused_components': relevant_components
    }
    
    return results, summary


def format_log_for_prompt(log: list[BaseMessage]) -> str:
    """Helper function to turn the message list into a readable string."""
    formatted = []
    for i, msg in enumerate(log):
        msg_type = _get_message_type(msg)
        content = _get_message_content(msg)
        
        if msg_type == 'system':
            formatted.append("Step 0 (System): [System Prompt Loaded]")
        elif msg_type == 'human':
            formatted.append(f"Step {i} (Human): {content}")
        elif msg_type == 'ai':
            tool_calls = _get_message_tool_calls(msg)
            if tool_calls:
                calls = []
                for tc in tool_calls:
                    if isinstance(tc, dict):
                        name = tc.get('name', 'unknown')
                        args = tc.get('args', {})
                    else:
                        name = getattr(tc, 'name', 'unknown')
                        args = getattr(tc, 'args', {})
                    calls.append(f"{name}({args})")
                formatted.append(f"Step {i} (AI Thought): {content}\nStep {i} (AI Action): {', '.join(calls)}")
            else:
                formatted.append(f"Step {i} (AI Final Answer): {content}")
        elif msg_type == 'tool':
            name = _get_message_name(msg)
            formatted.append(f"Step {i} (Observation from {name}): {content}")
    return "\n".join(formatted)
    
def find_responsible_component(judge_llm,query: str, log: list[BaseMessage]) -> str:
    """
    Uses an 'all-at-once' prompt to find the component
    (Orchestrator or a Tool) responsible for the decision/outcome.
    This identifies the component that made the key decision, whether it was an error or not.
    """
    print("--- 1. Running All-at-Once Analysis ---")
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """
You are a decision attribution expert for an AI agent.
The agent's task was to answer a user query. 
The agent has two types of components:
1.  'Orchestrator': The AI's own reasoning (its 'Thought' steps and 'Final Answer').
2.  'Tools': The functions it calls (e.g., `check_calendar`, `check_room_rules`).

Your job is to identify which single component is *most responsible*
for the final decision or outcome. This could be:
- The component that made the key decision
- The component that provided critical information that led to the outcome
- The component that executed the final action

Respond with *only* the name of the component (e.g., 'Orchestrator', 'check_room_rules', 'assign_task').
"""),
        ("human", """
User Query: {query}

Full Execution Log:
{log}

Based on the log, which component is most responsible for the final decision or outcome?
Respond with *only* the name of the component (e.g., 'Orchestrator', 'check_room_rules', 'assign_task').
""")
    ])
    
    chain = prompt_template | judge_llm
    response = chain.invoke({
        "query": query,
        "log": format_log_for_prompt(log)
    })
    
    component_name = response.content.strip().replace("'", "").replace('"', '')
    print(f"Responsible component identified: {component_name}")
    return component_name

def find_decisive_error_step(judge_llm, query: str, log: list[BaseMessage], responsible_component: str) -> dict:
    """
    Uses a 'step-by-step' prompt to find the exact error step,
    searching *only* messages from the responsible component.
    Returns None if no error is found (but the component is still responsible for the decision).
    """
    print(f"--- 2. Running Step-by-Step Analysis on '{responsible_component}' ---")
    
    prompt_template = ChatPromptTemplate.from_messages([
        ("system", """
You are a high-precision decision analyst. 
You must determine if the *very last step* in the provided history
contains an error or incorrect decision that led to a failure.

The user's goal: {query}

If there is an error, respond with 'Yes'. If the decision was correct (even if the outcome wasn't ideal), respond with 'No'.

Respond with 'Yes' or 'No' and a brief reason.
Format:
Yes/No: [Your decision]
Reason: [Your explanation]
"""),
        ("human", "Conversation history up to the current step:\n{log_so_far}")
    ])
    
    chain = prompt_template | judge_llm

    # Filter the log to create a "search space"
    # A "step" is a message in the log
    for i, msg in enumerate(log):
        # Determine if this message 'msg' is part of the component we're searching
        msg_type = _get_message_type(msg)
        is_relevant_step = False
        if responsible_component == 'Orchestrator' and msg_type == 'ai':
            is_relevant_step = True
        elif msg_type == 'tool' and _get_message_name(msg) == responsible_component:
            is_relevant_step = True
            
        if not is_relevant_step:
            continue # Skip analysis for this step

        print(f"Analyzing step {i} (Type: {msg_type}, Name: {_get_message_name(msg) or 'N/A'})...")
        
        # Get the log up to and including this step
        log_so_far = log[:i+1]
        
        response = chain.invoke({
            "query": query,
            "log_so_far": format_log_for_prompt(log_so_far)
        })
        
        # Parse the 'Yes/No' answer
        if "Yes" in response.content.splitlines()[0]:
            print(f"Found decisive error at step {i}.")
            return {"step_index": i, "message": msg, "reason": response.content}

    print("No decisive error step found by the judge.")
    return None

def failure_analysis(result, original_user_query, judge_llm):
    """
    Analyze failure using a two-step approach:
    1. Find the responsible component (Orchestrator or Tool)
    2. Find the decisive error step within that component
    
    Args:
        result: Dict with 'messages' key containing LangChain message objects
        original_user_query: The original user query that generated the trace (not the critic query)
        judge_llm: Agent instance or LLM model to use for analysis
    
    Returns:
        Tuple of:
        - List of tuples: (message, confidence_score, explanation) sorted by confidence
        - Summary dict with analysis results
    """
    # Extract LLM from agent if needed (same as find_issue_origin)
    if hasattr(judge_llm, 'agent') or hasattr(judge_llm, 'model_name'):
        # It's an Agent instance
        llm = _extract_llm_from_agent(judge_llm)
    else:
        # Assume it's already an LLM
        llm = judge_llm
    
    # Extract messages from result
    if not isinstance(result, dict) or 'messages' not in result:
        raise ValueError("result must be a dict with 'messages' key")
    
    failure_log = result['messages']
    if not failure_log:
        return [], {}
    
    # 1. Get the responsible component (use original query, not critic query)
    responsible_component = find_responsible_component(llm, original_user_query, failure_log)

    # 2. Get the decisive error step (use original query, not critic query)
    decisive_error = find_decisive_error_step(llm, original_user_query, failure_log, responsible_component)

    # 3. Build return values - identify failures (not culprits)
    failures = []
    failure_message_ids = []
    
    # Find the message(s) from the responsible component to tag
    responsible_messages = []
    for i, msg in enumerate(failure_log):
        msg_type = _get_message_type(msg)
        is_relevant = False
        if responsible_component == 'Orchestrator' and msg_type == 'ai':
            is_relevant = True
        elif msg_type == 'tool' and _get_message_name(msg) == responsible_component:
            is_relevant = True
        
        if is_relevant:
            responsible_messages.append((i, msg))
    
    # Tag failures - if there's a decisive error, that's a failure
    # Note: We don't tag as "responsible node" here - that's for find_issue_origin
    if decisive_error:
        msg = decisive_error['message']
        msg_id = getattr(msg, 'id', None)
        if msg_id:
            failure_message_ids.append(msg_id)
        
        # Create explanation without [RESPONSIBLE NODE] tag
        explanation = f"[FAILURE DETECTED] Decisive error in {responsible_component}. {decisive_error.get('reason', '')}"
        failures.append((msg, 1.0, explanation))
        
        # Add metadata to message object - mark as failure, not responsible node
        metadata = {
            'is_failure': True,
            'confidence': 1.0,
            'explanation': explanation,
            'responsible_component': responsible_component
        }
        # Preserve existing metadata if present
        existing_metadata = None
        if isinstance(msg, dict):
            existing_metadata = msg.get('_culprit_metadata', {})
        elif hasattr(msg, '_culprit_metadata'):
            existing_metadata = msg._culprit_metadata if isinstance(msg._culprit_metadata, dict) else {}
        
        if existing_metadata:
            metadata.update(existing_metadata)
        
        if isinstance(msg, dict):
            msg['_culprit_metadata'] = metadata
        else:
            msg._culprit_metadata = metadata
    # Note: We don't tag non-error cases as failures - only actual errors
    
    # Mark all other messages as not failures (for compatibility)
    for msg in failure_log:
        has_metadata = hasattr(msg, '_culprit_metadata') if not isinstance(msg, dict) else '_culprit_metadata' in msg
        if not has_metadata:
            metadata = {
                'is_failure': False,
                'confidence': 0.0,
                'explanation': ''
            }
            if isinstance(msg, dict):
                msg['_culprit_metadata'] = metadata
            else:
                msg._culprit_metadata = metadata
        else:
            # Ensure is_failure flag exists
            if isinstance(msg, dict):
                if '_culprit_metadata' not in msg or not isinstance(msg['_culprit_metadata'], dict):
                    msg['_culprit_metadata'] = {}
                if 'is_failure' not in msg['_culprit_metadata']:
                    msg['_culprit_metadata']['is_failure'] = False
            else:
                if not hasattr(msg, '_culprit_metadata') or not isinstance(msg._culprit_metadata, dict):
                    msg._culprit_metadata = {}
                if 'is_failure' not in msg._culprit_metadata:
                    msg._culprit_metadata['is_failure'] = False
    
    # Create summary
    summary = {
        'total_messages_checked': len(failure_log),
        'failures_found': len(failures),
        'confidence_threshold': 0.5,  # Default threshold
        'failure_message_ids': failure_message_ids,
        'responsible_component': responsible_component,
        'decisive_error_step_index': decisive_error['step_index'] if decisive_error else None,
        # For backward compatibility
        'culprits_found': len(failures),
        'culprit_message_ids': failure_message_ids
    }
    
    # 4. Print the final result
    print("\n" + "="*30)
    print("--- 🏁 Failure Analysis Complete ---")
    print(f"Responsible Component: {responsible_component}")
    
    if decisive_error:
        print(f"Failure Detected at Step Index: {decisive_error['step_index']}")
        print("\n--- Failure Message ---")
        print(decisive_error['message'])
        print("\n--- Judge's Reason ---")
        print(decisive_error['reason'])
    else:
        print("\nNo failure detected - component made the decision but no error was found.")
    print("="*30)
    
    return failures, summary