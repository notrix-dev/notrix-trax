from __future__ import annotations

from trax.cli import theme


def test_theme_helpers_return_plain_text_when_color_disabled(monkeypatch) -> None:
    monkeypatch.setenv("NO_COLOR", "1")

    assert theme.style_status("completed") == "completed"
    assert theme.style_diff_kind("ADDED") == "ADDED"
    assert theme.style_step_name("retrieval:query", "retrieval") == "retrieval:query"
    assert theme.style_safety_level("safe_read") == "safe_read"
    assert theme.style_header("Run") == "Run:"


def test_theme_helpers_emit_ansi_when_color_enabled(monkeypatch) -> None:
    monkeypatch.delenv("NO_COLOR", raising=False)
    monkeypatch.setattr(theme.sys.stdout, "isatty", lambda: True)

    assert "\033[" in theme.style_status("completed")
    assert "\033[" in theme.style_diff_kind("MODIFIED")
    assert "\033[" in theme.style_step_name("llm:call", "llm")
    assert "\033[" in theme.style_safety_level("unsafe_write")
    assert "\033[" in theme.style_header("Run")
