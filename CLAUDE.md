# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

TestTriage is an AI-powered Playwright test failure analysis agent. It analyzes test artifacts from Google Cloud Storage (prow/gcsweb links), performs root cause analysis using Gemini AI with visual screenshot analysis, and integrates with JIRA for bug tracking.

## Commands

```bash
# Install dependencies
pip install -r requirements.txt

# Run CLI interface
python main.py cli

# Run Slack bot
python main.py slack
```

## Required Environment Variables

- `GOOGLE_API_KEY` - Google AI API key for Gemini model (required)
- `JIRA_PAT` - JIRA Personal Access Token for bug creation/search
- `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET` - For Slack bot mode

## Architecture

### LangGraph Agent Workflow

The system uses LangGraph to orchestrate an agent workflow defined in `agents/nodes.py`:

```
User Input → test_triage node → (conditional) → tools node → test_triage → ... → slack_text_formatter → END
```

- **test_triage node**: Main LLM call using Gemini with bound tools
- **tools node**: Executes tool calls (ToolNode from langgraph.prebuilt)
- **slack_text_formatter node**: Formats final response for Slack mrkdwn
- **Routing**: `should_continue()` checks for tool_calls to determine next step

### Key Data Flow

1. CLI/Slack extracts `base_dir` from prow/gcsweb URLs using regex patterns
2. `E2ETestAnalysisBuilder` in `prompt_builder/test_analysis.py` constructs a detailed analysis prompt by:
   - Finding e2e job directories in GCS artifacts
   - Locating playwright project directories and JUnit XML files
   - Building per-project analysis instructions
3. The prompt instructs the agent to use specific tools in sequence
4. Conversation history is maintained (in-memory for CLI, pickle files for Slack)

### Tool Implementation Pattern

Tools are defined in `tools/test_analysis_tools.py` using the `@tool` decorator from `langchain_core.tools`. All tools that access test artifacts use `storage_client` (from `utils/storage.py`) which wraps GCS anonymous client access.

Key tools:
- `get_failed_testsuites`: Parses JUnit XML for failures
- `analyze_screenshot_visual_confirmation`: Sends image + context to Gemini for visual analysis
- `search_similar_jira_issues`: ChromaDB semantic search using Google embeddings
- `create_jira_bug` / `update_jira_bug`: JIRA API integration

### Adding New Tools

1. Add function with `@tool` decorator in `tools/test_analysis_tools.py`
2. Append to the `TOOLS` list at the bottom of that file
3. Tools are automatically bound to the model via `model.bind_tools(TOOLS)` in `agents/nodes.py`

### GCS Path Convention

All artifact paths are relative to the `test-platform-results` bucket. The `base_dir` extracted from URLs follows the pattern:
- `logs/<job-name>/<job-id>` (periodic jobs)
- `pr-logs/pull/<repo>/<pr>/<job-name>/<job-id>` (PR jobs)

## ChromaDB for JIRA Search

The `search_similar_jira_issues` tool uses ChromaDB with Google's `text-embedding-004` model. The collection `jira_issues` stores RHDHBUGS issues. A separate sync script (`jira_sync_to_chroma.py`) populates the database.
