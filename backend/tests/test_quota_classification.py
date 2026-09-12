"""「账户额度耗尽」与「限流」的区分。

两者都是 HTTP 429，但处置**完全相反**：限流可重试，额度耗尽重试多少次都没用。
不区分的话，用户看到的是「模型请求受到限流」——以为等等就好，而真正的行动项
（去充值）被藏起来了。
"""
from __future__ import annotations

import pytest

from app.infrastructure.llm.anthropic_client import _classify_anthropic_error
from app.infrastructure.llm.openai_compat import (
    OpenAICompatibleLLMError,
    classify_openai_compatible_error,
)
from app.infrastructure.llm.quota import is_quota_exhausted
from backend.application.model_rotation import classify_rotation_failure


class _FakeAPIError(Exception):
    """模拟 SDK 异常：带 status_code 与错误体文本。"""

    def __init__(self, status_code: int, body: str) -> None:
        self.status_code = status_code
        super().__init__(body)


# 线上真实抓到的报错原文（2026-09-12，openai / gpt-5.6-sol）
OPENAI_QUOTA_BODY = (
    "Error code: 429 - {'error': {'message': 'You have no credits remaining. "
    "Add credits to continue using the API at https://platform.openai.com/settings/"
    "organization/billing/.', 'type': 'insufficient_quota', 'param': None, "
    "'code': 'credit_balance_exhausted'}}"
)
OPENAI_PLAIN_RATE_LIMIT = (
    "Error code: 429 - {'error': {'message': 'Rate limit reached for gpt-4o', "
    "'type': 'requests'}}"
)
ANTHROPIC_QUOTA_BODY = (
    "Error code: 429 - {'type': 'error', 'error': {'type': 'invalid_request_error', "
    "'message': 'Your credit balance is too low to access the Anthropic API.'}}"
)


class TestIsQuotaExhausted:
    def test_detects_openai_insufficient_quota(self):
        assert is_quota_exhausted(_FakeAPIError(429, OPENAI_QUOTA_BODY)) is True

    def test_plain_rate_limit_is_not_quota(self):
        assert is_quota_exhausted(_FakeAPIError(429, OPENAI_PLAIN_RATE_LIMIT)) is False

    def test_detects_anthropic_credit_balance(self):
        assert is_quota_exhausted(_FakeAPIError(429, ANTHROPIC_QUOTA_BODY)) is True

    def test_follows_the_cause_chain(self):
        # SDK 常把原始错误包一层；关键字可能只在 __cause__ 上。
        outer = RuntimeError("wrapped")
        outer.__cause__ = _FakeAPIError(429, OPENAI_QUOTA_BODY)
        assert is_quota_exhausted(outer) is True


class TestOpenAICompatibleClassification:
    def test_quota_exhaustion_is_not_retryable(self):
        result = classify_openai_compatible_error(_FakeAPIError(429, OPENAI_QUOTA_BODY))
        assert result.code == "PROVIDER_QUOTA_EXHAUSTED"
        assert result.retryable is False

    def test_plain_rate_limit_stays_retryable(self):
        """回归护栏：别把真正的限流也一并变成不可重试。"""
        result = classify_openai_compatible_error(
            _FakeAPIError(429, OPENAI_PLAIN_RATE_LIMIT)
        )
        assert result.code == "PROVIDER_RATE_LIMITED"
        assert result.retryable is True


class TestAnthropicClassification:
    def test_quota_exhaustion_is_not_retryable(self):
        result = _classify_anthropic_error(_FakeAPIError(429, ANTHROPIC_QUOTA_BODY))
        assert result.code == "PROVIDER_QUOTA_EXHAUSTED"
        assert result.retryable is False

    def test_plain_rate_limit_stays_retryable(self):
        result = _classify_anthropic_error(
            _FakeAPIError(429, '{"error": {"message": "rate limit exceeded"}}')
        )
        assert result.code == "PROVIDER_RATE_LIMITED"
        assert result.retryable is True


class TestRotationFailureMapping:
    def test_provider_quota_code_becomes_terminal_rotation_failure(self):
        """带 .code 的错误走 _provider_error —— 新码必须显式映射。

        否则会掉进 `retryable and code.startswith("PROVIDER_")` 的兜底，
        被当成「上游暂时不可用」而继续轮换同一个没钱了的账号。
        """
        error = OpenAICompatibleLLMError(
            code="PROVIDER_QUOTA_EXHAUSTED",
            message="no quota",
            retryable=False,
            status_code=429,
        )
        failure = classify_rotation_failure(error, stage="request")
        assert failure.code == "MODEL_QUOTA_EXHAUSTED"
        assert failure.retryable is False
        assert "充值" in failure.message

    def test_fallback_path_also_separates_quota_from_rate_limit(self):
        """没有 .code 的裸异常走兜底路径，同样要分开。"""
        quota = classify_rotation_failure(
            _FakeAPIError(429, OPENAI_QUOTA_BODY), stage="request"
        )
        assert quota.code == "MODEL_QUOTA_EXHAUSTED"
        assert quota.retryable is False

        rate = classify_rotation_failure(
            _FakeAPIError(429, OPENAI_PLAIN_RATE_LIMIT), stage="request"
        )
        assert rate.code == "MODEL_RATE_LIMITED"
        assert rate.retryable is True


@pytest.mark.parametrize(
    "body",
    [
        "insufficient_quota",
        "credit_balance_exhausted",
        "you have no credits remaining",
        "exceeded your current quota",
        "credit balance is too low",
    ],
)
def test_marker_coverage(body):
    assert is_quota_exhausted(_FakeAPIError(429, body)) is True
