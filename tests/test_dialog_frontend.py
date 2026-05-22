"""T3.9.2 Tests: Frontend dialog panel + chart click events — 4 tests."""
import os

import pytest


FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


def test_index_html_contains_dialog_panel():
    with open(os.path.join(FRONTEND_DIR, "index.html"), "r", encoding="utf-8") as f:
        html = f.read()
    assert "dialog-panel" in html
    assert "dialog-overlay" in html
    assert "dialog-messages" in html
    assert "dialog-input" in html


def test_dialog_js_exists():
    path = os.path.join(FRONTEND_DIR, "static", "js", "dialog.js")
    assert os.path.exists(path)


def test_dialog_js_has_methods():
    path = os.path.join(FRONTEND_DIR, "static", "js", "dialog.js")
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    assert "openDialog" in source
    assert "closeDialog" in source
    assert "sendDialogMessage" not in source or "parseGenerativeUI" in source
    assert "parseGenerativeUI" in source


def test_app_js_has_chart_click_handlers():
    path = os.path.join(FRONTEND_DIR, "static", "js", "app.js")
    with open(path, "r", encoding="utf-8") as f:
        source = f.read()
    assert "getZr" in source or "bindChartClick" in source
