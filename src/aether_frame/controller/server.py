"""
Server startup script for the Aether Frame Controller API.

This module provides utilities to start the FastAPI server with proper configuration.
"""

import asyncio
import logging
import sys
import os
from typing import Optional

import uvicorn
from dotenv import load_dotenv

from ..config.settings import Settings
from .api_server import create_app


def setup_logging(log_level: str = "INFO") -> None:
    """Setup logging configuration for the server."""
    logging.basicConfig(
        level=getattr(logging, log_level.upper()),
        format='%(asctime)s | %(levelname)8s | %(name)s | %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )


def run_server(
    host: str = "0.0.0.0",
    port: int = 8000,
    reload: bool = False,
    log_level: str = "info",
    env_file: Optional[str] = None
) -> None:
    """
    Run the FastAPI server with uvicorn.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        reload: Enable auto-reload for development
        log_level: Logging level
        env_file: Path to environment file
    """
    # Load environment variables
    if env_file:
        load_dotenv(env_file)
    else:
        # Try to load common env files
        for env_path in [".env", ".env.local", ".env.production"]:
            if os.path.exists(env_path):
                load_dotenv(env_path)
                break

    # Setup logging
    setup_logging(log_level.upper())

    logger = logging.getLogger(__name__)
    logger.info(f"Starting Aether Frame Controller API server...")
    logger.info(f"Host: {host}")
    logger.info(f"Port: {port}")
    logger.info(f"Reload: {reload}")
    logger.info(f"Log level: {log_level}")

    if reload:
        # Development mode with reload - use import string
        uvicorn.run(
            "aether_frame.controller.api_server:create_app_factory",
            host=host,
            port=port,
            reload=reload,
            log_level=log_level,
            access_log=True,
            factory=True,  # Indicate that create_app_factory is a factory function
        )
    else:
        # Production mode - use app object directly (single process)
        settings = Settings()
        app = create_app(settings)

        uvicorn.run(
            app,
            host=host,
            port=port,
            reload=False,
            log_level=log_level,
            access_log=True,
            # Single process optimizations
            timeout_keep_alive=5,  # Keep-alive timeout
            limit_concurrency=1000,  # Limit concurrent connections
        )


async def run_server_async(
    host: str = "0.0.0.0",
    port: int = 8000,
    log_level: str = "info",
    env_file: Optional[str] = None
) -> None:
    """
    Run the FastAPI server asynchronously.

    This is useful for embedding the server in other async applications.

    Args:
        host: Host to bind the server to
        port: Port to bind the server to
        log_level: Logging level
        env_file: Path to environment file
    """
    # Load environment variables
    if env_file:
        load_dotenv(env_file)

    # Setup logging
    setup_logging(log_level.upper())

    # Create settings and app
    settings = Settings()
    app = create_app(settings)

    # Create server config
    config = uvicorn.Config(
        app,
        host=host,
        port=port,
        log_level=log_level,
        access_log=True
    )

    # Run server
    server = uvicorn.Server(config)
    await server.serve()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Aether Frame Controller API Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port to bind to")
    parser.add_argument("--reload", action="store_true",
                        help="Enable auto-reload")
    parser.add_argument("--log-level", default="info", help="Log level")
    parser.add_argument("--env-file", help="Path to environment file")

    args = parser.parse_args()

    try:
        run_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            env_file=args.env_file
        )
    except KeyboardInterrupt:
        print("\nServer stopped by user")
    except Exception as e:
        print(f"Server failed to start: {e}")
        sys.exit(1)
