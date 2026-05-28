"""Tests: MediaCrawler Wrapper."""
import asyncio
import json
import pytest
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, call, patch

from pipeline.collectors.media_crawler import MediaCrawlerWrapper, PLATFORM_MAP, DATA_DIR_MAP


def _no_init(self):
    pass


class TestIsAvailable:
    def test_available_when_main_exists(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")
            assert c.is_available() is True

    def test_not_available_when_main_missing(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            assert c.is_available() is False


class TestNormalizeItem:
    def test_extracts_all_fields(self):
        raw = {
            "title": "海豹用车体验",
            "desc": "开了三个月很满意",
            "nickname": "车主小王",
            "note_url": "https://xhs.com/note/123",
            "liked_count": 42,
            "comment_count": 5,
            "share_count": 3,
            "time": 1748217600000,
        }
        result = MediaCrawlerWrapper._normalize_item(raw, "xhs")
        assert result["title"] == "海豹用车体验"
        assert result["content"] == "开了三个月很满意"
        assert result["author"] == "车主小王"
        assert result["url"] == "https://xhs.com/note/123"
        assert result["likes"] == 42
        assert result["comments"] == 5
        assert result["shares"] == 3
        assert result["platform"] == "xhs"
        assert result["source"] == "mediacrawler"
        assert result["published_at"] == "2025-05-26T00:00:00"

    def test_string_counts_converted_to_int(self):
        raw = {
            "liked_count": "2670",
            "comment_count": "215",
            "share_count": "1699",
        }
        result = MediaCrawlerWrapper._normalize_item(raw, "xhs")
        assert result["likes"] == 2670
        assert result["comments"] == 215
        assert result["shares"] == 1699

    def test_empty_string_counts_become_zero(self):
        raw = {"liked_count": "", "comment_count": None}
        result = MediaCrawlerWrapper._normalize_item(raw, "xhs")
        assert result["likes"] == 0
        assert result["comments"] == 0

    def test_fallback_fields(self):
        raw = {"content": "text", "author": "test", "url": "http://x.com"}
        result = MediaCrawlerWrapper._normalize_item(raw, "dy")
        assert result["content"] == "text"
        assert result["title"] == "text"

    def test_title_fallback_from_content_when_empty(self):
        raw = {"content": "这是一条微博帖子的完整内容，比较长", "author": "user1", "note_url": "http://weibo.cn/detail/123"}
        result = MediaCrawlerWrapper._normalize_item(raw, "wb")
        assert result["title"] == "这是一条微博帖子的完整内容，比较长"

    def test_title_not_overridden_when_present(self):
        raw = {"title": "已有标题", "content": "内容更长一些", "nickname": "u"}
        result = MediaCrawlerWrapper._normalize_item(raw, "xhs")
        assert result["title"] == "已有标题"

    def test_title_fallback_truncates_long_content(self):
        raw = {"content": "a" * 200, "nickname": "u"}
        result = MediaCrawlerWrapper._normalize_item(raw, "wb")
        assert len(result["title"]) <= 43
        assert result["title"].startswith("a" * 40)

    def test_xhs_extracts_time_field(self):
        result = MediaCrawlerWrapper._normalize_item({"time": 1748217600000}, "xhs")
        assert result["published_at"] == "2025-05-26T00:00:00"

    def test_douyin_extracts_create_time(self):
        result = MediaCrawlerWrapper._normalize_item({"create_time": 1748217600}, "dy")
        assert result["published_at"] == "2025-05-26T00:00:00"

    def test_kuaishou_extracts_create_time(self):
        result = MediaCrawlerWrapper._normalize_item({"create_time": 1748217600}, "ks")
        assert result["published_at"] == "2025-05-26T00:00:00"

    def test_weibo_extracts_create_time(self):
        result = MediaCrawlerWrapper._normalize_item({"create_time": 1748217600}, "wb")
        assert result["published_at"] == "2025-05-26T00:00:00"

    def test_no_time_returns_empty_string(self):
        result = MediaCrawlerWrapper._normalize_item({}, "xhs")
        assert result["published_at"] == ""

    def test_invalid_time_returns_empty_string(self):
        result = MediaCrawlerWrapper._normalize_item({"time": "not_a_number"}, "xhs")
        assert result["published_at"] == ""


class TestReadResults:
    def test_reads_jsonl(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            jsonl_dir = tmp_path / "data" / "xhs" / "jsonl"
            jsonl_dir.mkdir(parents=True)
            items = [
                {"title": "A", "desc": "a", "nickname": "u1", "note_url": "http://1", "liked_count": 1, "comment_count": 0, "share_count": 0},
                {"title": "B", "desc": "b", "nickname": "u2", "note_url": "http://2", "liked_count": 2, "comment_count": 0, "share_count": 0},
            ]
            (jsonl_dir / "search_contents_2026-05-25.jsonl").write_text(
                "\n".join(json.dumps(i, ensure_ascii=False) for i in items),
                encoding="utf-8",
            )
            results = c._read_results("xhs", "海豹")
        assert len(results) == 2
        assert results[0]["title"] == "A"
        assert results[1]["platform"] == "xhs"

    def test_empty_dir_returns_empty(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            assert c._read_results("xhs", "海豹") == []

    def test_skips_invalid_json(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            jsonl_dir = tmp_path / "data" / "xhs" / "jsonl"
            jsonl_dir.mkdir(parents=True)
            (jsonl_dir / "search_contents_2026-05-25.jsonl").write_text(
                "not json\n{\"title\":\"ok\"}\n\n", encoding="utf-8",
            )
            results = c._read_results("xhs", "海豹")
        assert len(results) == 1
        assert results[0]["title"] == "ok"


class TestComments:
    def test_enrich_post_with_top_comments(self):
        posts = [{"url": "http://xhs.com/note/123", "content": "原内容"}]
        comments = {"123": [
            {"content": "好车", "like_count": 10, "nickname": "u1"},
            {"content": "不错", "like_count": 5, "nickname": "u2"},
        ]}
        result = MediaCrawlerWrapper._enrich_with_comments(posts, comments)
        assert "[热门评论]" in result[0]["content"]
        assert "好车" in result[0]["content"]

    def test_no_enrichment_when_no_comments(self):
        posts = [{"url": "http://xhs.com/note/123", "content": "原内容"}]
        result = MediaCrawlerWrapper._enrich_with_comments(posts, {})
        assert result[0]["content"] == "原内容"

    def test_orphan_comments_created(self):
        posts = [{"url": "http://xhs.com/note/111", "content": "x"}]
        comments = {"222": [
            {"content": "孤立评论", "nickname": "u1", "comment_id": "c1", "like_count": 3, "create_time": 1748217600},
        ]}
        orphans = MediaCrawlerWrapper._orphan_comments(posts, comments, "xhs")
        assert len(orphans) == 1
        assert orphans[0]["content"] == "孤立评论"
        assert orphans[0]["source"] == "mediacrawler_comment"
        assert orphans[0]["published_at"] == "2025-05-26T00:00:00"

    def test_orphan_comments_no_time(self):
        posts = [{"url": "http://xhs.com/note/111", "content": "x"}]
        comments = {"222": [
            {"content": "无时间评论", "nickname": "u1", "comment_id": "c1", "like_count": 0},
        ]}
        orphans = MediaCrawlerWrapper._orphan_comments(posts, comments, "xhs")
        assert orphans[0]["published_at"] == ""

    def test_no_orphan_when_comment_matched(self):
        posts = [{"url": "http://xhs.com/note/111", "content": "x"}]
        comments = {"111": [
            {"content": "匹配评论", "nickname": "u1", "comment_id": "c1", "like_count": 0},
        ]}
        orphans = MediaCrawlerWrapper._orphan_comments(posts, comments, "xhs")
        assert len(orphans) == 0

    def test_read_comments_from_jsonl(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            jsonl_dir = tmp_path / "data" / "xhs" / "jsonl"
            jsonl_dir.mkdir(parents=True)
            (jsonl_dir / "search_comments_2026-05-25.jsonl").write_text(
                '{"note_id":"n1","content":"好车","nickname":"u1","like_count":5,"comment_id":"c1"}\n'
                '{"note_id":"n1","content":"不错","nickname":"u2","like_count":3,"comment_id":"c2"}\n',
                encoding="utf-8",
            )
            comments = c._read_comments("xhs")
        assert "n1" in comments
        assert len(comments["n1"]) == 2

    def test_read_comments_empty_dir(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            assert c._read_comments("xhs") == {}


class TestExtractComments:
    def test_returns_separate_list(self):
        posts = [{"url": "https://www.xiaohongshu.com/explore/abc123"}]
        raw_comments = {
            "abc123": [
                {"content": "多少钱落地", "nickname": "网友A", "like_count": 5},
                {"content": "我也想买", "nickname": "网友B", "like_count": 2},
            ]
        }
        result = MediaCrawlerWrapper._extract_comments(posts, raw_comments, "xhs")
        assert len(result) == 2
        assert result[0]["content"] == "多少钱落地"
        assert result[0]["author"] == "网友A"
        assert result[0]["platform"] == "xhs"
        assert result[0]["post_note_id"] == "abc123"
        assert result[0]["post_url"] == "https://www.xiaohongshu.com/explore/abc123"
        assert result[0]["likes"] == 5
        assert result[1]["content"] == "我也想买"

    def test_skips_empty_content(self):
        posts = [{"url": "https://www.xiaohongshu.com/explore/abc123"}]
        raw_comments = {
            "abc123": [
                {"content": "", "nickname": "网友A", "like_count": 0},
                {"content": "有效评论", "nickname": "网友B", "like_count": 1},
            ]
        }
        result = MediaCrawlerWrapper._extract_comments(posts, raw_comments, "xhs")
        assert len(result) == 1
        assert result[0]["content"] == "有效评论"

    def test_no_comments_for_post(self):
        posts = [{"url": "https://www.xiaohongshu.com/explore/abc123"}]
        raw_comments = {"other_id": [{"content": "不相关", "nickname": "u"}]}
        result = MediaCrawlerWrapper._extract_comments(posts, raw_comments, "xhs")
        assert result == []

    def test_empty_posts_returns_empty(self):
        result = MediaCrawlerWrapper._extract_comments([], {"abc": [{"content": "x"}]}, "xhs")
        assert result == []

    def test_handles_none_like_count(self):
        posts = [{"url": "https://www.xiaohongshu.com/explore/abc123"}]
        raw_comments = {
            "abc123": [
                {"content": "评论", "nickname": "u", "like_count": None},
            ]
        }
        result = MediaCrawlerWrapper._extract_comments(posts, raw_comments, "xhs")
        assert len(result) == 1
        assert result[0]["likes"] == 0

    def test_handles_missing_like_count(self):
        posts = [{"url": "https://www.xiaohongshu.com/explore/abc123"}]
        raw_comments = {
            "abc123": [
                {"content": "评论", "nickname": "u"},
            ]
        }
        result = MediaCrawlerWrapper._extract_comments(posts, raw_comments, "xhs")
        assert len(result) == 1
        assert result[0]["likes"] == 0


class TestReadResultsNoCommentEnrich:
    def test_reads_without_comment_enrichment(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            jsonl_dir = tmp_path / "data" / "xhs" / "jsonl"
            jsonl_dir.mkdir(parents=True)
            (jsonl_dir / "search_contents_2026-05-25.jsonl").write_text(
                json.dumps({"title": "海豚提车", "desc": "提车一周感受", "nickname": "车主",
                            "note_url": "http://xhs.com/abc123", "liked_count": 10}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            # Also write a comment file — it should NOT be read
            (jsonl_dir / "search_comments_2026-05-25.jsonl").write_text(
                json.dumps({"note_id": "abc123", "content": "多少钱", "nickname": "u"}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            results = c._read_results_no_comment_enrich("xhs", "海豚")
        assert len(results) == 1
        assert results[0]["title"] == "海豚提车"
        # Content should NOT have [热门评论] appended
        assert "[热门评论]" not in results[0]["content"]

    def test_empty_dir_returns_empty(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            assert c._read_results_no_comment_enrich("xhs", "test") == []

    def test_does_not_filter_dealer_posts(self, tmp_path):
        """Dealer filtering should NOT happen in _read_results_no_comment_enrich (done by caller)."""
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            jsonl_dir = tmp_path / "data" / "xhs" / "jsonl"
            jsonl_dir.mkdir(parents=True)
            (jsonl_dir / "search_contents_2026-05-25.jsonl").write_text(
                json.dumps({"title": "优惠报价", "desc": "促销", "nickname": "比亚迪海洋4S店",
                            "note_url": "http://1", "liked_count": 5}, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            results = c._read_results_no_comment_enrich("xhs", "test")
        assert len(results) == 1
        assert results[0]["author"] == "比亚迪海洋4S店"


class TestSearchWithComments:
    @pytest.mark.asyncio
    async def test_returns_empty_when_not_available(self):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = Path("/nonexistent")
            posts, comments = await c.search_with_comments("海豹", "xiaohongshu")
        assert posts == []
        assert comments == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_bad_platform(self):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = Path("/some/dir")
            posts, comments = await c.search_with_comments("海豹", "bad_platform")
        assert posts == []
        assert comments == []

    @pytest.mark.asyncio
    async def test_returns_posts_and_comments_separately(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")

            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            with patch("pipeline.collectors.media_crawler.asyncio.create_subprocess_exec", return_value=mock_proc):
                with patch.object(c, "_read_results_no_comment_enrich", return_value=[
                    {"title": "海豚提车", "content": "提车一周感受", "url": "https://www.xiaohongshu.com/explore/abc123",
                     "source": "mediacrawler", "platform": "xhs", "author": "车主"},
                ]):
                    with patch.object(c, "_read_comments", return_value={
                        "abc123": [{"content": "多少钱落地", "nickname": "网友A", "like_count": 5}],
                    }):
                        posts, comments = await c.search_with_comments("海豚", "xiaohongshu")
        assert len(posts) == 1
        assert "[热门评论]" not in posts[0]["content"]
        assert len(comments) == 1
        assert comments[0]["content"] == "多少钱落地"
        assert comments[0]["post_note_id"] == "abc123"

    @pytest.mark.asyncio
    async def test_filters_dealer_posts(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")

            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            with patch("pipeline.collectors.media_crawler.asyncio.create_subprocess_exec", return_value=mock_proc):
                with patch.object(c, "_read_results_no_comment_enrich", return_value=[
                    {"title": "海豚体验", "content": "不错", "url": "http://1",
                     "source": "mediacrawler", "platform": "xhs", "author": "车主小王"},
                    {"title": "优惠", "content": "促销", "url": "http://2",
                     "source": "mediacrawler", "platform": "xhs", "author": "比亚迪海洋4S店"},
                ]):
                    with patch.object(c, "_read_comments", return_value={}):
                        posts, comments = await c.search_with_comments("海豚", "xiaohongshu")
        assert len(posts) == 1
        assert posts[0]["author"] == "车主小王"

    @pytest.mark.asyncio
    async def test_returns_empty_on_nonzero_returncode(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")

            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_proc.returncode = 1
            with patch("pipeline.collectors.media_crawler.asyncio.create_subprocess_exec", return_value=mock_proc):
                posts, comments = await c.search_with_comments("海豹", "xiaohongshu")
        assert posts == []
        assert comments == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_timeout(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")

            mock_proc = AsyncMock()
            mock_proc.kill = MagicMock()
            with patch("pipeline.collectors.media_crawler.asyncio.create_subprocess_exec", return_value=mock_proc):
                with patch("pipeline.collectors.media_crawler.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                    posts, comments = await c.search_with_comments("海豹", "xiaohongshu")
        assert posts == []
        assert comments == []
        mock_proc.kill.assert_called_once()


class TestDealerFilter:
    def test_filters_4s_shop(self):
        post = {"author": "比亚迪海洋4S店", "title": "优惠", "content": "x"}
        assert MediaCrawlerWrapper._is_dealer_post(post) is True

    def test_filters_dealer_in_author(self):
        post = {"author": "长安体验中心", "title": "test", "content": "x"}
        assert MediaCrawlerWrapper._is_dealer_post(post) is True

    def test_passes_normal_user(self):
        post = {"author": "车主小王", "title": "海豹真实感受", "content": "开了三个月"}
        assert MediaCrawlerWrapper._is_dealer_post(post) is False

    def test_filters_4s_promo_title(self):
        post = {"author": "某用户", "title": "4S店海豹优惠报价", "content": "x"}
        assert MediaCrawlerWrapper._is_dealer_post(post) is True

    def test_passes_title_with_4s_but_not_promo(self):
        post = {"author": "用户", "title": "4S店保养体验", "content": "去保养了"}
        assert MediaCrawlerWrapper._is_dealer_post(post) is False

    def test_filters_brand_dealer_name_shop(self):
        post = {"author": "比亚迪乾元新景湘潭九华店", "title": "新车上市", "content": "x"}
        assert MediaCrawlerWrapper._is_dealer_post(post) is True

    def test_filters_brand_dealer_name_auto(self):
        post = {"author": "长安鑫达汽车", "title": "优惠", "content": "x"}
        assert MediaCrawlerWrapper._is_dealer_post(post) is True

    def test_passes_normal_user_with_similar_name(self):
        post = {"author": "比亚迪车主", "title": "真实感受", "content": "开了半年"}
        assert MediaCrawlerWrapper._is_dealer_post(post) is False


class TestSearch:
    @pytest.mark.asyncio
    async def test_returns_empty_when_not_available(self):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = Path("/nonexistent")
            result = await c.search("海豹", "xiaohongshu")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_bad_platform(self):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = Path("/some/dir")
            result = await c.search("海豹", "bad_platform")
        assert result == []

    @pytest.mark.asyncio
    async def test_calls_subprocess_and_reads_results(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")

            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            with patch("pipeline.collectors.media_crawler.asyncio.create_subprocess_exec", return_value=mock_proc):
                with patch.object(c, "_read_results", return_value=[
                    {"title": "A", "source": "mediacrawler", "platform": "xhs"},
                ]):
                    result = await c.search("海豹", "xiaohongshu")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_subprocess_receives_get_comment_true(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")

            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b""))
            mock_proc.returncode = 0
            with patch("pipeline.collectors.media_crawler.asyncio.create_subprocess_exec", return_value=mock_proc) as mock_exec:
                with patch.object(c, "_read_results", return_value=[]):
                    await c.search("比亚迪海豹", "douyin")
        args = mock_exec.call_args[0]
        cmd = list(args)
        idx = cmd.index("--get_comment")
        assert cmd[idx + 1] == "true"

    @pytest.mark.asyncio
    async def test_returns_empty_on_nonzero_returncode(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")

            mock_proc = AsyncMock()
            mock_proc.communicate = AsyncMock(return_value=(b"", b"error"))
            mock_proc.returncode = 1
            with patch("pipeline.collectors.media_crawler.asyncio.create_subprocess_exec", return_value=mock_proc):
                result = await c.search("海豹", "xiaohongshu")
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_empty_on_timeout(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            (tmp_path / "main.py").write_text("")

            mock_proc = AsyncMock()
            mock_proc.kill = MagicMock()
            with patch("pipeline.collectors.media_crawler.asyncio.create_subprocess_exec", return_value=mock_proc):
                with patch("pipeline.collectors.media_crawler.asyncio.wait_for", side_effect=asyncio.TimeoutError()):
                    result = await c.search("海豹", "xiaohongshu")
        assert result == []
        mock_proc.kill.assert_called_once()


def test_platform_map():
    assert PLATFORM_MAP["xiaohongshu"] == "xhs"
    assert PLATFORM_MAP["weibo"] == "wb"
    assert PLATFORM_MAP["douyin"] == "dy"
    assert PLATFORM_MAP["kuaishou"] == "ks"
    assert "bilibili" not in PLATFORM_MAP
    assert "tieba" not in PLATFORM_MAP
    assert "zhihu" not in PLATFORM_MAP


def test_data_dir_map_short_to_full():
    assert DATA_DIR_MAP["dy"] == "douyin"
    assert DATA_DIR_MAP["ks"] == "kuaishou"
    assert DATA_DIR_MAP["xhs"] == "xhs"
    assert DATA_DIR_MAP["wb"] == "weibo"
    assert "bili" not in DATA_DIR_MAP


class TestReadResultsWithDirMap:
    def test_reads_douyin_from_full_dir_name(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            jsonl_dir = tmp_path / "data" / "douyin" / "jsonl"
            jsonl_dir.mkdir(parents=True)
            (jsonl_dir / "search_contents_2026-05-25.jsonl").write_text(
                '{"title":"dy video","desc":"content","nickname":"user","liked_count":"100"}\n',
                encoding="utf-8",
            )
            results = c._read_results("dy", "test")
        assert len(results) == 1
        assert results[0]["platform"] == "dy"
        assert results[0]["likes"] == 100

    def test_reads_kuaishou_from_full_dir_name(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            jsonl_dir = tmp_path / "data" / "kuaishou" / "jsonl"
            jsonl_dir.mkdir(parents=True)
            (jsonl_dir / "search_contents_2026-05-25.jsonl").write_text(
                '{"title":"ks video","desc":"content","nickname":"user","liked_count":"50"}\n',
                encoding="utf-8",
            )
            results = c._read_results("ks", "test")
        assert len(results) == 1
        assert results[0]["platform"] == "ks"

    def test_filters_dealer_posts(self, tmp_path):
        with patch.object(MediaCrawlerWrapper, "__init__", _no_init):
            c = MediaCrawlerWrapper()
            c._crawler_dir = tmp_path
            jsonl_dir = tmp_path / "data" / "xhs" / "jsonl"
            jsonl_dir.mkdir(parents=True)
            items = [
                {"title": "海豹体验", "desc": "不错", "nickname": "车主小王", "note_url": "http://1", "liked_count": 1},
                {"title": "优惠报价", "desc": "促销", "nickname": "比亚迪海洋4S店", "note_url": "http://2", "liked_count": 5},
            ]
            (jsonl_dir / "search_contents_2026-05-25.jsonl").write_text(
                "\n".join(json.dumps(i, ensure_ascii=False) for i in items),
                encoding="utf-8",
            )
            results = c._read_results("xhs", "海豹")
        assert len(results) == 1
        assert results[0]["author"] == "车主小王"
