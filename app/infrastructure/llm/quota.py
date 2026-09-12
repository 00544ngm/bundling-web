"""识别供应商的「账户额度已用尽」。

OpenAI 把账户余额耗尽也返回 **HTTP 429**（`type=insufficient_quota`、
`code=credit_balance_exhausted`），Anthropic 同样用 429 报余额不足 —— 状态码
和「限流」撞在一起，光看状态码分不出来。

两者的处置完全相反，所以必须分开：

- **限流**是暂时的，等一等/换个模型确实可能成功 → 可重试。
- **额度耗尽**是账户级问题，不充值的话重试多少次都不会成功 → 不可重试。
  这和 `PROVIDER_AUTH_FAILED`（密钥无效）是同一类，代码里那类错误在模型轮换
  中同样是终止性的。

不区分的代价有两条：一是提示说「限流」，用户以为等等就好，真正的行动项
（去充值）被藏起来了；二是让轮换继续拿同一个没钱了的账号反复试，白等几轮。
"""

# 各家在 429 错误体里的措辞。统一按小写子串匹配。
QUOTA_EXHAUSTED_MARKERS = (
    # OpenAI
    "insufficient_quota",
    "credit_balance_exhausted",
    "no credits remaining",
    "exceeded your current quota",
    # Anthropic
    "credit balance is too low",
    "insufficient credits",
)


def is_quota_exhausted(error: BaseException) -> bool:
    """错误（含其 __cause__ 链）里是否出现额度耗尽的措辞。"""
    current: BaseException | None = error
    for _ in range(6):
        if current is None:
            break
        text = str(current).lower()
        if any(marker in text for marker in QUOTA_EXHAUSTED_MARKERS):
            return True
        current = current.__cause__
    return False


__all__ = ["QUOTA_EXHAUSTED_MARKERS", "is_quota_exhausted"]
