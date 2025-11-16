import os
import time
import json
from pathlib import Path
from dotenv import load_dotenv
import langfuse
from langfuse import observe


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
from langchain_core.messages import HumanMessage
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
# os.environ["LANGSMITH_TRACING"] = "false"

@observe()
def check_calendar(date : str) -> str:
    """Check if the community center is available on the given date."""
    # Simulated calendar data
    #booked_dates = ["2025-12-01", "2025-12-03", "2025-12-10"]
    #return date not in booked_dates
    return f"Observation:{date} is AVAILABLE"

@observe()
def check_room_rules(room_id: str) -> str:
    """Check the rules for booking a specific room.
    Example rules: No smoking"""
    return f"Observation: Rules for {room_id} are 'max_capacity: 50, no_food_allowed'."

@observe()
def assign_task(staff_name: str, task : str) -> str:
    """Assign a task to a staff member."""
    return f"Action successful: Task '{task}' assigned to {staff_name}."



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
            "messages": [HumanMessage(content=self.system_prompt+user_ticket)]
        })

        return result


class GovAgent(Agent):
    def __init__(self, model_name: str):
        system_prompt = """
        You are a helpful Town Hall agent. Your goal is to process requests by thinking step-by-step and using the available tools. You must use the check_calendar, check_room_rules, assign_task, and final_answer tools. You will follow this pattern:

        Human: [The user's request]
        Agent thought: [Your reasoning and plan]
        Agent action: [The tool you will use]
        Observation: [The result from the tool]
        ... (repeat thought/action/observation) ...
        Agent thought: [Your final reasoning]
        Agent action: final_answer("[Your response to the human]")

        ---
        Here are some examples:
        ---

        Human: I need to book the community center for a 20-person meeting on Dec 5th.
        Agent thought: The user wants to book 'community_center' on 'Dec 5th' for 20 people. First, I must check if the room is available on that date.
        Agent action: check_calendar(date="2025-12-05")
        Observation: The calendar shows this date is AVAILABLE.
        Agent thought: The date is available. Now I need to check the rules for the 'community_center' to ensure a 20-person meeting is allowed.
        Agent action: check_room_rules(room_id="community_center")
        Observation: Rules for community_center are 'max_capacity: 50, no_food_allowed'.
        Agent thought: The 20-person meeting is within the 50-person capacity. The request is valid. I can now book it and inform the user of the 'no_food_allowed' rule.
        Agent action: final_answer("Booking confirmed for the community center on Dec 5th. Please note: no food is allowed.")

        ---
        Human: Please assign the 'Setup chairs' ticket to Bob.
        Agent thought: I need to assign the task 'Setup chairs' to 'Bob'. I must use the assign_task tool.
        Agent action: assign_task(staff_name="Bob", task="Setup chairs")
        Observation: Action was not successful. Reason: 'Bob' is marked as 'On-Leave'.
        Agent thought: I cannot assign the task to Bob because he is on leave. This is a failure[cite: 173]. I must inform the user that I cannot complete their request and state the reason.
        Agent action: final_answer("I'm sorry, I cannot assign 'Setup chairs' to Bob. My system shows he is 'On-Leave'.")
        """

        # Use the helper function - uses Holistic AI Bedrock by default
        super().__init__(
            model_name="claude-3-5-sonnet", 
            system_prompt=system_prompt, 
            tools=[check_calendar, check_room_rules, assign_task])