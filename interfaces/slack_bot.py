import os
import re
import pickle
import logging
from typing import List
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler
from langchain_core.messages import BaseMessage, HumanMessage

from agents.nodes import create_agent_graph
from prompt_builder.test_analysis import get_e2e_test_analysis_prompt
from config.settings import settings

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SlackBot:
    """Slack bot interface for the test analysis agent."""
    
    def __init__(self):
        self.app = create_agent_graph()
        self.slack_app = App(
            token=settings.slack_bot_token,
            signing_secret=settings.slack_signing_secret
        )
        
        # Register event handlers
        self._register_handlers()
    
    def _register_handlers(self):
        """Register Slack event handlers."""
        @self.slack_app.event("app_mention")
        def handle_app_mention(event, say, client):
            """Handle app mention events."""
            logger.info(f"Received app mention in channel {event['channel']}")
            thread_ts = event.get('thread_ts') or event.get('ts')
            
            try:
                conversation_dir = os.getenv('CONVERSATION_DATA_DIR', '')
                pickle_file = f"{conversation_dir}conversation_{thread_ts}.pkl"
                
                # Ignore bot messages and messages without text
                if event.get('subtype') == 'bot_message' or 'text' not in event:
                    logger.info("Ignoring bot message or message without text")
                    return
                
                logger.info(f"Received app mention in channel: \n {event}")
                
                # Load or initialize conversation history
                conversation_history_messages = (
                    pickle.load(open(pickle_file, 'rb')) 
                    if os.path.exists(pickle_file) 
                    else []
                )
                
                is_first_turn = len(conversation_history_messages) == 0
                
                if is_first_turn:
                    # Extract prow link from message
                    pattern = r'https://prow\.ci\.openshift\.org/view/gs/test-platform-results/(logs/[^|>\s/]+(?:/[^|>\s/]+)*)'
                    match = re.search(pattern, event['text'])
                    if match:
                        base_dir = match.group(1)
                    else:
                        say(
                            text="No prow link found",
                            thread_ts=thread_ts
                        )
                        return
                    
                    user_input_text = get_e2e_test_analysis_prompt(base_dir=base_dir)
                else:
                    user_input_text = event['text']

                # Add user message to history
                current_user_message = HumanMessage(content=user_input_text)
                conversation_history_messages.append(current_user_message)
                
                inputs = {"messages": conversation_history_messages}

                # Process with agent
                result = self.app.invoke(inputs,config={"recursion_limit": 50})
                conversation_history_messages = result["messages"]
                
                # Send response
                say(
                    text=f"{conversation_history_messages[-1].content}",
                    thread_ts=thread_ts
                )

                # Save conversation history
                with open(pickle_file, 'wb') as f:
                    pickle.dump(conversation_history_messages, f)
                logger.info(f"Conversation history saved to {pickle_file}")
                
                logger.info(f"Response sent successfully to channel {event['channel']}")
                
            except Exception as e:
                logger.error(f"Error handling app mention: {e}")
                say(
                    text="Something went wrong, please try again later",
                    thread_ts=thread_ts
                )
        
    def start_http_mode(self):
        logger.info("Starting app in HTTP Mode...")
        self.slack_app.start(port=settings.port)

if __name__ == "__main__":
    bot = SlackBot()
    bot.start_http_mode()