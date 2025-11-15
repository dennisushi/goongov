from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from backend.trace_to_graph import print_message_summary
from backend.detect_culprit import find_issue_origin

example_output = {
    'messages': [
        HumanMessage(
            content='\nYou are a helpful Town Hall agent. Your goal is to process requests by thinking step-by-step and using the available tools. You must use the check_calendar, check_room_rules, assign_task, and final_answer tools. You will follow this pattern:\n\nHuman: [The user\'s request]\nAgent thought: [Your reasoning and plan]\nAgent action: [The tool you will use]\nObservation: [The result from the tool]\n... (repeat thought/action/observation) ...\nAgent thought: [Your final reasoning]\nAgent action: final_answer("[Your response to the human]")\n\n---\nHere are some examples:\n---\n\nHuman: I need to book the community center for a 20-person meeting on Dec 5th.\nAgent thought: The user wants to book \'community_center\' on \'Dec 5th\' for 20 people. First, I must check if the room is available on that date.\nAgent action: check_calendar(date="2025-12-05")\nObservation: The calendar shows this date is AVAILABLE.\nAgent thought: The date is available. Now I need to check the rules for the \'community_center\' to ensure a 20-person meeting is allowed.\nAgent action: check_room_rules(room_id="community_center")\nObservation: Rules for community_center are \'max_capacity: 50, no_food_allowed\'.\nAgent thought: The 20-person meeting is within the 50-person capacity. The request is valid. I can now book it and inform the user of the \'no_food_allowed\' rule.\nAgent action: final_answer("Booking confirmed for the community center on Dec 5th. Please note: no food is allowed.")\n\n---\nHuman: Please assign the \'Setup chairs\' ticket to Bob.\nAgent thought: I need to assign the task \'Setup chairs\' to \'Bob\'. I must use the assign_task tool.\nAgent action: assign_task(staff_name="Bob", task="Setup chairs")\nObservation: Action was not successful. Reason: \'Bob\' is marked as \'On-Leave\'.\nAgent thought: I cannot assign the task to Bob because he is on leave. This is a failure[cite: 173]. I must inform the user that I cannot complete their request and state the reason.\nAgent action: final_answer("I\'m sorry, I cannot assign \'Setup chairs\' to Bob. My system shows he is \'On-Leave\'.")\nHuman: I would like to book the community center for a 30-person event on December 10th.', 
            additional_kwargs={}, response_metadata={}, id='2aca527f-36ec-4d17-a6a7-8daa84f44a9c'), 
        AIMessage(content='', additional_kwargs={}, response_metadata={}, 
            id='lc_run--0482436b-58f9-49e4-9fa7-b5825c1a51dd-0', 
            tool_calls=[{'name': 'check_calendar', 'args': {'date': '2023-12-10'}, 
            'id': 'toolu_bdrk_01726hSPHm9cVQ17LqHCqfPp', 'type': 'tool_call'}]), 
        ToolMessage(content='Observation:2023-12-10 is AVAILABLE', name='check_calendar', 
                    id='9e2ab60c-da09-4f96-a6a1-fe0efebe7ba4', tool_call_id='toolu_bdrk_01726hSPHm9cVQ17LqHCqfPp'), 
        AIMessage(content='', additional_kwargs={}, response_metadata={}, 
            id='lc_run--952a9fb0-8a9a-4544-8b33-f93c2d21a823-0', 
            tool_calls=[{'name': 'check_room_rules', 'args': {'room_id': 'community_center'}, 
                        'id': 'toolu_bdrk_01LYBoqJQsxMGycuDsFSRuLZ', 'type': 'tool_call'}]), 
        ToolMessage(content="Observation: Rules for community_center are 'max_capacity: 50, no_food_allowed'.", 
                    name='check_room_rules', id='b2c5834c-6ff8-4d57-a912-73267d178425', 
                    tool_call_id='toolu_bdrk_01LYBoqJQsxMGycuDsFSRuLZ'), 
        AIMessage(content='', additional_kwargs={}, response_metadata={}, 
                    id='lc_run--e177284f-30c5-4e8a-8700-e9f9e11556a9-0', 
                    tool_calls=[{'name': 'assign_task', 'args': {'staff_name': 'John', 'task': 'Prepare community center for December 10th event - 30 people'}, 
                    'id': 'toolu_bdrk_01QrZTgBShYFdnVtJRQcqYqY', 'type': 'tool_call'}]), 
        ToolMessage(
            content="Action successful: Task 'Prepare community center for December 10th event - 30 people' assigned to John.", name='assign_task', id='8cba59a0-fb01-4c23-ae81-7200bc3b4ac3', tool_call_id='toolu_bdrk_01QrZTgBShYFdnVtJRQcqYqY'), 
        AIMessage(content='', additional_kwargs={}, response_metadata={}, 
            id='lc_run--4974f8ea-df0f-44f4-a97e-9faf1150adb3-0', 
            tool_calls=[{'name': 'final_answer', 'args': {'response': "Your booking for the community center on December 10th has been confirmed. The venue can accommodate your 30-person event as it's within our maximum capacity of 50 people. Please note that no food is allowed in the community center. I've assigned staff to prepare the venue for your event."}, 'id': 'toolu_bdrk_01DpnTN47Q2e45qptFzfhtgp', 'type': 'tool_call'}]), 
        ToolMessage(content="Final Response to User: Your booking for the community center on December 10th has been confirmed. The venue can accommodate your 30-person event as it's within our maximum capacity of 50 people. Please note that no food is allowed in the community center. I've assigned staff to prepare the venue for your event.", 
            name='final_answer', 
            id='754dab08-0270-4b95-91a2-e5e796dad0a1', 
            tool_call_id='toolu_bdrk_01DpnTN47Q2e45qptFzfhtgp'), 
        AIMessage(
            content="{'content': [], 'usage': {'input_tokens': 1781, 'output_tokens': 3, 'total_tokens': 1784}, 'metadata': {'team_id': 'team_the_great_hack_2025_046', 'model': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0', 'cost_usd': 0.005388, 'latency_ms': 906.67, 'remaining_quota': {'requests_today': 35, 'tokens_today': 186752, 'llm_cost': 0.628632, 'gpu_cost': 0.0, 'total_cost': 0.628632, 'budget_limit': 50.0, 'remaining_budget': 49.371368, 'budget_usage_percent': 1.257264}}}", 
            additional_kwargs={}, 
            response_metadata={}, 
            id='lc_run--ec5829ea-602c-4dbc-b855-3cdba4340b46-0')
        ], 
    # 'structured_response': TechAnalysis(
    #     thought="I'll format this API response data as a structured JSON object. The data contains usage statistics, metadata about the team, model, costs, latency, and quota information. I'll present it in a properly indented, readable JSON format.", 
    #     action='{\n  "content": [],\n  "usage": {\n    "input_tokens": 1781,\n    "output_tokens": 3,\n    "total_tokens": 1784\n  },\n  "metadata": {\n    "team_id": "team_the_great_hack_2025_046",\n    "model": "us.anthropic.claude-3-5-sonnet-20241022-v2:0",\n    "cost_usd": 0.005388,\n    "latency_ms": 906.67,\n    "remaining_quota": {\n      "requests_today": 35,\n      "tokens_today": 186752,\n      "llm_cost": 0.628632,\n      "gpu_cost": 0.0,\n      "total_cost": 0.628632,\n      "budget_limit": 50.0,\n      "remaining_budget": 49.371368,\n      "budget_usage_percent": 1.257264\n    }\n  }\n}')
    }
    
if __name__ == "__main__":
    for m in example_output['messages']:
        print_message_summary(m)

    llm = get_chat_model("gpt-4")
    find_issue_origin(example_output, "why did they choose this room", 
                        llm_model=llm)