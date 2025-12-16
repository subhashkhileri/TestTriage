from typing import Annotated, Sequence, TypedDict
from langchain_core.messages import BaseMessage, HumanMessage
from langgraph.graph.message import add_messages
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_google_genai import ChatGoogleGenerativeAI
from config.settings import settings
from tools.test_analysis_tools import TOOLS


class AgentState(TypedDict):
    """State definition for the test analysis agent."""
    messages: Annotated[Sequence[BaseMessage], add_messages] 

# Initialize the model with tools
model = ChatGoogleGenerativeAI(
    model=settings.GEMINI_MODEL_NAME, 
    api_key=settings.google_api_key
)
llm_with_tools = model.bind_tools(TOOLS)

# Create tool node
tool_node = ToolNode(tools=TOOLS)

def model_call(state: AgentState) -> AgentState:
    """Main model call node that processes messages and generates responses."""
    current_messages = state["messages"]
    response = llm_with_tools.invoke(current_messages)
    return {"messages": [response]}

def slack_text_formatter(state: AgentState) -> AgentState:
    """Format the response text for Slack rich text formatting."""
    messages = state["messages"]
    last_message = messages[-1].content

    formatting_prompt = f"""You are a text formatter. Your ONLY job is to convert the provided text into Slack-compatible markdown format.

INSTRUCTIONS:
1. Keep all the content exactly as provided - do NOT summarize or change the meaning
2. Convert markdown to Slack's mrkdwn format:
   - Keep *bold* and _italic_ as-is
   - Keep `code blocks` as-is
   - Keep bullet points (• or -) as-is
   - Keep numbered lists as-is
   - Keep links in format: <url|text> or just <url>
3. Do NOT add any introductory text like "Here is..." or "The formatted text is..."
4. Do NOT add any explanations or comments
5. Return ONLY the formatted text, nothing else

TEXT TO FORMAT:
{last_message}

FORMATTED OUTPUT:"""

    current_user_message = HumanMessage(content=formatting_prompt)
    response = model.invoke([current_user_message])
    messages[-1].content = response.content
    return {"messages": messages}

def should_continue(state: AgentState) -> str:
    """Determine whether to continue with tool calls or end the conversation."""
    messages = state["messages"]
    last_message = messages[-1]
    if not last_message.tool_calls: 
        return "end"
    else:
        return "continue" 
    
def create_agent_graph():
    """Create and compile the agent graph."""
    graph = StateGraph(AgentState)
    
    # Add nodes
    graph.add_node("test_triage", model_call)
    graph.add_node("tools", tool_node)
    graph.add_node("slack_text_formatter", slack_text_formatter)
    
    # Set entry point
    graph.set_entry_point("test_triage")
    
    # Add conditional edges
    graph.add_conditional_edges(
        "test_triage",
        should_continue,
        {
            "continue": "tools",
            "end": "slack_text_formatter",
        },
    )
    
    # Add regular edges
    graph.add_edge("tools", "test_triage")
    graph.add_edge("slack_text_formatter", END)
    
    return graph.compile()

def save_graph_visualization(app, filename: str = "graph.png"):
    """Save the graph visualization as a PNG file."""
    try:
        image_data = app.get_graph().draw_mermaid_png()
        with open(filename, "wb") as f:
            f.write(image_data)
        print(f"Graph visualization saved to {filename}")
    except Exception as e:
        print(f"Error saving graph visualization: {e}") 