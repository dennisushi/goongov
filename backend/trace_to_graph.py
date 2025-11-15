
from termcolor import colored

def print_message_summary(msg):
    """
    Pretty-print a summary of a message object with colored type and content/redirect.
    Handles HumanMessage, AIMessage, ToolMessage.
    """
    msg_type = type(msg).__name__
    content = getattr(msg, 'content', '')
    if msg_type == "HumanMessage":
        tcolor = 'cyan'
        important = content.strip().split("\n")[-1][:100]  # Last line of prompt, max 100 chars
    elif msg_type == "AIMessage":
        tcolor = 'green'
        # If tool call(s), summarize; else, show content
        tool_calls = getattr(msg, 'tool_calls', None)
        if tool_calls and len(tool_calls) > 0:
            tc = tool_calls[0]
            important = f"Tool call: {tc.get('name', '')}({tc.get('args', {})})"
        else:
            important = content.strip()[:100]
    elif msg_type == "ToolMessage":
        tcolor = 'magenta'
        toolname = getattr(msg, "name", "")
        if content.startswith("Observation"):
            important = content.strip()[:120]
        else:
            important = f"{toolname}: {content.strip()[:100]}"
    else:
        tcolor='yellow'
        important = str(content)[:100]
    print(colored(f"[{msg_type:12s}] ", tcolor, attrs=["bold"]), end='')
    print(important)

