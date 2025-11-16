from langchain_core.messages import HumanMessage, AIMessage, ToolMessage
from backend.trace_to_graph import print_message_summary
from backend.detect_culprit import find_issue_origin
from backend.llm_utils import GovAgent, Agent
import json


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
    
example_output_with_culprits = {
    'messages': [
        HumanMessage(
            content='\nYou are a helpful Town Hall agent. Your goal is to process requests by thinking step-by-step and using the available tools. You must use the check_calendar, check_room_rules, assign_task, and final_answer tools. You will follow this pattern:\n\nHuman: [The user\'s request]\nAgent thought: [Your reasoning and plan]\nAgent action: [The tool you will use]\nObservation: [The result from the tool]\n... (repeat thought/action/observation) ...\nAgent thought: [Your final reasoning]\nAgent action: final_answer("[Your response to the human]")\n\n---\nHere are some examples:\n---\n\nHuman: I need to book the community center for a 20-person meeting on Dec 5th.\nAgent thought: The user wants to book \'community_center\' on \'Dec 5th\' for 20 people. First, I must check if the room is available on that date.\nAgent action: check_calendar(date="2025-12-05")\nObservation: The calendar shows this date is AVAILABLE.\nAgent thought: The date is available. Now I need to check the rules for the \'community_center\' to ensure a 20-person meeting is allowed.\nAgent action: check_room_rules(room_id="community_center")\nObservation: Rules for community_center are \'max_capacity: 50, no_food_allowed\'.\nAgent thought: The 20-person meeting is within the 50-person capacity. The request is valid. I can now book it and inform the user of the \'no_food_allowed\' rule.\nAgent action: final_answer("Booking confirmed for the community center on Dec 5th. Please note: no food is allowed.")\n\n---\nHuman: Please assign the \'Setup chairs\' ticket to Bob.\nAgent thought: I need to assign the task \'Setup chairs\' to \'Bob\'. I must use the assign_task tool.\nAgent action: assign_task(staff_name="Bob", task="Setup chairs")\nObservation: Action was not successful. Reason: \'Bob\' is marked as \'On-Leave\'.\nAgent thought: I cannot assign the task to Bob because he is on leave. This is a failure[cite: 173]. I must inform the user that I cannot complete their request and state the reason.\nAgent action: final_answer("I\'m sorry, I cannot assign \'Setup chairs\' to Bob. My system shows he is \'On-Leave\'.")\nHuman: I would like to book the community center for a 30-person event on December 10th.', id='2aca527f-36ec-4d17-a6a7-8daa84f44a9c'
        ),
        AIMessage(
            content='',
            tool_calls=[{'name': 'check_calendar', 'args': {'date': '2023-12-10'}, 'id': 'toolu_bdrk_01726hSPHm9cVQ17LqHCqfPp', 'type': 'tool_call'}], id='lc_run--0482436b-58f9-49e4-9fa7-b5825c1a51dd-0'
        ),
        ToolMessage(
            content='Observation:2023-12-10 is AVAILABLE', id='9e2ab60c-da09-4f96-a6a1-fe0efebe7ba4', name='check_calendar', tool_call_id='toolu_bdrk_01726hSPHm9cVQ17LqHCqfPp'
        ),
        AIMessage(
            content='',
            tool_calls=[{'name': 'check_room_rules', 'args': {'room_id': 'community_center'}, 'id': 'toolu_bdrk_01LYBoqJQsxMGycuDsFSRuLZ', 'type': 'tool_call'}], id='lc_run--952a9fb0-8a9a-4544-8b33-f93c2d21a823-0'
        ),
        ToolMessage(
            content="Observation: Rules for community_center are 'max_capacity: 50, no_food_allowed'.", id='b2c5834c-6ff8-4d57-a912-73267d178425', name='check_room_rules', tool_call_id='toolu_bdrk_01LYBoqJQsxMGycuDsFSRuLZ'
        ),
        AIMessage(
            content='',
            tool_calls=[{'name': 'assign_task', 'args': {'staff_name': 'John', 'task': 'Prepare community center for December 10th event - 30 people'}, 'id': 'toolu_bdrk_01QrZTgBShYFdnVtJRQcqYqY', 'type': 'tool_call'}], id='lc_run--e177284f-30c5-4e8a-8700-e9f9e11556a9-0'
        ),
        # ⚠️ CULPRIT: confidence=0.90, explanation='This message shows the explicit assignment of staff member John to handle the e
        ToolMessage(
            content="Action successful: Task 'Prepare community center for December 10th event - 30 people' assigned to John.", id='8cba59a0-fb01-4c23-ae81-7200bc3b4ac3', name='assign_task', tool_call_id='toolu_bdrk_01QrZTgBShYFdnVtJRQcqYqY'
        ),
        # ⚠️ CULPRIT: confidence=1.00, explanation='This message directly shows John being assigned as staff for the event, explici
        AIMessage(
            content='',
            tool_calls=[{'name': 'final_answer', 'args': {'response': "Your booking for the community center on December 10th has been confirmed. The venue can accommodate your 30-person event as it's within our maximum capacity of 50 people. Please note that no food is allowed in the community center. I've assigned staff to prepare the venue for your event."}, 'id': 'toolu_bdrk_01DpnTN47Q2e45qptFzfhtgp', 'type': 'tool_call'}], id='lc_run--4974f8ea-df0f-44f4-a97e-9faf1150adb3-0'
        ),
        ToolMessage(
            content="Final Response to User: Your booking for the community center on December 10th has been confirmed. The venue can accommodate your 30-person event as it's within our maximum capacity of 50 people. Please note that no food is allowed in the community center. I've assigned staff to prepare the venue for your event.", id='754dab08-0270-4b95-91a2-e5e796dad0a1', name='final_answer', tool_call_id='toolu_bdrk_01DpnTN47Q2e45qptFzfhtgp'
        ),
        AIMessage(
            content="{'content': [], 'usage': {'input_tokens': 1781, 'output_tokens': 3, 'total_tokens': 1784}, 'metadata': {'team_id': 'team_the_great_hack_2025_046', 'model': 'us.anthropic.claude-3-5-sonnet-20241022-v2:0', 'cost_usd': 0.005388, 'latency_ms': 906.67, 'remaining_quota': {'requests_today': 35, 'tokens_today': 186752, 'llm_cost': 0.628632, 'gpu_cost': 0.0, 'total_cost': 0.628632, 'budget_limit': 50.0, 'remaining_budget': 49.371368, 'budget_usage_percent': 1.257264}}}", id='lc_run--ec5829ea-602c-4dbc-b855-3cdba4340b46-0'
        )
    ],
    'query': 'who did they choose as staff handling the event?',
    'culprits': [
        {
            'id': '8cba59a0-fb01-4c23-ae81-7200bc3b4ac3',
            'type': 'ToolMessage',
            'content': "Action successful: Task 'Prepare community center for December 10th event - 30 people' assigned to J",
            'confidence': 1.0,
            'explanation': 'This message directly shows John being assigned as staff for the event, explicitly answering who was chosen to handle it through the assign_task action.'
        },
        {
            'id': 'lc_run--e177284f-30c5-4e8a-8700-e9f9e11556a9-0',
            'type': 'AIMessage',
            'content': '',
            'confidence': 0.9,
            'explanation': 'This message shows the explicit assignment of staff member John to handle the event, making it the direct source for answering who was chosen as staff. The tool call clearly documents the staffing decision.'
        }
    ]
}

