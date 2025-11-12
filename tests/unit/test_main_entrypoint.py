# -*- coding: utf-8 -*-
"""Tests for main module entry points."""

from unittest.mock import AsyncMock, patch

import pytest

from aether_frame import main as main_module


@pytest.mark.asyncio
async def test_main_calls_create_ai_assistant(monkeypatch):
    async def fake_create(settings):
        class FakeAssistant:
            async def process_request(self, request):
                return "ok"

        return FakeAssistant()

    monkeypatch.setattr(main_module, "create_ai_assistant", fake_create)
    result = await main_module.main()
    assert result is None


def test_cli_main_handles_keyboard_interrupt(capsys):
    def raise_interrupt(coro):
        coro.close()
        raise KeyboardInterrupt()

    with patch("asyncio.run", side_effect=raise_interrupt):
        main_module.cli_main()
    assert "Shutdown requested" in capsys.readouterr().out


def test_cli_main_handles_exception(monkeypatch, capsys):
    def raise_runtime_error(coro):
        coro.close()
        raise RuntimeError("boom")

    with patch("asyncio.run", side_effect=raise_runtime_error):
        with pytest.raises(SystemExit):
            main_module.cli_main()
    assert "Application failed" in capsys.readouterr().out
