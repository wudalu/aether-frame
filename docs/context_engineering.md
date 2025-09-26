# Context Engineering: ADK Custom SessionService Implementation Guide

本文档详细说明如何实现自定义的ADK SessionService，包括必须实现的接口、可选覆盖的方法，以及各种接口的使用时机。

## 1. 接口概览

### 1.1 BaseSessionService 继承结构

```python
from google.adk.sessions import BaseSessionService
from typing import Optional, List
from abc import ABC, abstractmethod

class BaseSessionService(ABC):
    """ADK SessionService 基础抽象类"""
    
    # === 必须实现的抽象方法 ===
    @abstractmethod
    async def create_session(*, app_name, user_id, state=None, session_id=None): pass
    
    @abstractmethod  
    async def get_session(*, app_name, user_id, session_id, config=None): pass
    
    @abstractmethod
    async def delete_session(*, app_name, user_id, session_id): pass
    
    @abstractmethod
    async def list_sessions(*, app_name, user_id): pass
    
    @abstractmethod
    async def list_events(*, app_name, user_id, session_id): pass
    
    # === 可选覆盖的方法（基类有默认实现）===
    async def append_event(session, event): pass  # 基类实现：添加到session.events
    async def close_session(*, session): pass     # 基类实现：空方法
```

## 2. 必须实现的接口

### 2.1 会话管理核心方法

| 方法 | 参数 | 返回值 | 调用时机 | 说明 |
|------|------|---------|----------|------|
| `create_session` | app_name, user_id, state?, session_id? | Session | Runner初始化新会话时 | 创建新会话，如果session_id为空需自动生成 |
| `get_session` | app_name, user_id, session_id, config? | Optional[Session] | Runner需要恢复会话时 | 获取存在的会话，不存在返回None |
| `delete_session` | app_name, user_id, session_id | None | 应用主动清理会话时 | 删除会话及其所有数据 |
| `list_sessions` | app_name, user_id | ListSessionsResponse | 管理界面列出用户会话时 | 返回用户在该应用下的所有会话 |
| `list_events` | app_name, user_id, session_id | ListEventsResponse | 需要获取完整对话历史时 | 返回会话中的所有事件 |

### 2.2 实现示例

```python
class CustomSessionService(BaseSessionService):
    def __init__(self, storage_backend):
        self.storage = storage_backend
        
    async def create_session(self, *, app_name: str, user_id: str, 
                           state: Optional[dict] = None, 
                           session_id: Optional[str] = None) -> Session:
        """创建新会话 - 必须实现"""
        if session_id is None:
            session_id = self._generate_session_id()
        
        session = Session(
            id=session_id,
            app_name=app_name, 
            user_id=user_id,
            state=state or {},
            events=[],
            last_update_time=time.time()
        )
        
        # 持久化到存储后端
        await self._store_session(session)
        return session
    
    async def get_session(self, *, app_name: str, user_id: str, 
                         session_id: str, config=None) -> Optional[Session]:
        """获取会话 - 必须实现"""
        session_key = self._make_session_key(app_name, user_id, session_id)
        session_data = await self.storage.get(session_key)
        
        if session_data is None:
            return None
        
        return self._deserialize_session(session_data)
    
    async def delete_session(self, *, app_name: str, user_id: str, session_id: str):
        """删除会话 - 必须实现"""
        session_key = self._make_session_key(app_name, user_id, session_id)
        await self.storage.delete(session_key)
        
        # 清理相关的用户状态和应用状态
        await self._cleanup_related_state(app_name, user_id, session_id)
    
    async def list_sessions(self, *, app_name: str, user_id: str) -> ListSessionsResponse:
        """列出会话 - 必须实现"""
        pattern = self._make_session_pattern(app_name, user_id)
        session_keys = await self.storage.scan(pattern)
        
        sessions = []
        for key in session_keys:
            session_data = await self.storage.get(key)
            sessions.append(self._deserialize_session(session_data))
        
        return ListSessionsResponse(sessions=sessions)
    
    async def list_events(self, *, app_name: str, user_id: str, 
                         session_id: str) -> ListEventsResponse:
        """列出事件 - 必须实现"""
        session = await self.get_session(
            app_name=app_name, user_id=user_id, session_id=session_id
        )
        
        if session is None:
            return ListEventsResponse(events=[])
        
        return ListEventsResponse(events=session.events)
```

## 3. 可选覆盖的接口

### 3.1 事件处理优化