example_culprits = [
    (
        ToolMessage(
            content="Action successful: Task 'Prepare community center for December 10th event - 30 people' assigned to John.", 
            id='8cba59a0-fb01-4c23-ae81-7200bc3b4ac3', 
            name='assign_task', 
            tool_call_id='toolu_bdrk_01QrZTgBShYFdnVtJRQcqYqY'), 
        1.0, 
        'This message directly shows John being assigned as staff for the event, explicitly answering who was chosen to handle it through the assign_task action.'
    ),
    (
        AIMessage(
            content='',
            tool_calls=[{'name': 'assign_task', 'args': {'staff_name': 'John', 'task': 'Prepare community center for December 10th event - 30 people'}, 'id': 'toolu_bdrk_01QrZTgBShYFdnVtJRQcqYqY', 'type': 'tool_call'}], id='lc_run--e177284f-30c5-4e8a-8700-e9f9e11556a9-0'
        ),
        0.9, 
        'This message shows the explicit assignment of staff member John to handle the event, making it the direct source for answering who was chosen as staff. The tool call clearly documents the staffing decision.'
    ),
    
]
example_summary = {
        'total_messages_checked': 10,
        'culprits_found': 2,
        'confidence_threshold': 0.5,
        'culprit_message_ids': ['8cba59a0-fb01-4c23-ae81-7200bc3b4ac3', 'lc_run--e177284f-30c5-4e8a-8700-e9f9e11556a9-0']
    }

