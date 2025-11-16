import os
import time
import json
from pathlib import Path
from dotenv import load_dotenv
import langfuse
from langfuse import observe
from langchain_core.tools import tool


# ============================================
# Load ENV (.env recommended)
# ============================================
env_path = Path('../.env')
if env_path.exists():
    load_dotenv(env_path)
    print("📄 Loaded configuration from .env file")
else:
    print("⚠️  No .env file found - using environment variables or hardcoded keys")

# ============================================
# 🔑 Langfuse Key Extraction
# ============================================
need_langfuse = False

if need_langfuse:
    LANGFUSE_PUBLIC_KEY = "pk-lf-43f9272f-d4a4-4efa-9a8c-d697f987f9b7"
    LANGFUSE_SECRET_KEY = "sk-lf-c95015fa-b35d-4885-b18c-cc10a21b6fba"
    LANGFUSE_HOST = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not LANGFUSE_PUBLIC_KEY or not LANGFUSE_SECRET_KEY:
        print("⚠️  Langfuse keys missing. Set LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY in .env.")
    else:
        print("✅ Langfuse keys loaded")

    # Initialize Langfuse client
    try:
        langfuse_client = langfuse.Langfuse(
            public_key=LANGFUSE_PUBLIC_KEY,
            secret_key=LANGFUSE_SECRET_KEY,
            host=LANGFUSE_HOST
        )
        print("✅ Langfuse client initialized")
    except Exception as e:
        print(f"❌ Failed to initialize Langfuse client: {e}")

# ============================================
# Import Holistic AI Bedrock helper (Optional)
# ============================================
import sys
try:
    sys.path.insert(0, '../core')
    from react_agent.holistic_ai_bedrock import HolisticAIBedrockChat, get_chat_model
    print("✅ Holistic AI Bedrock helper function loaded")
except ImportError:
    print("⚠️  Could not import from core - will use OpenAI only")

from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from typing import List

# ============================================
# Verify other API keys
# ============================================
print("\n🔑 API Key Status:")
if os.getenv('HOLISTIC_AI_TEAM_ID') and os.getenv('HOLISTIC_AI_API_TOKEN'):
    print("  ✅ Holistic AI Bedrock credentials loaded (will use Bedrock)")
elif os.getenv('OPENAI_API_KEY'):
    print("  ⚠️  OpenAI API key loaded (Bedrock credentials not set)")
    print("     💡 Tip: Set HOLISTIC_AI_TEAM_ID and HOLISTIC_AI_API_TOKEN to use Bedrock (recommended)")
else:
    print("  ⚠️  No API keys found")
    print("     Set Holistic AI Bedrock credentials (recommended) or OpenAI key")

print("✅ All imports successful!")
os.environ["LANGSMITH_TRACING"] = "false"

##old tools
##
##@observe()
##def check_calendar(date : str) -> str:
##    """Check if the community center is available on the given date."""
##    # Simulated calendar data
##    #booked_dates = ["2025-12-01", "2025-12-03", "2025-12-10"]
##    #return date not in booked_dates
##    return f"Observation:{date} is AVAILABLE"
##
##@observe()
##def check_room_rules(room_id: str) -> str:
##    """Check the rules for booking a specific room.
##    Example rules: No smoking"""
##    return f"Observation: Rules for {room_id} are 'max_capacity: 50, no_food_allowed'."
##
##@observe()
##def assign_task(staff_name: str, task : str) -> str:
##    """Assign a task to a staff member."""
##    return f"Action successful: Task '{task}' assigned to {staff_name}."
##

#new tools

@tool
@observe()
def get_rooms() -> List[str]:
    """Get a list of available rooms in the community center."""
    return ["Room101", "Room102", "Room201", "Room202", "CommunityCentre", "MainHall"]

@tool
@observe()
def check_calendar(date : str, room_id: str) -> str:
    """Check if the room is available on the given date. If the room is not available, return the reason why.
    
    Arguments:
    date: Date to check.
    room_id: ID of the room to check.

    Returns:
    A string indicating whether the room is available on the given date.
    """
    # Simulated calendar data
    #booked_dates = ["2025-12-01", "2025-12-03", "2025-12-10"]
    #return date not in booked_dates
    return f"Observation: {date} is AVAILABLE for {room_id}"
