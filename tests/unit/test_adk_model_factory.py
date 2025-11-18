# -*- coding: utf-8 -*-
"""Unit tests for AdkModelFactory model selection helpers."""

import os
import sys
from types import ModuleType, SimpleNamespace

import pytest

from aether_frame.framework.adk.model_factory import AdkModelFactory


@pytest.fixture(autouse=True)
def clear_env(monkeypatch):
    for key in ["DEEPSEEK_API_KEY", "DEEPSEEK_API_BASE", "AZURE_API_KEY", "AZURE_API_BASE", "AZURE_API_VERSION", "DASHSCOPE_API_KEY"]:
        monkeypatch.delenv(key, raising=False)


def _install_litellm(monkeypatch):
    google_module = sys.modules.setdefault("google", ModuleType("google"))
    adk_module = getattr(google_module, "adk", None) or ModuleType("google.adk")
    google_module.adk = adk_module
    models_module = getattr(adk_module, "models", None) or ModuleType("google.adk.models")
    adk_module.models = models_module
    lite_module = ModuleType("google.adk.models.lite_llm")

    class FakeLite:
        last_kwargs = None

        def __init__(self, **kwargs):
            FakeLite.last_kwargs = kwargs

    lite_module.LiteLlm = FakeLite
    monkeypatch.setitem(sys.modules, "google", google_module)
    monkeypatch.setitem(sys.modules, "google.adk", adk_module)
    monkeypatch.setitem(sys.modules, "google.adk.models", models_module)
    monkeypatch.setitem(sys.modules, "google.adk.models.lite_llm", lite_module)
    return FakeLite


@pytest.mark.asyncio
async def test_create_model_deepseek_streaming(monkeypatch):
    fake_module = ModuleType("aether_frame.framework.adk.deepseek_streaming_llm")

    class FakeStreaming:
        def __init__(self, model, **kwargs):
            self.model = model
            self.kwargs = kwargs

    fake_module.DeepSeekStreamingLLM = FakeStreaming
    monkeypatch.setitem(sys.modules, "aether_frame.framework.adk.deepseek_streaming_llm", fake_module)

    settings = SimpleNamespace(deepseek_api_key="abc123", deepseek_base_url="https://deepseek")
    result = AdkModelFactory.create_model(
        "deepseek/chat",
        settings=settings,
        enable_streaming=True,
        model_config={"temperature": 0.2},
    )
    assert isinstance(result, FakeStreaming)
    assert result.model == "deepseek/chat"
    assert result.kwargs["temperature"] == 0.2
    assert os.environ["DEEPSEEK_API_KEY"] == "abc123"
    assert os.environ["DEEPSEEK_API_BASE"] == "https://deepseek"


def test_create_model_openai_streaming(monkeypatch):
    fake_lite = _install_litellm(monkeypatch)
    AdkModelFactory.create_model(
        "gpt-4o",
        enable_streaming=True,
        model_config={"temperature": 0.7, "top_p": None},
    )
    assert fake_lite.last_kwargs["model"] == "gpt-4o"
    assert fake_lite.last_kwargs["stream"] is True
    assert fake_lite.last_kwargs["temperature"] == 0.7
    assert "top_p" not in fake_lite.last_kwargs


def test_create_model_azure_streaming(monkeypatch):
    from aether_frame.framework.adk import azure_streaming_llm as real_module

    class FakeAzureStreaming:
        def __init__(self, model, **kwargs):
            self.model = model
            self.kwargs = kwargs

    monkeypatch.setattr(real_module, "AzureStreamingLLM", FakeAzureStreaming)

    settings = SimpleNamespace(
        azure_api_key="key",
        azure_api_base="https://azure",
        azure_api_version="2024-03-01",
    )
    result = AdkModelFactory.create_model(
        "azure/gpt-4o",
        settings=settings,
        enable_streaming=True,
        model_config={"temperature": 0.1},
    )
    assert isinstance(result, FakeAzureStreaming)
    assert result.model == "azure/gpt-4o"
    assert result.kwargs["temperature"] == 0.1
    assert result.kwargs["api_key"] == "key"


def test_create_model_azure_sets_env(monkeypatch):
    fake_lite = _install_litellm(monkeypatch)
    settings = SimpleNamespace(
        azure_api_key="key",
        azure_api_base="https://azure",
        azure_api_version="2024-03-01",
    )
    AdkModelFactory.create_model("azure/phi-3-medium", settings=settings, enable_streaming=False)
    assert os.environ.get("AZURE_API_KEY") == "key"
    assert os.environ.get("AZURE_API_BASE") == "https://azure"
    assert os.environ.get("AZURE_API_VERSION") == "2024-03-01"
    assert fake_lite.last_kwargs["stream"] is False


def test_create_model_qwen_uses_dashscope_env(monkeypatch):
    fake_lite = _install_litellm(monkeypatch)
    settings = SimpleNamespace(qwen_api_key=None, qwen_base_url=None)
    monkeypatch.setenv("QWEN_API_KEY", "env-key")
    result = AdkModelFactory.create_model("qwen-long", settings=settings, enable_streaming=True)
    assert fake_lite.last_kwargs["model"] == "dashscope/qwen-long"
    assert fake_lite.last_kwargs["stream"] is True
    assert os.environ["DASHSCOPE_API_KEY"] == "env-key"
    assert result is not None


def test_create_model_deepseek_streaming_missing_dependency(monkeypatch):
    monkeypatch.setitem(sys.modules, "aether_frame.framework.adk.deepseek_streaming_llm", None)
    with pytest.raises(RuntimeError):
        AdkModelFactory.create_model("deepseek-mock", enable_streaming=True)


def test_create_model_openai_missing_litellm_returns_identifier(monkeypatch):
    import builtins

    real_import = builtins.__import__

    def fake_import(name, *args, **kwargs):
        if name == "google.adk.models.lite_llm":
            raise ImportError("missing")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)
    model = AdkModelFactory.create_model("gpt-4.1", enable_streaming=False)
    assert model == "gpt-4.1"


def test_is_custom_and_supports_streaming_flags():
    assert AdkModelFactory.is_custom_model("deepseek/chat") is True
    assert AdkModelFactory.supports_streaming("azure/gpt-4o") is True
    assert AdkModelFactory.is_custom_model("gemini-pro") is False
    assert AdkModelFactory.supports_streaming("unknown-model") is False