if __name__ == "__main__":
    import sys
    from backend.trace_to_graph import visualize_graph_html
    
    # Option 1: Use example output
    use_example = len(sys.argv) > 1 and sys.argv[1] == "--example"
    
    if use_example:
        print("=" * 80)
        print("Using example output")
        print("=" * 80)
        result = example_output
    else:
        # Run agent
        print("=" * 80)
        print("Running GovAgent...")
        print("=" * 80)
        model_name = "claude-3-5-sonnet"
        gov_agent = GovAgent(model_name)
        user_ticket = "I would like to book the community center for a 30-person event on December 10th."
        result = gov_agent.invoke(user_ticket)
    
    # Display action sequence
    print("\n" + "=" * 80)
    print("ACTION SEQUENCE")
    print("=" * 80 + "\n")
    for m in result['messages']:
        print_message_summary(m, highlight_culprit=False)
    
    # Analyze with critic
    print("\n" + "=" * 80)
    print("CRITIC ANALYSIS")
    print("=" * 80 + "\n")
    
    critic_system_prompt = "You are a helpful critic agent that analyzes agent execution traces."
    critic_agent = Agent("claude-3-5-sonnet", critic_system_prompt, [])
    query = "why did they choose this room"
    
    # Find issue origin (modifies result in place)
    if use_example:
        user_query = example_output_with_culprits['query']
        print(f"\nUsing example data with query: '{user_query}'...\n")
        result = example_output_with_culprits.copy()
        result['messages'] = example_output_with_culprits['messages'].copy()
        
        # Restore culprit metadata to messages from example_culprits
        culprits = example_culprits
        summary = example_summary
        
        # Create a mapping of message IDs to culprit data
        # First, use the culprits list from example_output_with_culprits (most reliable)
        culprit_map = {}
        if 'culprits' in example_output_with_culprits:
            for culprit_data in example_output_with_culprits['culprits']:
                culprit_id = culprit_data.get('id')
                if culprit_id:
                    culprit_map[culprit_id] = {
                        'is_culprit': True,
                        'confidence': culprit_data.get('confidence', 0.0),
                        'explanation': culprit_data.get('explanation', '')
                    }
        
        # Also add from example_culprits tuples (backup)
        for msg, confidence, explanation in culprits:
            msg_id = getattr(msg, 'id', None)
            if msg_id and msg_id not in culprit_map:
                culprit_map[msg_id] = {
                    'is_culprit': True,
                    'confidence': confidence,
                    'explanation': explanation
                }
        
        # Attach culprit metadata to messages by matching IDs
        matched_count = 0
        for msg in result['messages']:
            msg_id = getattr(msg, 'id', None)
            if msg_id and msg_id in culprit_map:
                # Found culprit - attach metadata
                msg._culprit_metadata = culprit_map[msg_id]
                matched_count += 1
            else:
                # Not a culprit - mark as such
                msg._culprit_metadata = {
                    'is_culprit': False,
                    'confidence': 0.0,
                    'explanation': ''
                }
        
        print(f"Restored culprit metadata: {matched_count} culprits matched out of {len(culprit_map)} in map")
        if matched_count == 0:
            print(f"Warning: No culprit IDs matched! Available IDs in map: {list(culprit_map.keys())}")
            print(f"Available message IDs: {[getattr(m, 'id', 'NO_ID') for m in result['messages']]}")
    else:
        # Allow user to input query
        user_query = input(f"\nEnter your critic query (or press Enter to use default: '{query}'): ").strip()
        if not user_query:
            user_query = query
        
        print(f"\nAnalyzing trace with query: '{user_query}'...\n")

        culprits, summary = find_issue_origin(
            result, 
            user_query, 
            llm_model=critic_agent,
            confidence_threshold=0.5
        )
    
    # Display summary
    print("\n" + "=" * 80)
    print("ANALYSIS SUMMARY")
    print("=" * 80)
    print(f"Total messages checked: {summary.get('total_messages_checked', 0)}")
    print(f"Culprits found: {summary.get('culprits_found', 0)}")
    print(f"Confidence threshold: {summary.get('confidence_threshold', 0.0):.2f}")
    
    # Display culprits
    if culprits:
        print("\n" + "=" * 80)
        print("CULPRIT MESSAGES")
        print("=" * 80 + "\n")
        for i, (msg, confidence, explanation) in enumerate(culprits, 1):
            print(f"{i}. [Confidence: {confidence:.2f}]")
            print(f"   Explanation: {explanation}")
            print_message_summary(msg, highlight_culprit=True)
            print()
    else:
        print("\nNo culprits found above the confidence threshold.")
    
    # Display action sequence with highlights
    print("\n" + "=" * 80)
    print("ACTION SEQUENCE (with culprit highlights)")
    print("=" * 80 + "\n")
    for m in result['messages']:
        print_message_summary(m, highlight_culprit=True)
    
    # # Print critic output as Python code for use as --example
    # print("\n" + "=" * 80)
    # print("CRITIC OUTPUT (for --example input)")
    # print("=" * 80 + "\n")
    # print("# Copy this output and paste it as example_output in main.py")
    # print("# Query used:", repr(user_query))
    # print("\nexample_output_with_culprits = {")
    # print("    'messages': [")
    
    # for i, msg in enumerate(result['messages']):
    #     # Get message type
    #     if isinstance(msg, HumanMessage):
    #         msg_type = "HumanMessage"
    #     elif isinstance(msg, AIMessage):
    #         msg_type = "AIMessage"
    #     elif isinstance(msg, ToolMessage):
    #         msg_type = "ToolMessage"
    #     else:
    #         msg_type = type(msg).__name__
        
    #     # Get content
    #     content = getattr(msg, 'content', '')
    #     content_repr = repr(content) if content else "''"
        
    #     # Get tool calls if present
    #     tool_calls = getattr(msg, 'tool_calls', [])
    #     tool_calls_str = ""
    #     if tool_calls:
    #         tool_calls_str = f",\n            tool_calls={repr(tool_calls)}"
        
    #     # Get other attributes
    #     msg_id = getattr(msg, 'id', '')
    #     id_str = f", id={repr(msg_id)}" if msg_id else ""
        
    #     name = getattr(msg, 'name', '')
    #     name_str = f", name={repr(name)}" if name else ""
        
    #     tool_call_id = getattr(msg, 'tool_call_id', '')
    #     tool_call_id_str = f", tool_call_id={repr(tool_call_id)}" if tool_call_id else ""
        
    #     additional_kwargs = getattr(msg, 'additional_kwargs', {})
    #     additional_kwargs_str = ""
    #     if additional_kwargs:
    #         additional_kwargs_str = f",\n            additional_kwargs={repr(additional_kwargs)}"
        
    #     response_metadata = getattr(msg, 'response_metadata', {})
    #     response_metadata_str = ""
    #     if response_metadata:
    #         response_metadata_str = f",\n            response_metadata={repr(response_metadata)}"
        
    #     # Get culprit metadata if present
    #     culprit_meta = ""
    #     if hasattr(msg, '_culprit_metadata'):
    #         meta = msg._culprit_metadata
    #         culprit_meta = f"\n        # Culprit metadata: is_culprit={meta.get('is_culprit')}, confidence={meta.get('confidence')}, explanation={repr(meta.get('explanation', ''))}"
        
    #     # Print message
    #     print(f"        {msg_type}(")
    #     print(f"            content={content_repr}{tool_calls_str}{additional_kwargs_str}{response_metadata_str}{id_str}{name_str}{tool_call_id_str}")
    #     print(f"        ){',' if i < len(result['messages']) - 1 else ''}{culprit_meta}")
    
    # print("    ],")
    # print("    'query': " + repr(user_query) + ",")
    # print("    'culprits': [")
    # for i, (msg, confidence, explanation) in enumerate(culprits):
    #     msg_id = getattr(msg, 'id', f'msg_{i}')
    #     msg_type = type(msg).__name__
    #     content = getattr(msg, 'content', '')[:100]
    #     print(f"        {{")
    #     print(f"            'id': {repr(msg_id)},")
    #     print(f"            'type': {repr(msg_type)},")
    #     print(f"            'content': {repr(content)},")
    #     print(f"            'confidence': {confidence},")
    #     print(f"            'explanation': {repr(explanation)}")
    #     print(f"        }}{',' if i < len(culprits) - 1 else ''}")
    # print("    ]")
    # print("}")
    # print("\n" + "=" * 80)
    
    # Generate graph visualization
    print("\n" + "=" * 80)
    print("GENERATING GRAPH VISUALIZATION")
    print("=" * 80 + "\n")
    
    try:
        culprit_ids = set(summary.get('culprit_message_ids', []))
        graph_path = visualize_graph_html(
            result,
            output_path="trace_analysis.html",
            culprit_ids=culprit_ids
        )
        print(f"Graph saved to: {graph_path}")
        print(f"Open in browser to view interactive visualization.")
    except Exception as e:
        print(f"Error generating graph: {e}")
        print("Make sure networkx and pyvis are installed: pip install networkx pyvis")
    
    # Option to start web server
    start_server = input("\nStart web server for interactive visualization? (y/n): ").strip().lower()
    if start_server == 'y':
        print("\nStarting web server on http://localhost:5000")
        print("Press Ctrl+C to stop the server\n")
        
        # Import and run Flask app
        from backend.app import app
        import json
        
        # Store trace in app's trace store
        import uuid
        trace_id = str(uuid.uuid4())
        app.config['current_trace'] = result
        app.config['current_trace_id'] = trace_id
        
        # Note: The frontend will need to load trace data via API
        # For now, we'll print instructions
        print(f"\nTo view the trace in the web interface:")
        print(f"1. Open http://localhost:5000 in your browser")
        print(f"2. The trace data is stored in the app")
        print(f"3. You can also POST to /api/analyze with the trace data\n")
        
        app.run(debug=True, port=5000, use_reloader=False)