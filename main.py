#!/usr/bin/env python3

# Uncomment the next line if you want to prevent __pycache__ creation
import sys; sys.dont_write_bytecode = True

import sys
import argparse
from interfaces.cli import start_cli
from interfaces.slack_bot import SlackBot

def main():
    """Main entry point for the test analysis agent."""
    parser = argparse.ArgumentParser(
        description="Test Analysis Agent - Analyze Playwright test failures",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py cli          # Start CLI interface
  python main.py slack        # Start Slack bot
        """
    )
    
    parser.add_argument(
        'interface',
        choices=['cli', 'slack'],
        help='Interface to use (cli or slack)'
    )
    
    args = parser.parse_args()
    
    try:
        if args.interface == 'cli':
            print("Starting Test Analysis Agent - CLI Interface")
            start_cli()
        elif args.interface == 'slack':
            print("Starting Test Analysis Agent - Slack Bot")
            bot = SlackBot()
            bot.start_http_mode()
    except KeyboardInterrupt:
        print("\nShutting down gracefully...")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()