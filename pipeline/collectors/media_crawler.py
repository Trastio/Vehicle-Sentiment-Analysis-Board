import asyncio
import json
import os
from pathlib import Path

MEDIA_CRAWLER_DIR = os.getenv("MEDIA_CRAWLER_DIR", "vendor/MediaCrawler")

PLATFORM_MAP = {
    "xiaohongshu": "xhs", "bilibili": "bili", "zhihu": "zhihu",
    "weibo": "wb", "douyin": "dy", "kuaishou": "ks", "tieba": "tieba",
}


class MediaCrawlerWrapper:
    def __init__(self):
        self._crawler_dir = Path(MEDIA_CRAWLER_DIR)

    def is_available(self) -> bool:
        return (self._crawler_dir / "main.py").exists()

    async def search(self, keyword: str, platform: str, max_notes: int = 20) -> list[dict]:
        platform_code = PLATFORM_MAP.get(platform, platform)
        if not self.is_available():
            return []
        config_path = self._crawler_dir / "config" / "base_config.py"
        if config_path.exists():
            self._update_config(config_path, keyword, max_notes)
        proc = await asyncio.create_subprocess_exec(
            "python", "main.py", "--platform", platform_code, "--lt", "qrcode", "--type", "search",
            cwd=str(self._crawler_dir),
            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
        )
        try:
            await asyncio.wait_for(proc.communicate(), timeout=120)
        except asyncio.TimeoutError:
            proc.kill()
            return []
        return self._read_results(platform_code, keyword)

    def _update_config(self, config_path: Path, keyword: str, max_notes: int):
        content = config_path.read_text(encoding="utf-8")
        lines = []
        for line in content.split("\n"):
            if line.strip().startswith("KEYWORDS"):
                lines.append(f'KEYWORDS = "{keyword}"')
            elif line.strip().startswith("MAX_NOTE_COUNT"):
                lines.append(f"MAX_NOTE_COUNT = {max_notes}")
            else:
                lines.append(line)
        config_path.write_text("\n".join(lines), encoding="utf-8")

    def _read_results(self, platform_code: str, keyword: str) -> list[dict]:
        data_dir = self._crawler_dir / "data"
        if not data_dir.exists():
            return []
        json_file = data_dir / f"{platform_code}_{keyword.replace(' ', '_')}.json"
        if not json_file.exists():
            return []
        with open(json_file, "r", encoding="utf-8") as f:
            data = json.load(f)
        results = []
        if isinstance(data, list):
            for item in data:
                results.append({
                    "title": item.get("title", ""),
                    "content": item.get("desc", item.get("content", "")),
                    "author": item.get("nickname", item.get("author", "")),
                    "url": item.get("note_id", item.get("url", "")),
                    "likes": item.get("liked_count", item.get("likes", 0)),
                    "comments": item.get("comment_count", item.get("comments", 0)),
                    "shares": item.get("share_count", item.get("shares", 0)),
                    "platform": platform_code,
                    "source": "mediacrawler",
                })
        return results
