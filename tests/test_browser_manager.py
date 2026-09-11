from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

from app.core.exceptions import BrowserError
from app.infrastructure.browser import (
    PlaywrightBrowserManager,
    build_chrome_launch_args,
)


def test_chrome_launch_args_do_not_disable_security_boundaries(tmp_path):
    args = build_chrome_launch_args(tmp_path / "profile")

    assert "--no-sandbox" not in args
    assert "--remote-allow-origins=*" not in args


@pytest.mark.asyncio
async def test_stop_terminates_manager_owned_chrome_process():
    manager = PlaywrightBrowserManager()
    process = Mock()
    process.wait.return_value = 0
    playwright = AsyncMock()
    manager._chrome_process = process
    manager._owns_chrome_process = True
    manager._playwright = playwright

    await manager.stop()

    playwright.stop.assert_awaited_once()
    process.terminate.assert_called_once()
    process.wait.assert_called_once_with(timeout=5)


@pytest.mark.asyncio
async def test_stop_leaves_external_chrome_process_running():
    manager = PlaywrightBrowserManager()
    process = Mock()
    manager._chrome_process = process
    manager._owns_chrome_process = False
    manager._playwright = AsyncMock()

    await manager.stop()

    process.terminate.assert_not_called()
    process.kill.assert_not_called()


@pytest.mark.asyncio
async def test_stop_continues_cleanup_after_disconnected_context():
    manager = PlaywrightBrowserManager()
    context = AsyncMock()
    context.close.side_effect = RuntimeError("target already closed")
    browser = AsyncMock()
    playwright = AsyncMock()
    manager._context = context
    manager._browser = browser
    manager._playwright = playwright

    with pytest.raises(BrowserError, match="target already closed"):
        await manager.stop()

    browser.close.assert_awaited_once()
    playwright.stop.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_suppresses_stale_cleanup_error_and_starts_fresh_browser():
    manager = PlaywrightBrowserManager()
    manager.stop = AsyncMock()
    manager.start = AsyncMock()

    await manager.restart()

    manager.stop.assert_awaited_once_with(raise_errors=False)
    manager.start.assert_awaited_once()


@pytest.mark.asyncio
async def test_restart_visible_relaunches_browser_in_headful_mode():
    manager = PlaywrightBrowserManager()
    manager._headless = True
    manager.stop = AsyncMock()
    manager._start_cdp = AsyncMock()
    playwright = SimpleNamespace(chromium=Mock(), stop=AsyncMock())

    with (
        patch("app.infrastructure.browser.async_playwright") as async_playwright,
        patch("app.infrastructure.browser.settings") as settings,
    ):
        settings.browser_ws_endpoint = ""
        async_playwright.return_value.start = AsyncMock(return_value=playwright)
        await manager.restart_visible()

    assert manager._headless is False
    manager._start_cdp.assert_awaited_once()
