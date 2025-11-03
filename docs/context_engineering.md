# Context Engineering: Implementing a Custom ADK SessionService

This guide walks through building a bespoke SessionService for the ADK runtime. It covers the mandatory interface, optional extension points, recommended helper routines, and real backend examples so the service can be production-ready.

## 1. Interface Overview

### 1.1 BaseSessionService inheritance diagram

```python
from google.adk.sessions import BaseSessionService
from typing import Optional, List
from abc import ABC, abstractmethod

class BaseSessionService(ABC):
    """Abstract base class for ADK SessionService implementations."""

    # === Required abstract methods ===
    @abstractmethod
    async def create_session(*, app_name, user_id, state=None, session_id=None):
        ...

    @abstractmethod
    async def get_session(*, app_name, user_id, session_id, config=None):
        ...

    @abstractmethod
    async def delete_session(*, app_name, user_id, session_id):
        ...

    @abstractmethod
    async def list_sessions(*, app_name, user_id):
        ...

    @abstractmethod
    async def list_events(*, app_name, user_id, session_id):
        ...

    # === Optional overrides with default implementations ===
    async def append_event(session, event):
        ...  # Base implementation pushes into session.events

    async def close_session(*, session):
        ...  # Base implementation is a no-op
```

## 2. Required Interface Surface

### 2.1 Core lifecycle methods

| Method | Parameters | Return Value | Invocation | Notes |
|--------|------------|--------------|------------|-------|
| `create_session` | app_name, user_id, state?, session_id? | `Session` | Runner initialises a new session | Generate an ID when `session_id` is empty. |
| `get_session` | app_name, user_id, session_id, config? | `Optional[Session]` | Runner resumes a session | Return `None` when the session does not exist. |
| `delete_session` | app_name, user_id, session_id | `None` | Application performs cleanup | Remove the session and all associated data. |
| `list_sessions` | app_name, user_id | `ListSessionsResponse` | Management UI lists sessions | Provide every session for the given user/application. |
| `list_events` | app_name, user_id, session_id | `ListEventsResponse` | Full conversation history requested | Return the event stream for the session. |

### 2.2 Minimal implementation example

```python
class CustomSessionService(BaseSessionService):
    def __init__(self, storage_backend):
        self.storage = storage_backend

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        """Create a new session."""
        if session_id is None:
            session_id = self._generate_session_id()

        session = Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=state or {},
            events=[],
            last_update_time=time.time(),
        )

        await self._store_session(session)
        return session

    async def get_session(
        self, *, app_name: str, user_id: str, session_id: str, config=None
    ) -> Optional[Session]:
        """Fetch an existing session."""
        session_key = self._make_session_key(app_name, user_id, session_id)
        session_data = await self.storage.get(session_key)

        if session_data is None:
            return None

        return self._deserialize_session(session_data)

    async def delete_session(self, *, app_name: str, user_id: str, session_id: str):
        """Delete a session."""
        session_key = self._make_session_key(app_name, user_id, session_id)
        await self.storage.delete(session_key)

        await self._cleanup_related_state(app_name, user_id, session_id)

    async def list_sessions(self, *, app_name: str, user_id: str) -> ListSessionsResponse:
        """Enumerate every session for the given user."""
        pattern = self._make_session_pattern(app_name, user_id)
        session_keys = await self.storage.scan(pattern)

        sessions = []
        for key in session_keys:
            session_data = await self.storage.get(key)
            sessions.append(self._deserialize_session(session_data))

        return ListSessionsResponse(sessions=sessions)

    async def list_events(
        self, *, app_name: str, user_id: str, session_id: str
    ) -> ListEventsResponse:
        """Return the full event history."""
        session = await self.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )

        if session is None:
            return ListEventsResponse(events=[])

        return ListEventsResponse(events=session.events)
```

## 3. Optional Overrides

### 3.1 Event-handling improvements

| Method | Default Behaviour | Why Override? | Trigger |
|--------|-------------------|---------------|---------|
| `append_event` | Appends to `session.events` and applies the state delta | Persist events incrementally or introduce custom storage semantics | Every time the agent or a tool emits an event |
| `close_session` | No-op | Release resources, flush buffers, notify listeners | When a session ends gracefully |