| 方法 | 默认行为 | 覆盖目的 | 调用时机 |
|------|----------|----------|----------|
| `append_event` | 添加到session.events列表，处理state_delta | 优化存储性能，实现增量存储 | 每次Agent或Tool产生事件时 |
| `close_session` | 空操作 | 清理资源，关闭连接 | 会话正常结束时 |

```python
async def append_event(self, session: Session, event: Event) -> Event:
    """优化的事件添加 - 可选覆盖"""
    # 处理状态更新（支持前缀）
    if event.actions and event.actions.state_delta:
        await self._process_state_delta(session, event.actions.state_delta)
    
    # 添加事件到会话
    session.events.append(event)
    session.last_update_time = time.time()
    
    # 优化策略：增量存储而非全量更新
    await self._append_event_to_storage(session.id, event)
    
    return event

async def close_session(self, *, session: Session):
    """会话关闭清理 - 可选覆盖"""
    # 清理缓存
    await self._clear_session_cache(session.id)
    
    # 关闭数据库连接
    await self._close_session_connections(session.id)
    
    # 触发清理回调
    await self._trigger_session_cleanup_callbacks(session)
```

## 4. 自定义辅助方法的使用时机

### 4.1 存储层辅助方法

| 方法名 | 调用时机 | 用途 |
|--------|----------|------|
| `_store_session` | create_session, append_event | 将会话持久化到存储后端 |
| `_retrieve_session` | get_session | 从存储后端获取会话数据 |
| `_append_event_to_storage` | append_event | 增量存储新事件（性能优化） |
| `_cleanup_related_state` | delete_session | 清理user:和app:级别的状态 |

### 4.2 状态管理辅助方法

| 方法名 | 调用时机 | 用途 |
|--------|----------|------|
| `_process_state_delta` | append_event | 处理事件中的状态变更 |
| `_update_user_state` | 处理user:前缀状态时 | 跨会话用户状态持久化 |
| `_update_app_state` | 处理app:前缀状态时 | 全局应用状态管理 |
| `_handle_temp_state` | 处理temp:前缀状态时 | 临时状态处理（不持久化） |

```python
async def _process_state_delta(self, session: Session, state_delta: dict):
    """状态变更处理 - 核心业务逻辑"""
    for key, value in state_delta.items():
        if key.startswith('temp:'):
            # temp: 状态仅在内存中存在，不持久化
            continue
        elif key.startswith('user:'):
            # 跨会话用户状态
            await self._update_user_state(session.user_id, key, value)
        elif key.startswith('app:'):
            # 全局应用状态
            await self._update_app_state(session.app_name, key, value) 
        else:
            # 会话级状态
            session.state[key] = value
```

### 4.3 生命周期管理辅助方法

| 方法名 | 调用时机 | 用途 |
|--------|----------|------|
| `_cleanup_expired_sessions` | 定时任务 | 清理过期会话 |
| `_backup_session_data` | 定期或关键操作前 | 数据备份 |
| `_migrate_session_format` | 版本升级时 | 数据格式迁移 |
| `_validate_session_integrity` | 系统启动或定期检查 | 数据完整性校验 |

## 5. 实际实现案例

### 5.1 Redis实现

```python
import redis.asyncio as redis
import json
import time
from typing import Optional

class RedisSessionService(BaseSessionService):
    """Redis-based SessionService implementation"""
    
    def __init__(self, redis_url: str, ttl_seconds: int = 7 * 24 * 3600):
        self.redis = redis.from_url(redis_url)
        self.ttl_seconds = ttl_seconds
        
        # 启动后台清理任务
        asyncio.create_task(self._background_cleanup())
    
    # === 必须实现的方法 ===
    async def create_session(self, *, app_name: str, user_id: str,
                           state: Optional[dict] = None,
                           session_id: Optional[str] = None) -> Session:
        session_id = session_id or f"sess_{uuid4().hex[:12]}"
        session = Session(
            id=session_id,
            app_name=app_name,
            user_id=user_id, 
            state=state or {},
            events=[],
            last_update_time=time.time()
        )
        await self._store_session(session)
        return session
    
    # 其他必须方法的实现...
    
    # === 可选覆盖的方法 ===
    async def append_event(self, session: Session, event: Event) -> Event:
        """优化的事件添加"""
        # 处理状态更新
        if event.actions and event.actions.state_delta:
            await self._process_state_delta(session, event.actions.state_delta)
        
        session.events.append(event)
        session.last_update_time = time.time()
        
        # 使用Redis管道提高性能
        pipe = self.redis.pipeline()
        pipe.hset(f"session:{session.id}", "events", json.dumps([e.dict() for e in session.events]))
        pipe.hset(f"session:{session.id}", "state", json.dumps(session.state))
        pipe.hset(f"session:{session.id}", "last_update", session.last_update_time)
        pipe.expire(f"session:{session.id}", self.ttl_seconds)
        await pipe.execute()
        
        return event
    
    # === 辅助方法 ===
    async def _store_session(self, session: Session):
        """存储会话到Redis"""
        session_key = f"session:{session.id}"
        session_data = {
            "id": session.id,
            "app_name": session.app_name,
            "user_id": session.user_id,
            "state": json.dumps(session.state),
            "events": json.dumps([event.dict() for event in session.events]),
            "last_update": session.last_update_time
        }
        
        pipe = self.redis.pipeline()
        pipe.hmset(session_key, session_data)
        pipe.expire(session_key, self.ttl_seconds)
        await pipe.execute()
    
    async def _background_cleanup(self):
        """后台清理过期会话"""
        while True:
            try:
                # 清理逻辑
                await asyncio.sleep(3600)  # 每小时清理一次
            except Exception as e:
                logger.error(f"Background cleanup error: {e}")
```

