"""Tests for LLM client utilities — token parameter selection."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from app.core.config import settings
from app.core.exceptions import LLMError
from app.infrastructure import llm as llm_module
from app.infrastructure.llm import (
    OpenAILLMClient,
    _reasoning_params,
    _structured_output_max_tokens,
    _temperature_param,
    _token_param,
)
from app.infrastructure.llm.openai_compat import normalize_openai_compatible_base_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://api.example.com", "https://api.example.com/v1"),
        ("https://api.example.com/v1/", "https://api.example.com/v1"),
        (
            "https://api.example.com/v1/chat/completions?x=1#part",
            "https://api.example.com/v1",
        ),
        (
            "https://gateway.example.com/openai/v1/responses",
            "https://gateway.example.com/openai/v1",
        ),
    ],
)
def test_normalize_openai_compatible_base_url(raw, expected):
    assert normalize_openai_compatible_base_url(raw) == expected


@pytest.mark.asyncio
async def test_custom_gpt56_can_use_chat_completions_explicitly():
    client = OpenAILLMClient(
        model="gpt-5.6",
        api_key="secret",
        base_url="https://proxy.example/v1",
        transport_mode="chat_completions",
        structured_output_mode="prompt_json",
    )
    chat_create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
        )
    )
    responses_create = AsyncMock()
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=chat_create)),
        responses=SimpleNamespace(create=responses_create),
    )

    result = await client.chat_structured(
        messages=[{"role": "user", "content": "return JSON"}],
        output_schema={"type": "object"},
        max_tokens=128,
        max_retries=1,
    )

    assert result == {"ok": True}
    chat_create.assert_awaited_once()
    responses_create.assert_not_awaited()
    assert "response_format" not in chat_create.await_args.kwargs


@pytest.mark.asyncio
async def test_openai_compatible_invalid_json_exposes_stable_error_metadata():
    client = OpenAILLMClient(
        model="gpt-5.6",
        api_key="secret",
        base_url="https://proxy.example/v1",
        transport_mode="chat_completions",
        structured_output_mode="prompt_json",
    )
    client._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(
                    return_value=SimpleNamespace(
                        choices=[
                            SimpleNamespace(
                                message=SimpleNamespace(content='{"status":')
                            )
                        ]
                    )
                )
            )
        )
    )

    with pytest.raises(LLMError) as exc_info:
        await client.chat_structured(
            messages=[{"role": "user", "content": "return JSON"}],
            output_schema={"type": "object"},
            max_retries=1,
        )

    assert exc_info.value.code == "MODEL_INVALID_JSON"
    assert exc_info.value.retryable is True


@pytest.mark.parametrize(
    ("model", "expected"),
    [
        ("gpt-5.5", 600.0),
        ("gpt-5.5-pro", 600.0),
        ("gpt-5.5-2026-04-23", 600.0),
        (" GPT-5.5-PRO ", 600.0),
        ("gpt-5.6", 600.0),
        ("gpt-5.6-terra", 600.0),
        ("gpt-5.6-sol", 600.0),
        ("gpt-5.4", 120.0),
        ("gpt-4o", 120.0),
        # 智谱 / Moonshot：真实任务实测在 run_hypothesis 阶段双双 MODEL_TIMEOUT
        # （glm-5.3 146.6s、kimi-k2.6 141.6s），都撞在 120s 默认预算上。
        ("glm-5.3", 600.0),
        ("glm-5.3-flash", 600.0),
        ("glm-4.6", 600.0),
        ("kimi-k2.6", 600.0),
        ("kimi-k3", 600.0),
    ],
)
def test_structured_report_timeout_is_model_specific(model, expected):
    assert llm_module._structured_report_timeout_seconds(model) == expected


@pytest.mark.parametrize("model", ["gpt-5.5", "gpt-5.5-pro", "gpt-5.6"])
def test_new_gpt_models_get_larger_structured_output_budget(model):
    assert _structured_output_max_tokens(model, 16384) == 32768


def test_older_model_keeps_configured_structured_output_budget():
    assert _structured_output_max_tokens("gpt-5.4", 16384) == 16384


@pytest.mark.parametrize(
    "model", ["glm-5.3", "glm-5.3-flash", "kimi-k2.6", "kimi-k3", "deepseek-v4-pro"]
)
def test_reasoning_models_get_the_reasoning_output_budget(model):
    """推理模型把输出预算烧在隐藏思维链上，需要远高于普通档的上限。

    实测 glm-5.3 与 kimi-k2.6 在 16384 的普通档下跑满约 470 秒后返回**空内容**
    （"OpenAI-compatible response shape invalid: response text is empty"），
    与当年 deepseek-v4 的现象同源。
    """
    assert _structured_output_max_tokens(model, 16384) == 65536


def test_openai_client_bounds_each_request_and_disables_hidden_sdk_retries(
    monkeypatch,
):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    constructor = Mock(return_value=SimpleNamespace())
    monkeypatch.setattr("app.infrastructure.llm.AsyncOpenAI", constructor)

    OpenAILLMClient(model="gpt-4.1")

    constructor.assert_called_once_with(
        api_key="test-key",
        timeout=120.0,
        max_retries=0,
    )


class TestTokenParam:
    """max_completion_tokens vs max_tokens based on model name."""

    def test_gpt4o_uses_max_tokens(self):
        assert _token_param("gpt-4o", 16384) == {"max_tokens": 16384}

    def test_gpt_5_5_uses_max_completion_tokens(self):
        assert _token_param("gpt-5.5", 16384) == {"max_completion_tokens": 16384}

    def test_gpt_5_6_uses_max_completion_tokens(self):
        assert _token_param("gpt-5.6", 8192) == {"max_completion_tokens": 8192}

    def test_gpt_5_6_variants(self):
        for model in ("gpt-5.6-terra", "gpt-5.6-sol", "gpt-5.6-luna"):
            assert _token_param(model, 4096) == {"max_completion_tokens": 4096}

    def test_gpt_5_5_pro(self):
        assert _token_param("gpt-5.5-pro", 16384) == {"max_completion_tokens": 16384}

    def test_o_series_uses_max_completion_tokens(self):
        for model in ("o1", "o3", "o4"):
            assert _token_param(model, 100000) == {"max_completion_tokens": 100000}

    def test_unknown_model_falls_back_to_max_tokens(self):
        assert _token_param("unknown-model", 100) == {"max_tokens": 100}


class TestTemperatureParam:
    """temperature omission for models that don't support it."""

    def test_gpt4o_includes_temperature(self):
        assert _temperature_param("gpt-4o", 0.3) == {"temperature": 0.3}

    def test_gpt4o_none_omits_temperature(self):
        assert _temperature_param("gpt-4o", None) == {}

    def test_gpt_5_5_omits_temperature(self):
        assert _temperature_param("gpt-5.5", 0.3) == {}

    def test_gpt_5_5_pro_omits_temperature(self):
        assert _temperature_param("gpt-5.5-pro", 0.3) == {}

    def test_o_series_omits_temperature(self):
        assert _temperature_param("o1", 0.3) == {}
        assert _temperature_param("o3", 1.0) == {}

    def test_kimi_models_omit_temperature(self):
        """Moonshot 的 k2 系只接受 temperature=1。

        我们发 0.3 会被上游 400 拒绝（实测原文："invalid temperature: only 1
        is allowed for this model"），而省略该参数时由供应商套用自己的默认值，
        就是唯一允许的那个 1。
        """
        assert _temperature_param("kimi-k2.6", 0.3) == {}
        assert _temperature_param("kimi-k2.7-code", 0.3) == {}
        assert _temperature_param("kimi-k2.6", None) == {}

    def test_unknown_model_includes_temperature(self):
        assert _temperature_param("unknown", 0.5) == {"temperature": 0.5}


