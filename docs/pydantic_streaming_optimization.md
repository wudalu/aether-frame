## Reducing Pydantic Overhead in Azure Streaming

### Problem recap
- `src/aether_frame/framework/adk/azure_streaming_llm.py` heavily relies on `google.genai.types` (Pydantic models) for every streaming chunk: `_clone_content`, `_normalize_history`, `_ingest_text`, `_capture_tool_calls`.
- Profiling shows `pydantic/main.py` (`__setattr__`, `__init__`, `__repr__`, etc.) dominating CPU time when GPT‑4* streams rapidly. Each chunk triggers multiple deep copies, even though most data is just pass-through.

### External references
- **Google Gemini API streaming** (Context7 `https://ai.google.dev/api/generate-content`): examples simply iterate over streamed chunks and append raw text without wrapping each chunk in models.
- **LiteLLM Gemini adapter** (`litellm/google_genai/streaming_iterator.py` & `adapters/transformation.py`): streams raw bytes/dicts, defers Pydantic (`ModelResponse`) creation until a full response is needed. This keeps hot paths lightweight.

### Optimization pattern
1. **Introduce lightweight structures**  
   Use simple dataclasses for in-flight history/chunks:
   ```python
   from dataclasses import dataclass, field
   from typing import List, Optional

   @dataclass
   class LitePart:
       text: Optional[str] = None
       function_call: Optional[dict] = None

   @dataclass
   class LiteContent:
       role: str
       parts: List[LitePart] = field(default_factory=list)
   ```
   Store/adapt history in these `Lite*` objects, and convert back to `types.Content` only when sending a request or emitting the final `LlmResponse`.

2. **Single conversion point**
   ```python
   def lite_to_content(item: LiteContent) -> types.Content:
       return types.Content(
           role=item.role,
           parts=[
               types.Part(
                   text=part.text,
                   function_call=types.FunctionCall(**part.function_call)
                   if part.function_call else None,
               )
               for part in item.parts
           ],
       )
   ```
   `send_history` / `_prepare_request` call this only once per message. Streaming loops mutate `LiteContent` directly (list append/extend) with trivial cost.

3. **Batch conversion at flush**
   - `_enqueue_with_batching` accumulates raw fragments (strings/tool-call dicts) inside a `LiteContent`.  
   - Flush rule satisfied → call `lite_to_content` and build `LlmResponse`.  
   - Tool-call args remain plain strings/dicts until flush, avoiding repeated `types.FunctionCall(...)`.

4. **Reuse caches**
   - Keep a dict of `tool_call_id -> LitePart` so we update only the `args` string instead of allocating new Pydantic objects per chunk.
   - History normalization operates on `LiteContent` and only clones simple dataclasses.

### Example integration sketch
```python
class AzureLiveConnection(BaseLlmConnection):
    def __init__(...):
        self._history_lite: List[LiteContent] = []

    def _clone_content(self, content: types.Content) -> LiteContent:
        return LiteContent(
            role=content.role,
            parts=[
                LitePart(
                    text=getattr(part, "text", None),
                    function_call=getattr(part, "function_call", None).model_dump()
                    if getattr(part, "function_call", None) else None,
                )
                for part in content.parts or []
            ],
        )

    def _prepare_request(self) -> LlmRequest:
        request = self._base_request.model_copy(deep=True)
        request.contents = [lite_to_content(item) for item in self._history_lite]
        return request

    def _enqueue_with_batching(self, fragments: List[str]):
        lite = LiteContent(role="model", parts=[LitePart(text="".join(fragments))])
        llm_response = LlmResponse(content=lite_to_content(lite), partial=True)
        await self._response_queue.put(llm_response)
```

### Expected benefits
- Hot-path operations turn into list/dict mutations; Pydantic allocations happen O(messages) instead of O(chunks).
- Profiling should show significant drop in `pydantic.main.__setattr__` and friends.
- Easier to integrate batching logic: `LiteContent`/`LitePart` can be merged/split without touching Pydantic internals.

### Rollout suggestions
1. Add `Lite*` structures + conversion helpers alongside existing code; guard with feature flag for safe rollout.
2. Instrument `lite_to_content` to count conversions; compare before/after to ensure Pydantic operations only occur when necessary.
3. Combine with `streaming_controls.TokenBatchingConfig` to further reduce the number of final conversions.

### Quick win checklist
For immediate relief before the full refactor:
1. Cache history in lightweight dicts: keep `_history_lite` as plain dicts and only call `types.Content.model_validate` inside `_prepare_request`.
2. Mark freshly appended content to skip duplicate clones inside `_normalize_history`.
3. Accumulate streaming text as raw strings and create `types.Part.from_text` only when pushing to `_response_queue`.
4. Store tool-call metadata as `{id: {"name": ..., "args": ...}}` and construct `types.FunctionCall(...)` only at flush time.
These changes touch only `azure_streaming_llm.py` and can be rolled out quickly to reduce the hottest `pydantic.main` frames even before adopting `LiteContent`.
