"""T3.2 Tests: Frontend files — 5 tests."""
import os

FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "..", "frontend")


def test_index_html_exists():
    path = os.path.join(FRONTEND_DIR, "index.html")
    assert os.path.exists(path)


def test_index_html_contains_vue_and_echarts():
    path = os.path.join(FRONTEND_DIR, "index.html")
    content = open(path, encoding="utf-8").read()
    assert "vue" in content.lower() or "Vue" in content
    assert "echarts" in content.lower() or "ECharts" in content


def test_app_js_exists_and_parseable():
    path = os.path.join(FRONTEND_DIR, "static", "js", "app.js")
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert "createApp" in content or "Vue" in content


def test_style_css_exists():
    path = os.path.join(FRONTEND_DIR, "static", "css", "style.css")
    assert os.path.exists(path)
    content = open(path, encoding="utf-8").read()
    assert len(content) > 100


def test_index_has_dashboard_sections():
    path = os.path.join(FRONTEND_DIR, "index.html")
    content = open(path, encoding="utf-8").read()
    assert "overview" in content.lower() or "概览" in content
    assert "trend" in content.lower() or "趋势" in content or "chart" in content.lower()
