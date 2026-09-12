"""根 `.env.example` 只能包含 `app.core.config.Settings` 认识的键。

背景：`Settings` 的 pydantic 配置是 `extra=forbid`（pydantic-settings 的默认值，
不在自己 model_config 里写也一样），而它通过 `env_file=".env"` 直接读根 `.env`。
所以根 `.env` 里只要出现一个它没声明的键，**应用启动就会直接崩**：

    pydantic_core.ValidationError: 1 validation error for Settings
      provider_key_file  Extra inputs are not permitted [type=extra_forbidden]

这个坑真实发生过：根 `.env.example` 里带过 `PROVIDER_ENCRYPTION_KEY` 与
`PROVIDER_KEY_FILE`（那是 `BackendSettings` 的字段），照模板复制成 `.env`
部署到服务器后 uvicorn 起不来。
"""
from __future__ import annotations

from pathlib import Path

from app.core.config.settings import Settings

REPO_ROOT = Path(__file__).resolve().parent.parent


def _declared_assignment_keys(path: Path) -> set[str]:
    """取出文件里形如 `KEY=...` 的键，忽略注释与空行。"""
    keys: set[str] = set()
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        keys.add(line.split("=", 1)[0].strip())
    return keys


def test_root_env_example_only_uses_keys_settings_declares() -> None:
    keys = _declared_assignment_keys(REPO_ROOT / ".env.example")
    assert keys, "没从根 .env.example 解析出任何键，检查文件是否被改动过"

    # 环境变量名是字段名的大写形式（Settings.__init__ 里 `env_name = name.upper()`）。
    declared = set(Settings.model_fields)
    undeclared = sorted(key for key in keys if key.lower() not in declared)
    assert not undeclared, (
        "根 .env.example 含 Settings 未声明的键，照抄成 .env 会让应用启动即崩 "
        f"（extra_forbidden）：{undeclared}。后端专属的键应放 backend/.env。"
    )


def test_settings_is_still_extra_forbid_so_this_guard_is_meaningful() -> None:
    """护栏本身的前提：Settings 会对未知键报错。

    若哪天有人给 Settings 加了 extra="ignore"，这条会红 —— 那时应当连带
    重新评估上面那条测试还有没有必要，而不是默默失效。
    """
    import pytest
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        Settings(definitely_not_a_real_field="x")
