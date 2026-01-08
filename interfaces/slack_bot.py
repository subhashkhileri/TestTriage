import os
import re
import pickle
import logging
import threading
from typing import List
from concurrent.futures import ThreadPoolExecutor
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
            signing_secret=settings.slack_signing_secret,
            process_before_response=False  # Process events after responding to Slack
        )
        # Thread pool for handling events asynchronously
        self.executor = ThreadPoolExecutor(max_workers=10, thread_name_prefix="slack-handler")

        # Register event handlers
        self._register_handlers()
    
    def _process_mention(self, event, client):
        """Process app mention in background thread."""
        thread_ts = event.get('thread_ts') or event.get('ts')

        try:
            conversation_dir = os.getenv('CONVERSATION_DATA_DIR', '')
            pickle_file = f"{conversation_dir}conversation_{thread_ts}.pkl"

            logger.info(f"Processing app mention in channel: \n {event}")

            # Load or initialize conversation history
            conversation_history_messages = (
                pickle.load(open(pickle_file, 'rb'))
                if os.path.exists(pickle_file)
                else []
            )

            is_first_turn = len(conversation_history_messages) == 0

            if is_first_turn:
                # Extract prow or gcsweb link from message
                # Pattern for prow URLs
                prow_pattern = r'https://prow\.ci\.openshift\.org/view/gs/test-platform-results/((?:logs|pr-logs)/[^|>\s/]+(?:/[^|>\s/]+)*)'
                # Pattern for gcsweb URLs - extract base_dir up to job ID
                gcsweb_pattern = r'https://gcsweb-ci\.apps\.ci\.l2s4\.p1\.openshiftapps\.com/gcs/test-platform-results/((?:logs|pr-logs)(?:/[^/\s|>]+)*/\d+)'

                prow_match = re.search(prow_pattern, event['text'])
                gcsweb_match = re.search(gcsweb_pattern, event['text'])

                if prow_match:
                    base_dir = prow_match.group(1)
                elif gcsweb_match:
                    base_dir = gcsweb_match.group(1)
                    prow_link = f"https://prow.ci.openshift.org/view/gs/test-platform-results/{base_dir}"
                    logger.info(f"Constructed prow link from gcsweb: {prow_link}")
                else:
                    client.chat_postMessage(
                        channel=event['channel'],
                        text="No valid prow or gcsweb link found",
                        thread_ts=thread_ts,
                        unfurl_links=False,
                        unfurl_media=False
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
            result = self.app.invoke(inputs, config={"recursion_limit": 50})
            conversation_history_messages = result["messages"]

            # Send response
            response_text = conversation_history_messages[-1].content
            if not response_text or not response_text.strip():
                response_text = "No response generated"

            client.chat_postMessage(
                channel=event['channel'],
                text=response_text,
                thread_ts=thread_ts,
                unfurl_links=False,
                unfurl_media=False
            )

            # Save conversation history
            with open(pickle_file, 'wb') as f:
                pickle.dump(conversation_history_messages, f)
            logger.info(f"Conversation history saved to {pickle_file}")

            logger.info(f"Response sent successfully to channel {event['channel']}")

        except Exception as e:
            logger.error(f"Error processing app mention: {e}", exc_info=True)
            try:
                client.chat_postMessage(
                    channel=event['channel'],
                    text="Something went wrong, please try again later",
                    thread_ts=thread_ts,
                    unfurl_links=False,
                    unfurl_media=False
                )
            except Exception as send_error:
                logger.error(f"Failed to send error message: {send_error}")

    def _register_handlers(self):
        """Register Slack event handlers."""
        @self.slack_app.event("app_mention")
        def handle_app_mention(event, say, client):
            """Handle app mention events - acknowledges immediately and processes in background."""
            # Quick validation and immediate return
            if 'text' not in event:
                return

            # Submit to thread pool and return immediately
            self.executor.submit(self._process_mention, event, client)
            # Log after submission to minimize handler execution time
            logger.info(f"Queued app mention for processing: channel={event.get('channel')}, ts={event.get('ts')}")
        
    def start_http_mode(self):
        logger.info("Starting app in HTTP Mode...")
        try:
            self.slack_app.start(port=settings.port)
        finally:
            logger.info("Shutting down thread pool...")
            self.executor.shutdown(wait=True)

if __name__ == "__main__":
    bot = SlackBot()
    bot.start_http_mode()