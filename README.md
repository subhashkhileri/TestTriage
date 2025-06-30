# TestTriage 🔍

An intelligent AI-powered test analysis agent that automatically analyzes Playwright test failures, provides root cause analysis, and integrates with your development workflow through CLI and Slack interfaces.

## 🌟 Features

- **AI-Powered Analysis**: Uses Google's Gemini AI to analyze test failures with contextual understanding
- **Visual Analysis**: Analyzes screenshots from failed tests to provide visual confirmation and insights
- **Multi-Interface Support**: 
  - Interactive CLI interface for direct analysis
  - Slack bot integration for team collaboration
- **Smart Integration**:
  - Google Cloud Storage for test artifacts
  - JIRA integration for bug tracking and management
  - JUnit XML parsing for comprehensive test result analysis
- **Production Ready**: Kubernetes deployment with Docker containerization
- **Extensible Architecture**: LangGraph-based agent workflow system

## 🚀 Coming Soon

- **PR Level Support**: Automated analysis and reporting at the pull request level for seamless CI/CD integration

## 🏗️ Architecture

TestTriage uses a sophisticated agent-based architecture built on LangGraph:

```
┌─────────────────┐    ┌──────────────────┐    ┌─────────────────┐
│   User Input    │───▶│   Test Triage    │───▶│   Tool Node     │
│  (CLI/Slack)    │    │     Agent        │    │  (Analysis)     │
└─────────────────┘    └──────────────────┘    └─────────────────┘
                              │                          │
                              ▼                          ▼
                    ┌──────────────────┐    ┌─────────────────┐
                    │ Slack Formatter  │    │   External      │
                    │     Node         │    │   Services      │
                    └──────────────────┘    │ • GCS Storage   │
                                           │ • JIRA API      │  
                                           │ • Gemini AI     │
                                           └─────────────────┘
```

### Core Components

- **Agent Nodes**: LangGraph-based workflow with conditional routing
- **Analysis Tools**: Comprehensive set of tools for test artifact analysis
- **Storage Layer**: Google Cloud Storage integration for test results
- **AI Models**: Support for multiple LLM providers (Google Gemini, Ollama, Mistral)

## 🚀 Quick Start

### Prerequisites

- Python 3.8+
- Google Cloud credentials (for storage and AI services)
- Optional: Slack app credentials (for bot functionality)
- Optional: JIRA credentials (for bug integration)

### Installation

1. **Clone the repository**:
   ```bash
   git clone <repository-url>
   cd TestTriage
   ```

2. **Set up virtual environment**:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. **Install dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure environment variables**:
   ```bash
   export GOOGLE_API_KEY="your-google-ai-api-key"
   # Optional: For Slack integration
   export SLACK_BOT_TOKEN="xoxb-your-slack-bot-token"
   export SLACK_SIGNING_SECRET="your-slack-signing-secret"
   export SLACK_APP_TOKEN="xapp-your-slack-app-token"
   ```

## 📖 Usage

### CLI Interface

Start the interactive CLI for direct test analysis:

```bash
python main.py cli
```

The CLI interface allows you to:
- Analyze specific test failure artifacts
- Get detailed root cause analysis
- Search for related JIRA issues
- View visual analysis of test screenshots

### Slack Bot

Launch the Slack bot for team-wide test analysis collaboration:

```bash
python main.py slack
```

The Slack bot provides:
- Team-wide access to test analysis
- Rich text formatting for analysis results
- Integration with your existing Slack workflows
- Automated notifications and reports

## 🛠️ Core Capabilities

### Test Analysis Tools

| Tool | Purpose | Description |
|------|---------|-------------|
| `get_failed_testsuites` | JUnit Analysis | Extracts failed test suites from JUnit XML files |
| `analyze_screenshot_visual_confirmation` | Visual Analysis | AI-powered analysis of test failure screenshots |
| `get_text_from_file` | Artifact Reading | Retrieves content from test artifacts and logs |
| `get_folder_structure` | Directory Analysis | Provides tree structure of test result directories |
| `get_immediate_log_files_content` | Log Analysis | Concatenates and analyzes log files from test runs |

### JIRA Integration Tools

| Tool | Purpose | Description |
|------|---------|-------------|
| `create_jira_bug` | Bug Creation | Creates new JIRA tickets with analysis results |
| `update_jira_bug` | Bug Updates | Updates existing JIRA tickets with new information |
| `search_jira_bugs` | Bug Discovery | Searches for related existing bugs using JQL queries |

### Analysis Process

TestTriage follows a systematic approach to test failure analysis:

1. **Artifact Collection**: Gathers JUnit XML, screenshots, logs, and build artifacts
2. **Failure Identification**: Parses test results to identify specific failures
3. **Visual Analysis**: Analyzes screenshots using AI for visual confirmation
4. **Root Cause Analysis**: Combines textual and visual information for comprehensive analysis
5. **JIRA Integration**: Searches for existing issues and creates/updates tickets as needed
6. **Reporting**: Provides structured analysis with actionable recommendations

