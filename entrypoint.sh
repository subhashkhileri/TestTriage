#!/bin/bash
set -e

echo "Running Jira sync to ChromaDB..."
python jira_sync_to_chroma.py || {
    echo "Warning: Jira sync failed, but continuing to start Slack bot..."
}

echo "Starting Slack bot..."
exec python main.py slack
