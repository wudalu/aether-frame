# ADK Ephemeral File Handling Design

## Background
Aether Frame recently gained long-term knowledge persistence by syncing `TaskRequest.available_knowledge` into the ADK memory service. This flow targets reusable, durable knowledge (product docs, FAQs, etc.).  
Users can also upload files that are only relevant to the current conversation turn or session. Pushing every upload into long-term memory is wasteful and can leak sensitive data that should expire with the session.

## Goals
- Treat user uploads as *ephemeral attachments* unless explicitly promoted to long-term knowledge.
- Ensure agents can access attachments immediately during the current request.
- Avoid polluting MemoryService state with short-lived data.
- Preserve a pathway for future RAG ingestion (manual or automated) without coupling it to the baseline flow.

## Options Considered
| Option | Pros | Cons |
| ------ | ---- | ---- |
| Store uploads as `KnowledgeSource` & sync to MemoryService | Reuses existing pipeline | Forces long-term persistence; duplicates data; leaks session-only files |
| Only inject attachments via ad-hoc message metadata | Simple to implement | Hard to standardise; no structured metadata for downstream tools |
| Use existing `FileReference` + `UniversalMessage` split (chosen) | Unified file contract; easy to extend; keeps long-term and short-term concerns separate | Requires additional wiring to surface attachments in runtime |

## Selected Design
1. Extend `TaskRequest` with an `attachments: List[FileReference]` field for session-scoped files.
2. Preserve current behaviour for `available_knowledge` (long-term memory).
3. Session manager and memory sync logic ignore attachments entirely.
4. Domain agents append attachment metadata to the outgoing conversation payload so ADK/Gemini can reference them in the current execution.
5. Future RAG ingestion can opt-in by converting `FileReference` entries into `KnowledgeSource`; this step remains explicit.

## Implementation Plan
1. **Contracts & Builders**  
   - Add `attachments` field to `TaskRequest` with default empty list.  
   - Update factories/builders to accept the new field.
2. **Execution Flow**  
   - Ensure `AdkSessionManager` ignores attachments while syncing knowledge to MemoryService.  
   - Update `AdkDomainAgent` to surface attachment metadata within the request payload (e.g., append a message summarising available files).
3. **Tooling & Metadata**  
   - Provide a helper that converts `FileReference` to a human-readable summary for the ADK conversation.  
   - Preserve original `FileReference` object in runtime context for potential tool usage.
4. **Tests**  
   - Unit test: attachments stay out of MemoryService sync.  
   - Unit/integration test: domain agent includes attachments in outgoing content.
5. **Docs & Follow-ups**  
   - Document the short vs. long-term split (this file).  
   - Future work: optional pipeline to promote attachments into KnowledgeSource when desired.