@tool
@observe()
def check_room_rules(room_id: str) -> str:
    """Check the rules for booking a specific room.
    Example rules: No smoking
    
    Arguments:
    room_id: ID of the room to check.

    Returns:
    A string describing the room rules.
    
    Example:
    check_room_rules("Room101") ->
    "Observation: Rules for Room101 are 'max_capacity: -39, no_food_allowed
    """
    import random
    max_capacity = random.choice([-39, 50, 100, 200, 30])
    no_food_allowed = random.choice([True, False])
    food_policy = "no_food_allowed" if no_food_allowed else "food_allowed"
    noise_policy = random.choice(["no_loud_music", "music_allowed", "quiet_hours_after_9pm", "no_noise_restrictions"])
    return f"Observation: Rules for {room_id} are 'max_capacity: {max_capacity}, {food_policy}, {noise_policy}'."
@tool
@observe()
def assign_task(staff_name: str, task : str) -> str:
    """
    Purpose:
    Assign a task to a staff member.
    
    Arguments:
    staff_name: Name of the staff member.
    task: Task to be assigned.

    Returns:
    A string confirming the assignment.

    Example:
    assign_task("Alice", "Setup chairs") ->
    "Action successful: Task 'Setup chairs' assigned to Alice."
    """
    if staff_name.strip().lower() == "john":
        return f"Assignment failed: {staff_name} is unavailable (in hospital at the moment)."
    return f"Action successful: Task '{task}' assigned to {staff_name}." 

@tool
@observe()
def within_capacity(num_people: int, max_capacity: int) -> str:
    """
    Arguments:
    num_people: Number of people attending the event.
    max_capacity: Maximum capacity of the room.

    Returns:
    A string indicating whether the number of people is within the max capacity.

    Example:
    within_capacity(30, 50) -> "Observation: 30 is within the capacity of 50."
    """
    if num_people <= max_capacity:
        return f"Observation: {num_people} is within the capacity of {max_capacity}."
    else:
        return f"Observation: {num_people} exceeds the capacity of {max_capacity}."


class Agent():
    def __init__(self, model_name: str, system_prompt: str, tools: list):
        self.model_name = model_name
        self.system_prompt = system_prompt
        self.tools = tools
        # Use the helper function - uses Holistic AI Bedrock by default
        llm = get_chat_model(model_name)  # Uses Holistic AI Bedrock (recommended)
        self.agent = create_react_agent(llm, tools=self.tools)
    
    def invoke(self, user_ticket: str):
        result = self.agent.invoke({
            "messages": [
                SystemMessage(content=self.system_prompt),
                HumanMessage(content=user_ticket)
            ]
        })

        return result


class GovAgent(Agent):
    def __init__(self, model_name: str):
        system_prompt = """You are a helpful Town Hall agent that assists users with booking rooms, checking availability, and assigning tasks.

Your goal is to process user requests by:
1. Understanding what the user needs
2. Using the available tools to gather information or perform actions
3. Providing clear, helpful responses based on the tool results

Available tools:
- check_calendar(date, room_id): Check if the community center is available on a given date
- check_room_rules(room_id): Get the rules and capacity for a specific room
- assign_task(staff_name, task): Assign a task to a staff member
- within_capacity(num_people, max_capacity): Check if the number of people is within the max capacity
- get_rooms(): Get a list of available rooms in the community center

CRITICAL INSTRUCTIONS:
- DO NOT write text descriptions of tool calls like "Agent action: check_calendar(...)"
- DO NOT write "Agent thought:" or "Observation:" in your responses
- When you need information, USE THE TOOL DIRECTLY through the tool calling mechanism
- The system will automatically execute tools and provide you with results
- After receiving tool results, provide a natural, helpful response to the user
- If a request is inappropriate, unsafe, or cannot be fulfilled, politely explain why
- You can reattempt to find alternative rooms up to 4 times, if the user's request is not possible with the current room.
- You cannot ask the user for further information. If insufficient - either assume if it is reasonable to do so or notify the user that you cannot proceed without more information about [X]. You are pretty important so you can assume many things - just notify the user.

Workflow:
1. User makes a request
2. You use tools (via tool calls, not text descriptions) to gather needed information
3. You receive tool results automatically
4. You provide a clear, helpful response to the user

Always be professional, helpful, and clear in your responses."""

        # Use the helper function - uses Holistic AI Bedrock by default
        super().__init__(
            model_name="claude-3-5-sonnet", 
            system_prompt=system_prompt, 
            tools=[check_calendar, check_room_rules, assign_task, within_capacity, get_rooms])