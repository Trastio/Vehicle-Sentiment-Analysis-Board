"""T1.4 Tests: Cookie Manager."""
import json
import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import patch, MagicMock


def test_load_secrets_missing_file():
    from pipeline.collectors.cookie_manager import CookieManager
    with patch("os.path.exists", return_value=False):
        mgr = CookieManager.__new__(CookieManager)
        mgr._secrets = mgr._load_secrets()
    assert mgr._secrets == {}


def test_load_secrets_valid_file():
    from pipeline.collectors.cookie_manager import CookieManager
    mock_data = '{"baidu": {"username": "test"}}'
    with patch("os.path.exists", return_value=True):
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=mock_data))),
            __exit__=MagicMock(return_value=False),
        ))):
            mgr = CookieManager.__new__(CookieManager)
            mgr._secrets = mgr._load_secrets()
    assert mgr._secrets["baidu"]["username"] == "test"


def test_cache_path_creates_directory():
    from pipeline.collectors.cookie_manager import CookieManager
    mgr = CookieManager.__new__(CookieManager)
    mgr._secrets = {}
    with patch.object(Path, "mkdir") as m:
        mgr._cache_path("baidu")
        m.assert_called_once_with(parents=True, exist_ok=True)


def test_is_cache_valid_no_meta():
    from pipeline.collectors.cookie_manager import CookieManager
    mgr = CookieManager.__new__(CookieManager)
    mgr._secrets = {}
    with patch.object(Path, "exists", return_value=False):
        assert mgr._is_cache_valid("baidu") is False


def test_is_cache_valid_fresh():
    from pipeline.collectors.cookie_manager import CookieManager
    mgr = CookieManager.__new__(CookieManager)
    mgr._secrets = {}
    today = datetime.now().strftime("%Y-%m-%d")
    fresh = (datetime.now() - timedelta(days=1)).isoformat()
    meta = {"login_time": fresh, "login_count_today": 1, "last_login_date": today}
    with patch.object(Path, "exists", return_value=True):
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=json.dumps(meta)))),
            __exit__=MagicMock(return_value=False),
        ))):
            assert mgr._is_cache_valid("baidu") is True


def test_is_cache_valid_expired():
    from pipeline.collectors.cookie_manager import CookieManager
    mgr = CookieManager.__new__(CookieManager)
    mgr._secrets = {}
    old = (datetime.now() - timedelta(days=10)).isoformat()
    meta = {"login_time": old, "login_count_today": 0, "last_login_date": "2000-01-01"}
    with patch.object(Path, "exists", return_value=True):
        with patch("builtins.open", MagicMock(return_value=MagicMock(
            __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value=json.dumps(meta)))),
            __exit__=MagicMock(return_value=False),
        ))):
            assert mgr._is_cache_valid("baidu") is False


def test_get_baidu_cookie_from_cache():
    from pipeline.collectors.cookie_manager import CookieManager
    mgr = CookieManager.__new__(CookieManager)
    mgr._secrets = {}
    with patch.object(mgr, "_is_cache_valid", return_value=True):
        with patch.object(Path, "exists", return_value=True):
            with patch("builtins.open", MagicMock(return_value=MagicMock(
                __enter__=MagicMock(return_value=MagicMock(read=MagicMock(return_value='{"cookie_str":"BAIDUID=abc"}'))),
                __exit__=MagicMock(return_value=False),
            ))):
                assert mgr.get_baidu_cookie() == "BAIDUID=abc"


def test_record_login_increments(tmp_path):
    from pipeline.collectors.cookie_manager import CookieManager
    import pipeline.collectors.cookie_manager as cm_mod
    orig = cm_mod.COOKIE_CACHE_DIR
    cm_mod.COOKIE_CACHE_DIR = str(tmp_path)
    try:
        mgr = CookieManager.__new__(CookieManager)
        mgr._secrets = {}
        today = datetime.now().strftime("%Y-%m-%d")
        meta_path = tmp_path / "baidu_meta.json"
        meta_path.write_text(json.dumps({"login_count_today": 2, "last_login_date": today}))
        mgr._record_login("baidu")
        result = json.loads(meta_path.read_text())
        assert result["login_count_today"] == 3
    finally:
        cm_mod.COOKIE_CACHE_DIR = orig
