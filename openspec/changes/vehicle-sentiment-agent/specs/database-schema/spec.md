## Module: database-schema

SQLite 数据库重构，新增车型管理、采集状态、热度指标、异常事件、报告存储等表。

### Tables

```sql
-- 车型管理
CREATE TABLE vehicles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    brand TEXT NOT NULL,
    search_keywords TEXT,           -- JSON 数组
    lifecycle_anchors TEXT,         -- JSON
    competitor_ids TEXT,            -- JSON 数组
    status TEXT DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 采集状态
CREATE TABLE collection_status (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT REFERENCES vehicles(id),
    source TEXT NOT NULL,
    mode TEXT NOT NULL,
    last_collected_at TIMESTAMP,
    posts_collected INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending',
    error_message TEXT,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 原始帖子
CREATE TABLE raw_posts (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT REFERENCES vehicles(id),
    source TEXT NOT NULL,           -- 平台来源
    platform TEXT,                  -- weibo/xiaohongshu/bilibili/zhihu/douyin/news/...
    title TEXT,
    content TEXT NOT NULL,
    author TEXT,
    url TEXT,
    published_at TIMESTAMP,
    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    likes INTEGER DEFAULT 0,
    comments INTEGER DEFAULT 0,
    shares INTEGER DEFAULT 0,
    analysis_status TEXT DEFAULT 'pending'  -- pending | analyzed | needs_review
);

-- 分析结果
CREATE TABLE analyzed_posts (
    id TEXT PRIMARY KEY,
    post_id TEXT REFERENCES raw_posts(id),
    vehicle_id TEXT REFERENCES vehicles(id),
    sentiment TEXT NOT NULL,        -- positive | negative | neutral
    event_tags TEXT,                -- JSON 数组
    opinion_tags TEXT,              -- JSON 数组
    confidence REAL,                -- 0.0-1.0
    analyzed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    model_used TEXT                 -- qwen3-4b | deepseek-v4-flash
);

-- 热度指标
CREATE TABLE heat_metrics (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT REFERENCES vehicles(id),
    date DATE NOT NULL,
    attention_index REAL,           -- 注意力指数（百度/微博/头条指数均值）
    discussion_volume INTEGER,      -- 讨论声量（帖子数）
    media_volume INTEGER,           -- 媒体声量（新闻数）
    interaction_intensity REAL,     -- 互动烈度（归一化 0-100）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vehicle_id, date)
);

-- 异常事件
CREATE TABLE anomaly_events (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT REFERENCES vehicles(id),
    date DATE NOT NULL,
    volume_change_rate REAL,        -- 声量变化率
    today_volume REAL,
    yesterday_volume REAL,
    event_type TEXT,                 -- spike | drop
    sentiment_shift TEXT,            -- JSON: 情感分布变化
    top_posts TEXT,                  -- JSON: 代表性帖子 ID 列表
    brief_generated BOOLEAN DEFAULT FALSE,
    report_generated BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(vehicle_id, date)
);

-- 报告
CREATE TABLE reports (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT REFERENCES vehicles(id),
    type TEXT NOT NULL,              -- brief | deep
    anomaly_event_id TEXT REFERENCES anomaly_events(id),
    title TEXT,
    content TEXT NOT NULL,           -- Markdown 或 HTML
    time_range_start DATE,
    time_range_end DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 对话历史
CREATE TABLE dialog_conversations (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT REFERENCES vehicles(id),
    anchor_type TEXT,                -- trend | platform | event | opinion | anomaly | post
    anchor_data TEXT,                -- JSON: 锚点上下文数据
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE dialog_messages (
    id TEXT PRIMARY KEY,
    conversation_id TEXT REFERENCES dialog_conversations(id),
    role TEXT NOT NULL,              -- user | assistant
    content TEXT NOT NULL,
    generative_ui TEXT,              -- JSON: Generative UI 指令
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### Indexes
```sql
CREATE INDEX idx_raw_posts_vehicle_date ON raw_posts(vehicle_id, published_at);
CREATE INDEX idx_analyzed_posts_vehicle ON analyzed_posts(vehicle_id);
CREATE INDEX idx_heat_metrics_vehicle_date ON heat_metrics(vehicle_id, date);
CREATE INDEX idx_anomaly_events_vehicle_date ON anomaly_events(vehicle_id, date);
CREATE INDEX idx_dialog_messages_conversation ON dialog_messages(conversation_id);
```