## ⚙️ Configuration

### Environment Variables

| Variable | Required | Description | Default |
|----------|----------|-------------|---------|
| `GOOGLE_API_KEY` | Yes | Google AI API key for Gemini model | - |
| `SLACK_BOT_TOKEN` | Slack only | Slack bot OAuth token | - |
| `SLACK_SIGNING_SECRET` | Slack only | Slack app signing secret | - |
| `SLACK_APP_TOKEN` | Slack only | Slack app-level token | - |
| `PORT` | No | HTTP server port for Slack bot | 3000 |

### Model Configuration

The default configuration uses Google's Gemini 2.0 Flash model. You can modify model settings in `config/settings.py`:

```python
class Settings:
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash"
    GCS_BUCKET_NAME: str = "test-platform-results"
```

## 🐳 Deployment

### Docker

Build and run the Docker container:

```bash
# Build the image
docker build -t testtriage .

# Run the container
docker run -p 3000:3000 \
  -e GOOGLE_API_KEY="your-api-key" \
  -e SLACK_BOT_TOKEN="your-bot-token" \
  testtriage
```

### Kubernetes

Deploy to Kubernetes using the provided manifests:

1. **Create secrets**:
   ```bash
   # Copy and edit the secrets template
   cp k8s/secrets-template.yaml k8s/secrets.yaml
   # Edit k8s/secrets.yaml with your actual credentials
   kubectl apply -f k8s/secrets.yaml
   ```

2. **Deploy the application**:
   ```bash
   kubectl apply -f k8s/
   ```

3. **Automated deployment**:
   ```bash
   # Use the deployment script
   chmod +x k8s/deploy.sh
   ./k8s/deploy.sh
   ```

The Kubernetes setup includes:
- **Deployment**: Application pods with configurable replicas
- **Service**: Internal service discovery
- **Route**: External access configuration
- **Secrets**: Secure credential management

## 🔧 Development

### Project Structure

```
TestTriage/
├── agents/           # LangGraph agent definitions
│   └── nodes.py     # Agent workflow nodes
├── config/          # Configuration management
│   └── settings.py  # Application settings
├── interfaces/      # User interfaces
│   ├── cli.py       # Command-line interface
│   └── slack_bot.py # Slack bot implementation
├── tools/           # Analysis tools
│   └── test_analysis_tools.py # Test analysis capabilities
├── utils/           # Utility functions
│   └── storage.py   # Google Cloud Storage utilities
├── prompt_builder/         # AI prompt_builder and templates
│   └── test_analysis.py # Analysis prompt templates
├── k8s/             # Kubernetes deployment files
├── main.py          # Application entry point
└── requirements.txt # Python dependencies
```

### Adding New Tools

To extend TestTriage with new analysis capabilities:

1. **Create a new tool** in `tools/test_analysis_tools.py`:
   ```python
   @tool
   def your_new_tool(parameter: str):
       """Description of what your tool does.
       
       Args:
           parameter (str): Description of the parameter
           
       Returns:
           str: Description of the return value
       """
       # Your implementation here
       return result
   ```

2. **Add the tool to the TOOLS list** in the same file:
   ```python
   TOOLS = [
       # ... existing tools
       your_new_tool,
   ]
   ```

3. **Update the agent workflow** if needed in `agents/nodes.py`

### Testing

Run the application in development mode:

```bash
# CLI mode
python main.py cli

# Slack bot mode (requires Slack app setup)
python main.py slack
```

## 📚 Examples

### CLI Analysis Example

```bash
$ python main.py cli
Starting Test Analysis Agent - CLI Interface
> Analyze test failures in gs://test-platform-results/pr-logs/pull/123/test-run-456
```

### Slack Bot Example

After setting up the Slack bot, users can interact with it directly in Slack:

```
@TestTriage analyze test failures from build #456
```

The bot will provide structured analysis with:
- Test failure summaries
- Root cause analysis
- Visual screenshot analysis
- Related JIRA tickets
- Actionable recommendations

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature/amazing-feature`
3. Make your changes and add tests
4. Commit your changes: `git commit -m 'Add amazing feature'`
5. Push to the branch: `git push origin feature/amazing-feature`
6. Open a Pull Request

### Development Guidelines

- Follow Python PEP 8 style guidelines
- Add comprehensive docstrings to new functions and classes
- Include error handling and logging
- Test new features thoroughly
- Update documentation for new capabilities

## 🆘 Support

For support and questions:

1. **Documentation**: Check this README and inline code documentation
2. **Issues**: Open a GitHub issue for bugs and feature requests
3. **Discussions**: Use GitHub Discussions for questions and ideas

---

**Built with ❤️ for better test failure analysis and faster debugging cycles.** 