@pytest.mark.asyncio
async def test_structured_chat_sends_json_schema(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient()
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"ok": true}'))]
        )
    )
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }

    result = await client.chat_structured(
        messages=[{"role": "user", "content": "return JSON"}],
        output_schema=schema,
        schema_name="test_output",
    )

    assert result == {"ok": True}
    assert create.await_args.kwargs["response_format"] == {
        "type": "json_schema",
        "json_schema": {
            "name": "test_output",
            "strict": True,
            "schema": schema,
        },
    }


@pytest.mark.asyncio
async def test_gpt5_chat_uses_responses_api(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient(model="gpt-5.5-pro")
    create = AsyncMock(return_value=SimpleNamespace(output_text="OK"))
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))

    result = await client.chat(
        messages=[{"role": "user", "content": "reply OK"}],
        max_tokens=64,
        max_retries=1,
    )

    assert result == "OK"
    create.assert_awaited_once_with(
        model="gpt-5.5-pro",
        input=[{"role": "user", "content": "reply OK"}],
        max_output_tokens=64,
    )


@pytest.mark.asyncio
async def test_responses_path_passes_temperature_when_the_model_accepts_it(monkeypatch):
    """Responses 路径曾经对**所有**模型丢掉 temperature，使 openai_temperature
    静默失效。gpt-5.5/gpt-5.6 系不接受该参数（由 _temperature_param 过滤），
    但 gpt-5.4 这类模型既走 Responses 路径、又接受温度，必须显式传下去。
    """
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    monkeypatch.setattr(settings, "openai_temperature", 0.3)
    client = OpenAILLMClient(model="gpt-5.4")
    create = AsyncMock(return_value=SimpleNamespace(output_text="OK"))
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))

    await client.chat(
        messages=[{"role": "user", "content": "reply OK"}],
        max_tokens=64,
        max_retries=1,
    )

    assert create.await_args.kwargs["temperature"] == 0.3


