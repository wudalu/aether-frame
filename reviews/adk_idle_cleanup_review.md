# ADK Idle Cleanup Review

## Findings

- **High – runner teardown during chat cleanup**  
  `AdkSessionManager.cleanup_chat_session()` now calls `_cleanup_session_and_runner()` which unconditionally invokes `runner_manager.cleanup_runner()` (`src/aether_frame/framework/adk/adk_session_manager.py:573`).  
  - `cleanup_runner` removes the runner, clears every session mapped to it, and fires `_handle_agent_cleanup`, so the owning agent is dropped from `AgentManager`.  
  - In scenarios where one agent backs multiple business chat sessions, clearing a single chat removes the shared runner/agent while other `ChatSessionInfo` objects still reference it (`active_runner_id`, `active_adk_session_id`). The next turn for those chats will fail because `get_runner_for_agent()` can no longer locate the runner entry.  
  - Please gate runner destruction on “no other sessions remain” (reuse `_cleanup_session_only` + `_evaluate_runner_agent_idle`) instead of always tearing down the runner.

## Notes

- Tests (`tests/unit/test_adk_session_manager_idle.py`, `tests/integration/test_adk_idle_cleanup_flow.py`, `tests/e2e/test_adk_idle_cleanup_e2e.py`) only exercise single-chat scenarios, so they don’t expose the runner-sharing regression described above.
