# -*- coding: utf-8 -*-
from loguru import logger
from db.database import get_connection


def init_database():
    conn = None
    try:
        conn = get_connection()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sentiment_data (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_model TEXT NOT NULL,
                platform TEXT NOT NULL,
                title TEXT,
                content TEXT NOT NULL,
                author TEXT,
                publish_time DATETIME,
                url TEXT,
                like_count INTEGER DEFAULT 0,
                comment_count INTEGER DEFAULT 0,
                share_count INTEGER DEFAULT 0,
                view_count INTEGER DEFAULT 0,
                sentiment_label TEXT,
                sentiment_score REAL,
                keywords TEXT,
                crawl_time DATETIME DEFAULT CURRENT_TIMESTAMP,
                source TEXT DEFAULT 'api',
                UNIQUE(url, car_model)
            );

            CREATE INDEX IF NOT EXISTS idx_sentiment_car_model ON sentiment_data(car_model);
            CREATE INDEX IF NOT EXISTS idx_sentiment_platform ON sentiment_data(platform);
            CREATE INDEX IF NOT EXISTS idx_sentiment_time ON sentiment_data(publish_time);

            CREATE TABLE IF NOT EXISTS monitor_tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                car_model TEXT NOT NULL UNIQUE,
                status TEXT DEFAULT 'active',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                last_crawl_time DATETIME
            );

            CREATE TABLE IF NOT EXISTS conversations (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL DEFAULT '',
                car_model TEXT DEFAULT '',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                conversation_id TEXT NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system')),
                content TEXT NOT NULL DEFAULT '',
                message_type TEXT NOT NULL DEFAULT 'text' CHECK(message_type IN ('text', 'visual_report', 'opinion_report', 'progress', 'error')),
                metadata TEXT DEFAULT '{}',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (conversation_id) REFERENCES conversations(id)
            );

            CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
            CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at);
            CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at);
        """)
        conn.commit()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        raise
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    init_database()
