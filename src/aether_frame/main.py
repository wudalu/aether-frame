"""Main application entry point for Aether Frame."""

import asyncio
import logging
from typing import Optional

from aether_frame.config.settings import Settings
from aether_frame.execution.ai_assistant import AIAssistant


async def main() -> None:
    """Main application entry point."""
    # Load configuration
    settings = Settings()

    # Setup logging
    logging.basicConfig(
        level=getattr(logging, settings.log_level),
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Aether Frame v{settings.app_version}")

    # Initialize AI Assistant
    assistant = AIAssistant(settings)

    # Example usage
    task = {
        "description": "Example task for demonstration",
        "context": {"domain": "example"},
    }

    try:
        result = await assistant.process_request(task)
        logger.info(f"Task completed: {result}")
    except Exception as e:
        logger.error(f"Task failed: {e}")
        raise


def cli_main() -> None:
    """CLI entry point."""
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutdown requested by user")
    except Exception as e:
        print(f"Application failed: {e}")
        exit(1)


if __name__ == "__main__":
    cli_main()
