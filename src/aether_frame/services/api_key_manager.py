"""API Key Manager for dynamic key retrieval from database."""

import asyncio
import logging
from typing import Dict, Optional, Any
import asyncpg
from datetime import datetime

from ..config.settings import Settings

logger = logging.getLogger(__name__)


class APIKeyManager:
    """Manages API keys by fetching them from database periodically."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self._api_keys: Dict[str, str] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._connection_pool: Optional[asyncpg.Pool] = None

        # SQL queries for different providers (to be customized)
        self._queries = {
            "azure_openai": "",  # TODO: Add your SQL query here
            # Add more providers as needed
            # "openai": "",
            # "anthropic": "",
        }

    async def start(self):
        """Start the API key manager."""
        if self._running:
            logger.warning("API key manager is already running")
            return

        if not self.settings.enable_api_key_manager:
            logger.info("API key manager is disabled")
            return

        logger.info("Starting API key manager...")

        try:
            # Create database connection pool using existing PostgreSQL settings
            self._connection_pool = await asyncpg.create_pool(
                host=self.settings.postgres_host,
                port=self.settings.postgres_port,
                user=self.settings.postgres_user,
                password=self.settings.postgres_password,
                database=self.settings.postgres_database,
                min_size=1,
                max_size=5
            )

            self._running = True
            self._task = asyncio.create_task(self._refresh_loop())
            logger.info("API key manager started successfully")

        except Exception as e:
            logger.error(f"Failed to start API key manager: {e}")
            raise

    async def stop(self):
        """Stop the API key manager."""
        if not self._running:
            return

        logger.info("Stopping API key manager...")
        self._running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        if self._connection_pool:
            await self._connection_pool.close()

        logger.info("API key manager stopped")

    async def _refresh_loop(self):
        """Main refresh loop that runs every interval."""
        while self._running:
            try:
                await self._refresh_keys()
                await asyncio.sleep(self.settings.api_key_refresh_interval)
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in API key refresh loop: {e}")
                await asyncio.sleep(self.settings.api_key_refresh_interval)

    async def _refresh_keys(self):
        """Refresh API keys from database."""
        if not self._connection_pool:
            logger.error("Database connection pool not available")
            return

        logger.debug("Refreshing API keys from database...")

        try:
            async with self._connection_pool.acquire() as conn:
                for provider, query in self._queries.items():
                    if not query.strip():
                        logger.debug(
                            f"No query configured for provider: {provider}")
                        continue

                    try:
                        result = await conn.fetchval(query)
                        if result:
                            self._api_keys[provider] = result
                            logger.debug(
                                f"Updated API key for provider: {provider}")
                        else:
                            logger.warning(
                                f"No API key found for provider: {provider}")
                    except Exception as e:
                        logger.error(
                            f"Failed to fetch API key for {provider}: {e}")

            logger.debug(
                f"API key refresh completed. Active keys: {list(self._api_keys.keys())}")

        except Exception as e:
            logger.error(f"Failed to refresh API keys: {e}")

    def get_api_key(self, provider: str) -> Optional[str]:
        """Get API key for a specific provider."""
        return self._api_keys.get(provider)

    def get_azure_api_key(self) -> Optional[str]:
        """Get Azure OpenAI API key."""
        return self.get_api_key("azure_openai")

    def get_openai_api_key(self) -> Optional[str]:
        """Get OpenAI API key."""
        return self.get_api_key("openai")

    def get_anthropic_api_key(self) -> Optional[str]:
        """Get Anthropic API key."""
        return self.get_api_key("anthropic")

    def set_query(self, provider: str, query: str):
        """Set SQL query for a provider."""
        self._queries[provider] = query
        logger.info(f"Updated query for provider: {provider}")

    def get_all_keys(self) -> Dict[str, str]:
        """Get all available API keys."""
        return self._api_keys.copy()

    @property
    def is_running(self) -> bool:
        """Check if the manager is running."""
        return self._running


# Global instance
_api_key_manager: Optional[APIKeyManager] = None


def get_api_key_manager() -> Optional[APIKeyManager]:
    """Get the global API key manager instance."""
    return _api_key_manager


def initialize_api_key_manager(settings: Settings) -> APIKeyManager:
    """Initialize the global API key manager."""
    global _api_key_manager
    _api_key_manager = APIKeyManager(settings)
    return _api_key_manager