### 5.2 MongoDB实现

```python
from motor.motor_asyncio import AsyncIOMotorClient

class MongoSessionService(BaseSessionService):
    """MongoDB-based SessionService implementation"""
    
    def __init__(self, mongo_url: str, db_name: str = "adk_sessions"):
        self.client = AsyncIOMotorClient(mongo_url)
        self.db = self.client[db_name]
        self.sessions = self.db.sessions
        self.user_states = self.db.user_states
        self.app_states = self.db.app_states
        
        # 创建索引
        asyncio.create_task(self._create_indexes())
    
    async def _create_indexes(self):
        """创建必要的索引"""
        await self.sessions.create_index([("app_name", 1), ("user_id", 1)])
        await self.sessions.create_index([("last_update_time", 1)])  # 用于TTL
        await self.user_states.create_index([("user_id", 1)])
        await self.app_states.create_index([("app_name", 1)])
    
    async def _process_state_delta(self, session: Session, state_delta: dict):
        """MongoDB优化的状态处理"""
        session_updates = {}
        user_updates = {}
        app_updates = {}
        
        for key, value in state_delta.items():
            if key.startswith('temp:'):
                continue
            elif key.startswith('user:'):
                user_updates[key] = value
            elif key.startswith('app:'):
                app_updates[key] = value
            else:
                session.state[key] = value
                session_updates[f"state.{key}"] = value
        
        # 批量更新
        operations = []
        
        if session_updates:
            operations.append(
                UpdateOne(
                    {"_id": f"{session.app_name}:{session.user_id}:{session.id}"},
                    {"$set": session_updates}
                )
            )
        
        if user_updates:
            operations.append(
                UpdateOne(
                    {"user_id": session.user_id},
                    {"$set": user_updates},
                    upsert=True
                )
            )
        
        if app_updates:
            operations.append(
                UpdateOne(
                    {"app_name": session.app_name},
                    {"$set": app_updates},
                    upsert=True
                )
            )
        
        if operations:
            # 使用事务确保一致性
            async with await self.client.start_session() as mongo_session:
                async with mongo_session.start_transaction():
                    for op in operations:
                        await self._execute_update_operation(op)
```

## 6. 最佳实践建议

### 6.1 性能优化

1. **连接池管理**：合理配置数据库连接池大小
2. **批量操作**：使用管道/批量操作减少网络IO
3. **索引优化**：为查询字段创建合适的索引
4. **缓存策略**：对频繁访问的会话进行缓存

### 6.2 可靠性保障

1. **事务支持**：关键操作使用事务保证一致性
2. **错误重试**：网络错误时实现指数退避重试
3. **健康检查**：定期检查存储后端连接状态
4. **降级策略**：存储不可用时的应急处理

### 6.3 监控和维护

1. **指标收集**：会话创建/删除/查询的延迟和成功率
2. **资源清理**：定期清理过期会话和孤立数据
3. **容量规划**：监控存储使用量，提前扩容
4. **版本兼容**：保持数据格式的向后兼容性

## 7. 总结

实现自定义SessionService需要：

1. **必须实现**：5个抽象方法（CRUD + list操作）
2. **可选覆盖**：2个方法（append_event, close_session）进行性能优化
3. **辅助方法**：根据存储后端特性实现相应的存储、清理、状态管理逻辑
4. **生命周期管理**：考虑会话的创建、使用、清理全过程

通过合理的接口实现和优化策略，可以构建高性能、高可靠的会话管理服务。