```python
async def append_event(self, session: Session, event: Event) -> Event:
    """Optimised event ingestion."""
    if event.actions and event.actions.state_delta:
        await self._process_state_delta(session, event.actions.state_delta)

    session.events.append(event)
    session.last_update_time = time.time()

    await self._append_event_to_storage(session.id, event)
    return event

async def close_session(self, *, session: Session):
    """Cleanup hook when a session closes."""
    await self._clear_session_cache(session.id)
    await self._close_session_connections(session.id)
    await self._trigger_session_cleanup_callbacks(session)
```

## 4. Helper Routines

### 4.1 Storage helpers

| Helper | Used By | Purpose |
|--------|---------|---------|
| `_store_session` | `create_session`, `append_event` | Persist the session snapshot. |
| `_retrieve_session` | `get_session` | Fetch the session materialised view. |
| `_append_event_to_storage` | `append_event` | Incrementally persist new events (performance optimisation). |
| `_cleanup_related_state` | `delete_session` | Purge user/app level state tied to the session. |

### 4.2 State-management helpers

| Helper | Trigger | Purpose |
|--------|---------|---------|
| `_process_state_delta` | `append_event` | Apply state changes embedded in events. |
| `_update_user_state` | When handling `user:` prefix keys | Persist user-scoped state across sessions. |
| `_update_app_state` | When handling `app:` prefix keys | Maintain global application state. |
| `_handle_temp_state` | When handling `temp:` prefix keys | Manage in-memory-temporary state without persistence. |

```python
async def _process_state_delta(self, session: Session, state_delta: dict):
    """Core logic for mutating state based on event payloads."""
    for key, value in state_delta.items():
        if key.startswith("temp:"):
            continue  # In-memory only.
        elif key.startswith("user:"):
            await self._update_user_state(session.user_id, key, value)
        elif key.startswith("app:"):
            await self._update_app_state(session.app_name, key, value)
        else:
            session.state[key] = value
```

### 4.3 Lifecycle management helpers

| Helper | Trigger | Purpose |
|--------|---------|---------|
| `_cleanup_expired_sessions` | Scheduled job | Remove sessions that exceeded retention. |
| `_backup_session_data` | On schedule or before critical actions | Capture backups for recovery. |
| `_migrate_session_format` | During version upgrades | Transform session payloads to new schemas. |
| `_validate_session_integrity` | At startup or scheduled audits | Guard against corruption or missing fields. |

## 5. Reference Implementations

### 5.1 Redis-powered implementation

```python
import redis.asyncio as redis
import json
import time
from typing import Optional

class RedisSessionService(BaseSessionService):
    """SessionService backed by Redis."""

    def __init__(self, redis_url: str, ttl_seconds: int = 7 * 24 * 3600):
        self.redis = redis.from_url(redis_url)
        self.ttl_seconds = ttl_seconds
        asyncio.create_task(self._background_cleanup())

    async def create_session(
        self,
        *,
        app_name: str,
        user_id: str,
        state: Optional[dict] = None,
        session_id: Optional[str] = None,
    ) -> Session:
        session_id = session_id or f"sess_{uuid4().hex[:12]}"
        session = Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id,
            state=state or {},
            events=[],
            last_update_time=time.time(),
        )
        await self._store_session(session)
        return session

    async def append_event(self, session: Session, event: Event) -> Event:
        """Efficient event appends with Redis pipelines."""
        if event.actions and event.actions.state_delta:
            await self._process_state_delta(session, event.actions.state_delta)

        session.events.append(event)
        session.last_update_time = time.time()

        pipe = self.redis.pipeline()
        pipe.hset(
            f"session:{session.id}", "events", json.dumps([e.dict() for e in session.events])
        )
        pipe.hset(f"session:{session.id}", "state", json.dumps(session.state))
        pipe.hset(f"session:{session.id}", "last_update", session.last_update_time)
        pipe.expire(f"session:{session.id}", self.ttl_seconds)
        await pipe.execute()
        return event

    async def _store_session(self, session: Session):
        """Persist the session snapshot into Redis."""
        session_key = f"session:{session.id}"
        session_data = {
            "id": session.id,
            "app_name": session.app_name,
            "user_id": session.user_id,
            "state": json.dumps(session.state),
            "events": json.dumps([event.dict() for event in session.events]),
            "last_update": session.last_update_time,
        }

        pipe = self.redis.pipeline()
        pipe.hmset(session_key, session_data)
        pipe.expire(session_key, self.ttl_seconds)
        await pipe.execute()

    async def _background_cleanup(self):
        """Periodic cleanup of expired sessions."""
        while True:
            try:
                # Custom cleanup logic per deployment requirements
                await asyncio.sleep(3600)
            except Exception as exc:
                logger.error("Background cleanup error: %s", exc)
```

