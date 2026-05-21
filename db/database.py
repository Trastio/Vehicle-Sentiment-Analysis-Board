# -*- coding: utf-8 -*-
import sqlite3
from pathlib import Path
from typing import List, Dict, Any, Optional
from loguru import logger
from config import settings


def get_db_path() -> str:
    db_path = Path(settings.DB_PATH)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return str(db_path)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(get_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def execute_query(sql: str, params: tuple = ()) -> List[Dict[str, Any]]:
    conn = None
    try:
        conn = get_connection()
        cursor = conn.execute(sql, params)
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    except Exception as e:
        logger.error(f"数据库查询错误: {e}")
        return []
    finally:
        if conn:
            conn.close()


def execute_update(sql: str, params: tuple = ()) -> int:
    conn = None
    try:
        conn = get_connection()
        cursor = conn.execute(sql, params)
        conn.commit()
        return cursor.lastrowid
    except Exception as e:
        logger.error(f"数据库更新错误: {e}")
        if conn:
            conn.rollback()
        return -1
    finally:
        if conn:
            conn.close()


def insert_sentiment_data(data: Dict[str, Any]) -> int:
    sql = """
    INSERT OR IGNORE INTO sentiment_data
    (car_model, platform, title, content, author, publish_time, url,
     like_count, comment_count, share_count, view_count, source)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """
    return execute_update(sql, (
        data.get("car_model", ""),
        data.get("platform", ""),
        data.get("title", ""),
        data.get("content", ""),
        data.get("author", ""),
        data.get("publish_time"),
        data.get("url", ""),
        data.get("like_count", 0),
        data.get("comment_count", 0),
        data.get("share_count", 0),
        data.get("view_count", 0),
        data.get("source", "api"),
    ))


def delete_sentiment_data(car_model: str, source: str = None) -> int:
    if source:
        sql = "DELETE FROM sentiment_data WHERE car_model = ? AND source = ?"
        return execute_update(sql, (car_model, source))
    else:
        sql = "DELETE FROM sentiment_data WHERE car_model = ?"
        return execute_update(sql, (car_model,))


def query_sentiment_data(car_model: str, platform: str = None, limit: int = 200) -> List[Dict[str, Any]]:
    if platform:
        sql = """
        SELECT * FROM sentiment_data
        WHERE car_model = ? AND platform = ?
        ORDER BY publish_time DESC LIMIT ?
        """
        return execute_query(sql, (car_model, platform, limit))
    else:
        sql = """
        SELECT * FROM sentiment_data
        WHERE car_model = ?
        ORDER BY publish_time DESC LIMIT ?
        """
        return execute_query(sql, (car_model, limit))