@pytest.mark.asyncio
async def test_responses_path_omits_temperature_when_the_model_rejects_it(monkeypatch):
    """反向护栏：gpt-5.6 不接受 temperature，传下去会 400。"""
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient(model="gpt-5.6")
    create = AsyncMock(return_value=SimpleNamespace(output_text="OK"))
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))

    await client.chat(
        messages=[{"role": "user", "content": "reply OK"}],
        max_tokens=64,
        max_retries=1,
    )

    assert "temperature" not in create.await_args.kwargs


@pytest.mark.asyncio
async def test_gpt5_structured_chat_uses_responses_api(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient(model="gpt-5.5-pro")
    create = AsyncMock(return_value=SimpleNamespace(output_text='{"ok": true}'))
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))
    schema = {
        "type": "object",
        "properties": {"ok": {"type": "boolean"}},
        "required": ["ok"],
        "additionalProperties": False,
    }

    result = await client.chat_structured(
        messages=[{"role": "user", "content": "return JSON"}],
        output_schema=schema,
        max_tokens=128,
        max_retries=1,
    )

    assert result == {"ok": True}
    request = create.await_args.kwargs
    assert request["model"] == "gpt-5.5-pro"
    assert request["max_output_tokens"] == 128
    assert request["input"][0]["role"] == "system"
    assert '"additionalProperties": false' in request["input"][0]["content"]


@pytest.mark.asyncio
async def test_gpt5_structured_chat_uses_larger_default_budget(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient(model="gpt-5.6")
    create = AsyncMock(return_value=SimpleNamespace(output_text='{"ok": true}'))
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))

    await client.chat_structured(
        messages=[{"role": "user", "content": "return JSON"}],
        output_schema={"type": "object"},
        max_retries=1,
    )

    assert create.await_args.kwargs["max_output_tokens"] == 32768


@pytest.mark.asyncio
async def test_gpt5_structured_chat_reports_incomplete_response(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient(model="gpt-5.6")
    create = AsyncMock(
        return_value=SimpleNamespace(
            status="incomplete",
            incomplete_details=SimpleNamespace(reason="max_output_tokens"),
            output_text='{"ok":',
        )
    )
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))

    with pytest.raises(LLMError, match="response truncated: max_output_tokens"):
        await client.chat_structured(
            messages=[{"role": "user", "content": "return JSON"}],
            output_schema={"type": "object"},
            max_retries=1,
        )


@pytest.mark.asyncio
async def test_structured_chat_uses_json_object_for_freeform_schema(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient(model="gpt-4o")
    create = AsyncMock(
        return_value=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content='{"data": {"key": "value"}}'))]
        )
    )
    client._client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    schema = {
        "type": "object",
        "properties": {
            "data": {
                "type": "object",
                "additionalProperties": True,
            }
        },
    }

    result = await client.chat_structured(
        messages=[{"role": "user", "content": "return JSON"}],
        output_schema=schema,
        schema_name="freeform_output",
        max_retries=1,
    )

    assert result == {"data": {"key": "value"}}
    request = create.await_args.kwargs
    assert request["response_format"] == {"type": "json_object"}
    assert request["messages"][0]["role"] == "system"
    assert '"additionalProperties": true' in request["messages"][0]["content"]


@pytest.mark.asyncio
async def test_structured_chat_reports_openai_response_shape_error(monkeypatch):
    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient(model="claude-fable-5")
    client._client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(create=AsyncMock(return_value="not-openai"))
        )
    )

    with pytest.raises(LLMError, match="OpenAI-compatible response shape invalid"):
        await client.chat_structured(
            messages=[{"role": "user", "content": "return JSON"}],
            output_schema={"type": "object"},
            max_retries=1,
        )


