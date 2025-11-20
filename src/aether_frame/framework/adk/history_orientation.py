# -*- coding: utf-8 -*-
"""Utilities for keeping ADK conversation history in chronological order."""

from __future__ import annotations

import logging
from typing import List, Optional, Tuple

from google.genai import types

TextSignature = Tuple[str, Tuple[str, ...]]


def content_text_signature(content: types.Content) -> Optional[TextSignature]:
    """Return a lightweight text signature for comparison purposes."""
    parts = getattr(content, "parts", None) or []
    texts = []
    for part in parts:
        text = getattr(part, "text", None)
        if text:
            texts.append(text.strip())
        else:
            return None
    if not texts:
        return None
    return content.role, tuple(texts)


class HistoryOrientationManager:
    """Detects whether history arrives newest-first and reorders if needed."""

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._orientation: Optional[str] = None

    def prepare_history(self, history: List[types.Content]) -> List[types.Content]:
        """Apply the previously detected orientation to a new history payload."""
        if self._orientation == "newest_first":
            return list(reversed(history))
        return history

    def ensure_chronological(
        self, history: List[types.Content], new_content: types.Content
    ) -> List[types.Content]:
        """Ensure stored history ordering matches chronological expectations."""
        if not history or self._orientation is not None:
            return history

        new_signature = content_text_signature(new_content)
        if not new_signature:
            return history

        first_signature = content_text_signature(history[0])
        last_signature = content_text_signature(history[-1])

        if last_signature and new_signature == last_signature:
            self._orientation = "chronological"
            return history

        if first_signature and new_signature == first_signature:
            self._orientation = "newest_first"
            self._logger.warning(
                "Detected newest-first conversation history ordering; reversing "
                "contents before forwarding to the streaming model."
            )
            return list(reversed(history))

        return history
