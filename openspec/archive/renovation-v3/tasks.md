## Phase 0：基础设施

- [x] 0.1 更新 requirements.txt：新增 trafilatura, crawl4ai, simhash, scikit-learn, tenacity
- [x] 0.2 重建数据库：models/schemas.py 新增 PostComment、EventGroup、VehicleGroup 表；RawPost 加 full_content/duplicate_group_id；AnalyzedPost 加 is_event/event_description/dim_sentiment/comment_summary；HeatMetric 加 rank/percentile；AnomalyEvent 加 root_cause；Vehicle 加 expanded_keywords
- [x] 0.3 验证数据库表自动创建（drop_all + create_all）

## Phase 1：数据采集质量

### 改造 1：全文抓取

- [x] 1.1 新增 pipeline/collectors/full_text_crawler.py：实现 _try_trafilatura() 和 _try_crawl4ai() 和 crawl_full_text()
- [x] 1.2 修改 pipeline/scheduler.py：采集后异步调用 crawl_full_text 抓全文
- [x] 1.3 修改 pipeline/analysis/analyzer.py：分析优先使用 full_content

### 改造 2：关键词扩展

- [x] 2.1 新增 pipeline/collectors/keyword_expander.py：实现 expand_keywords() 函数
- [x] 2.2 修改 pipeline/scheduler.py：采集前检查 expanded_keywords，为空则扩展

### 改造 3：去重 + 评论独立 + URL解析

- [x] 3.1 新增 pipeline/analysis/deduplicator.py：实现 SimHash 去重 deduplicate()
- [x] 3.2 新增 XHS 短链解析：resolve_note_id() 和 _resolve_short_link()
- [x] 3.3 修改 pipeline/collectors/media_crawler.py：评论返回独立列表，不拼进 content
- [x] 3.4 修改 pipeline/scheduler.py：新增去重/URL解析/评论分离步骤；实现 _is_new_post() 增量采集；新增 _store_comments()
- [x] 3.5 修改 pipeline/analysis/heat_calculator.py：移除 mediacrawler_comment 源，改用加权公式

## Phase 2：分析增强

### 改造 4：双模型管道 + 评论分析

- [x] 4.1 修改 pipeline/analysis/analyzer.py：重构为双模型并行（_call_sentiment_model + _call_event_model + asyncio.gather）
- [x] 4.2 新增预定义事件标签池 EVENT_TAG_POOL（17 个标签）
- [x] 4.3 新增 LLM prompt：EVENT_ANALYSIS_PROMPT（事件标注）、SENTIMENT_DIM_PROMPT（情感+维度）、COMMENT_SUMMARY_PROMPT（评论总结）
- [x] 4.4 新增半月窗口计算：get_current_period() + get_boundary_overlap_periods()
- [x] 4.5 修改 pipeline/analysis/batch_runner.py：分析后查 Top 5 → 批处理评论总结

### 改造 5：热度增强 + 异常根因

- [x] 5.1 修改 pipeline/analysis/heat_calculator.py：加权互动烈度 + rank/percentile 计算
- [x] 5.2 新增 pipeline/analysis/anomaly_explainer.py：异常根因解释（查当日 event_tags 分布 + 热门帖子）

## Phase 3：展现与交互

### 改造 6：事件追踪

- [x] 6.1 新增 pipeline/analysis/event_tracker.py：DBSCAN 聚类 cluster_events()
- [x] 6.2 修改 api/routes/dashboard.py：新增事件时间线端点 GET /api/vehicles/{id}/events
- [x] 6.3 新增 EventGroup 摘要生成（LLM 调用）

### 改造 7A：车型分组

- [x] 7.1 新增 api/routes/group.py：分组 CRUD + overview/comparison/trend 端点
- [x] 7.2 修改 api/main.py：注册 group 路由
- [x] 7.3 修改 frontend/index.html：分组下拉 + 分组视图布局
- [x] 7.4 修改 frontend/static/js/app.js：分组数据加载 + 图表渲染 + 模式切换
- [x] 7.5 修改 frontend/static/css/style.css：分组视图样式

### 改造 7B：搜索优化

- [x] 7.6 修改 api/routes/vehicle.py：新增搜索端点 GET /api/vehicles/search
- [x] 7.7 修改 frontend/index.html + app.js + style.css：可搜索 combobox

### 改造 7C：看板对话增强

- [x] 7.8 修改 api/routes/dialog.py：注入 EventGroup 上下文 + 事件锚点
- [x] 7.9 修改 frontend/static/js/dialog.js：事件卡片渲染
