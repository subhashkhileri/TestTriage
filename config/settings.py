import os
import getpass
from typing import Optional

class Settings:
    """Configuration settings for the test analysis agent."""
    
    # Model configurations
    GEMINI_MODEL_NAME: str = "gemini-2.0-flash"
    
    # Google Cloud Storage
    GCS_BUCKET_NAME: str = "test-platform-results"
    
    # API Keys
    @property
    def google_api_key(self) -> str:
        """Get Google API key from environment or prompt user."""
        if "GOOGLE_API_KEY" not in os.environ:
            os.environ["GOOGLE_API_KEY"] = getpass.getpass("Enter your Google AI API key: ")
        return os.environ["GOOGLE_API_KEY"]
    
    # Slack configuration
    @property
    def slack_bot_token(self) -> Optional[str]:
        """Get Slack bot token from environment."""
        return os.environ.get('SLACK_BOT_TOKEN')
    
    @property
    def slack_signing_secret(self) -> Optional[str]:
        """Get Slack signing secret from environment."""
        return os.environ.get('SLACK_SIGNING_SECRET')
    
    @property
    def slack_app_token(self) -> Optional[str]:
        """Get Slack app token from environment."""
        return os.environ.get("SLACK_APP_TOKEN")
    
    @property
    def port(self) -> int:
        """Get port for HTTP mode."""
        return int(os.environ.get('PORT', 3000))

# Global settings instance
settings = Settings() 