@pytest.mark.asyncio
async def test_structured_chat_exposes_task_timeout_without_duplicate_retry(monkeypatch):
    from openai import APITimeoutError

    from app.core.exceptions import LLMTaskTimeoutError

    monkeypatch.setattr(settings, "openai_api_key", "test-key")
    client = OpenAILLMClient(model="gpt-5.5-2026-04-23")
    create = AsyncMock(side_effect=APITimeoutError(request=Mock()))
    client._client = SimpleNamespace(responses=SimpleNamespace(create=create))

    with pytest.raises(LLMTaskTimeoutError) as exc_info:
        await client.chat_structured(
            messages=[{"role": "user", "content": "return JSON"}],
            output_schema={"type": "object"},
            max_retries=1,
        )

    assert exc_info.value.code == "PROVIDER_MODEL_TASK_TIMEOUT"
    assert exc_info.value.retryable is False
    assert exc_info.value.timeout_seconds == 600
    create.assert_awaited_once()
    assert create.await_args.kwargs["timeout"] == 600.0


class TestReasoningParams:
    """推理强度控制。

    智谱 GLM 与 Moonshot Kimi 的旗舰模型默认重推理，会把输出预算烧在思维链上。
    实测 glm-5.3 / kimi-k2.6 在未加控制时跑满约 470 秒后正文一个字都不剩
    （"response text is empty"）。
    """

    def test_adjustable_models_get_low_effort(self):
        # glm-5.3 系与 kimi-k3 思考关不掉，只能用 reasoning_effort 调深浅（默认 max）。
        assert _reasoning_params("glm-5.3") == {"reasoning_effort": "low"}
        assert _reasoning_params("glm-5.3-flash") == {"reasoning_effort": "low"}
        assert _reasoning_params("kimi-k3") == {"reasoning_effort": "low"}

    def test_disableable_models_turn_thinking_off(self):
        for model in ("kimi-k2.6", "kimi-k2.5", "glm-5.2", "glm-5", "glm-5.1", "glm-4.6"):
            assert _reasoning_params(model) == {
                "extra_body": {"thinking": {"type": "disabled"}}
            }, model

    def test_forced_thinking_models_are_left_untouched(self):
        """glm-4.7 与 kimi-k2.7-code 关不掉思考，传 disabled 会被上游拒绝。"""
        assert _reasoning_params("glm-4.7") == {}
        assert _reasoning_params("kimi-k2.7-code") == {}

    def test_never_sends_both_controls_at_once(self):
        """上游会 400：cannot specify both 'thinking' and 'reasoning_effort'。"""
        for model in ("glm-5.3", "glm-5.3-flash", "kimi-k3", "kimi-k2.6", "glm-5"):
            params = _reasoning_params(model)
            assert not ("reasoning_effort" in params and "extra_body" in params), model

    def test_unrelated_models_keep_original_behaviour(self):
        for model in ("gpt-5.6-terra", "gpt-4o", "deepseek-v4-pro", "deepseek-flash"):
            assert _reasoning_params(model) == {}, model


@pytest.mark.asyncio
async def test_reasoning_params_reach_the_wire():
    """抓真实的 HTTP body，确认推理控制参数确实发出去了（不是只算了个字典）。"""
    import json as _json

    import httpx
    from openai import AsyncOpenAI

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = _json.loads(request.content)
        return httpx.Response(
            200,
            json={"choices": [{"message": {"content": '{"ok": true}'}}]},
        )

    client = OpenAILLMClient(model="kimi-k2.6", api_key="x", base_url="https://api.moonshot.cn/v1")
    client._client = AsyncOpenAI(
        api_key="x",
        base_url="https://api.moonshot.cn/v1",
        max_retries=0,
        http_client=httpx.AsyncClient(transport=httpx.MockTransport(handler)),
    )

    await client.chat_structured(
        messages=[{"role": "user", "content": "return JSON"}],
        output_schema={"type": "object"},
        max_tokens=64,
        max_retries=1,
    )

    body = captured["body"]
    # 关掉思考的模型走 extra_body
    assert body["thinking"] == {"type": "disabled"}
    # 且绝不能同时带另一个（上游会 400）
    assert "reasoning_effort" not in body