### 5.2 MongoDB implementation

```python
from motor.motor_asyncio import AsyncIOMotorClient

class MongoSessionService(BaseSessionService):
    """SessionService backed by MongoDB."""

    def __init__(self, mongo_url: str, db_name: str = "adk_sessions"):
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[db_name]
        self.sessions = self.db.sessions
        self.user_states = self.db.user_states
        self.app_states = self.db.app_states

        asyncio.create_task(self._create_indexes())

    async def _create_indexes(self):
        """Ensure indexes exist for query performance."""
        await self.sessions.create_index([("app_name", 1), ("user_id", 1)])
        await self.sessions.create_index([("last_update_time", 1)])
        await self.user_states.create_index([("user_id", 1)])
        await self.app_states.create_index([("app_name", 1)])

    async def _process_state_delta(self, session: Session, state_delta: dict):
        """State-processing strategy tuned for MongoDB."""
        session_updates = {}
        user_updates = {}
        app_updates = {}

        for key, value in state_delta.items():
            if key.startswith("temp:"):
                continue
            elif key.startswith("user:"):
                user_updates[key] = value
            elif key.startswith("app:"):
                app_updates[key] = value
            else:
                session.state[key] = value
                session_updates[f"state.{key}"] = value

        operations = []

        if session_updates:
            operations.append(
                UpdateOne(
                    {"_id": f"{session.app_name}:{session.user_id}:{session.id}"},
                    {"$set": session_updates},
                )
            )

        if user_updates:
            operations.append(
                UpdateOne(
                    {"user_id": session.user_id},
                    {"$set": user_updates},
                    upsert=True,
                )
            )

        if app_updates:
            operations.append(
                UpdateOne(
                    {"app_name": session.app_name},
                    {"$set": app_updates},
                    upsert=True,
                )
            )

        if operations:
            async with await self.client.start_session() as mongo_session:
                async with mongo_session.start_transaction():
                    for op in operations:
                        await self._execute_update_operation(op)
```

## 6. Best Practices

### 6.1 Performance

1. **Connection pooling** – size connection pools for expected concurrency.
2. **Batch operations** – use pipelines/bulk writes to reduce round trips.
3. **Index design** – add indexes for frequently queried keys.
4. **Caching** – cache hot sessions when appropriate.

### 6.2 Reliability

1. **Transactional guarantees** – wrap critical updates in transactions.
2. **Retry policies** – retry transient I/O failures with exponential backoff.
3. **Health checks** – monitor the backing store connectivity.
4. **Graceful degradation** – define fallback behaviour when storage is unavailable.

### 6.3 Observability & Maintenance

1. **Metrics** – collect latency and success rates for create/get/delete/list calls.
2. **Data hygiene** – schedule cleanup for expired sessions and orphaned state.
3. **Capacity planning** – track storage usage and plan ahead for growth.
4. **Schema compatibility** – keep data format changes backward compatible.

## 7. Summary

To deliver a production-grade SessionService:

1. Implement the five abstract CRUD/list methods.
2. Override `append_event` and `close_session` when performance or cleanup needs demand it.
3. Provide helper routines that match your storage engine, covering persistence, state management, and housekeeping.
4. Manage the end-to-end lifecycle: creation, steady-state usage, cleanup, and long-term retention.

With thoughtful interface coverage and careful optimisation, you can build a high-performance, highly reliable session layer for ADK workloads.
