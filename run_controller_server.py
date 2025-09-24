#!/usr/bin/env python3
"""
Convenience script to run the Aether Frame Controller API server.

Usage:
    python run_controller_server.py                    # Default settings
    python run_controller_server.py --port 8080        # Custom port
    python run_controller_server.py --reload           # Development mode
"""

import sys
import os

# Add src to path FIRST
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

# Now import after path is set
from aether_frame.controller.server import run_server


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Aether Frame Controller API Server")
    parser.add_argument("--host", default="0.0.0.0",
                        help="Host to bind to (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000,
                        help="Port to bind to (default: 8000)")
    parser.add_argument("--reload", action="store_true",
                        help="Enable auto-reload for development")
    parser.add_argument("--log-level", default="info",
                        help="Log level (default: info)")
    parser.add_argument("--env-file", help="Path to environment file")

    args = parser.parse_args()

    print("🚀 Starting Aether Frame Controller API Server")
    print("=" * 50)
    print(f"Host: {args.host}")
    print(f"Port: {args.port}")
    print(f"Reload: {args.reload}")
    print(f"Log Level: {args.log_level}")
    if args.env_file:
        print(f"Env File: {args.env_file}")
    print("=" * 50)
    print()
    print("📋 Available endpoints:")
    print(f"  Health Check: http://{args.host}:{args.port}/api/v1/health")
    print(f"  Chat API:     http://{args.host}:{args.port}/api/v1/chat")
    print(f"  Process API:  http://{args.host}:{args.port}/api/v1/process")
    print(f"  API Docs:     http://{args.host}:{args.port}/docs")
    print()

    try:
        run_server(
            host=args.host,
            port=args.port,
            reload=args.reload,
            log_level=args.log_level,
            env_file=args.env_file
        )
    except KeyboardInterrupt:
        print("\n🛑 Server stopped by user")
    except Exception as e:
        print(f"\n💥 Server failed to start: {e}")
        sys.exit(1)
