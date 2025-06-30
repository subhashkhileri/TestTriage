import os
from typing import List
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage
import re

from agents.nodes import create_agent_graph, save_graph_visualization
from prompt_builder.test_analysis import get_e2e_test_analysis_prompt

class CLIInterface:
    """Command Line Interface for the test analysis agent."""
    
    def __init__(self):
        self.app = create_agent_graph()
        self.conversation_history: List[BaseMessage] = []
        
        # Save graph visualization
        save_graph_visualization(self.app)
    
    def start_conversation(self):
        """Start an interactive conversation with the agent."""
        print("Starting chat with the AI test analysis expert. Type 'exit' to end.")
        
        is_first_turn = True
        try:
            while True:
                if is_first_turn:
                    pattern = r'https://prow\.ci\.openshift\.org/view/gs/test-platform-results/(logs/[^|>\s/]+(?:/[^|>\s/]+)*)'
                    match = re.search(pattern, input("Enter the prow link: "))
                    if match:
                        base_dir = match.group(1)
                    else:
                        print("No prow link found")
                        return
                    user_input_text = get_e2e_test_analysis_prompt(
                        base_dir=base_dir
                    )
                    # Display a truncated version for console
                    print(f"\nYOU (Initial Setup & Query): {user_input_text.splitlines()[1][:100]}...")
                    is_first_turn = False
                else:
                    user_input_text = input("\nYOU: ")
                    if user_input_text.lower() == "exit":
                        print("Exiting chat.")
                        break

                # Add user message to history
                current_user_message = HumanMessage(content=user_input_text)
                self.conversation_history.append(current_user_message)
                
                inputs = {"messages": self.conversation_history}
                
                print("\nAI: ", end="", flush=True)
                
                full_response_content = ""
                tool_calls_made = []

                # Stream the response
                for event in self.app.stream(inputs, stream_mode="values",config={"recursion_limit": 50}):
                    messages_from_event = event["messages"]
                    latest_message = messages_from_event[-1]

                    if isinstance(latest_message, AIMessage):
                        if latest_message.content:
                            if isinstance(latest_message.content, str) and latest_message.content not in full_response_content:
                                new_content = latest_message.content.replace(full_response_content, "", 1)
                                print(new_content, end="", flush=True)
                                full_response_content += new_content

                        if latest_message.tool_calls:
                            tool_calls_made = latest_message.tool_calls

                    # Update conversation history
                    self.conversation_history = messages_from_event

                print()  # Newline after AI response

                # Handle cases where no textual output was produced
                final_ai_message_for_turn = self.conversation_history[-1]
                if isinstance(final_ai_message_for_turn, AIMessage):
                    if not final_ai_message_for_turn.content and not tool_calls_made:
                        if not full_response_content:
                            print("(AI produced no textual output for this turn.)")
                    elif tool_calls_made and not final_ai_message_for_turn.content:
                        if not full_response_content:
                            print(f"(AI initiated tool calls: {[tc['name'] for tc in tool_calls_made]})")

            # Save conversation log
            self._save_conversation_log()
        except Exception as e:
            print(f"Error: {e}")
            self._save_conversation_log()
            return

    def _save_conversation_log(self):
        """Save the full conversation to a log file."""
        if self.conversation_history:
            with open("full_conversation_log.txt", "w") as f:
                f.write("--- Full Conversation History ---\n")
                for i, msg in enumerate(self.conversation_history):
                    f.write(f"--- Message {i}: {type(msg).__name__} ---\n")
                    if hasattr(msg, 'content') and msg.content is not None:
                        f.write(f"Content: {msg.content}\n")
                    
                    if isinstance(msg, AIMessage) and msg.tool_calls:
                        f.write(f"Tool Calls: {msg.tool_calls}\n")
                    
                    if isinstance(msg, ToolMessage):
                        f.write(f"Tool Call ID: {msg.tool_call_id}\n")
                        if hasattr(msg, 'name') and msg.name:
                            f.write(f"Tool Name: {msg.name}\n")
                    f.write("\n")
            print("\nFull conversation saved to full_conversation_log.txt")
        else:
            print("\nNo conversation to save.")

def start_cli():
    """Entry point for CLI interface."""
    cli = CLIInterface()
    cli.start_conversation() 