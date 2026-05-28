## Why

当前车型舆情 Agent 存在 10 个核心痛点（详见改造方案 一、当前痛点），集中在三个层面：

1. **数据质量差**：新闻只有 100 字 snippet、评论拼进 content 污染分析、同事件多源重复、关键词手配搜不全
2. **分析能力弱**：22 标签硬贴、无事件/非事件区分、无维度情感、热度只有原始数字、异常无原因
3. **交互体验差**：单车型视角无法对比、下拉列表找车困难、对话回复空泛、无事件脉络追踪

用户需要一个从"数据采集 → 深度分析 → 智能展示"全链路升级的系统，而非局部修补。

## What Changes

- **BREAKING**: 重构分析模型——双模型并行（Qwen3-4B 本地 + GLM-4.7 API），新增 is_event/event_description/dim_sentiment 字段，替换原 22 标签强制分类
- **BREAKING**: 评论独立存储——新增 PostComment 表，MediaCrawler 评论不再拼接进 RawPost.content
- **BREAKING**: 数据库重建——新增 3 表（PostComment、EventGroup、VehicleGroup），修改 6 表字段，开发阶段 drop_all + create_all
- 新增全文抓取：Trafilatura 优先 + Crawl4AI 兜底，新闻帖子抓取全文替代 snippet
- 新增 AI 关键词扩展：LLM 从新闻标题提取扩展关键词，首次采集时扩展一次后续复用
- 新增 SimHash 去重：64 位指纹 Hamming 距离 ≤ 3，替代 URL 级去重
- 新增增量采集：只拉新帖，通过 published_at + platform + URL 判断是否已存在
- 新增小红书短链解析：xhslink.com → HTTP 重定向 → 正则提取 note_id
- 新增评论批处理总结：Top 5 热门帖子（半月窗口，不区分事件/非事件）评论区一次 LLM 调用，输出整体风向
- 新增热度加权：互动烈度改为 likes×1 + comments×5 + shares×10，新增 rank/percentile
- 新增异常根因：异常事件自动查当日事件标签分布，生成一句话解释
- 新增 DBSCAN 事件聚类：同 event_tag 内按时间密度自动分组，7 天半径
- 新增车型分组：VehicleGroup 表 + 分组看板（趋势叠加/情感对比/维度雷达）
- 新增前端搜索优化：可搜索 combobox 替代 select 下拉

## Capabilities

### New Capabilities
- `full-text-crawler`: 两级全文抓取策略（Trafilatura → Crawl4AI → snippet fallback）
- `keyword-expander`: AI 关键词扩展（LLM 从新闻标题提取，首次采集时扩展）
- `deduplication-and-comments`: SimHash 去重 + 评论独立存储 + XHS 短链解析 + 增量采集
- `dual-model-analyzer`: 双模型并行分析管道 + 预定义事件标签池 + 评论批处理总结（半月窗口 Top 5）
- `heat-and-anomaly`: 加权互动烈度 + rank/percentile 标准化 + 异常根因解释
- `event-tracker`: DBSCAN 事件聚类 + EventGroup 表 + 事件时间线 API
- `vehicle-group-and-search`: 车型分组 CRUD + 分组看板 + 可搜索 combobox

### Modified Capabilities
- `analyzer`: 从单模型 22 标签改为双模型并行（sentiment + event 通道分离）
- `heat_calculator`: 互动烈度加权 + SOCIAL_SOURCES 移除 mediacrawler_comment
- `media_crawler`: 评论返回独立列表而非拼接进 content
- `scheduler`: 新增全文爬取/去重/URL解析/评论分离/增量采集步骤
- `dashboard`: 查询过滤重复帖子 + 新增事件时间线端点 + 分组看板端点
- `dialog`: 注入 EventGroup 上下文 + 事件锚点

## Impact

- **数据库**: drop_all + create_all 重建；新增 PostComment、EventGroup、VehicleGroup 表；RawPost 加 full_content/duplicate_group_id；AnalyzedPost 加 is_event/event_description/dim_sentiment/comment_summary；HeatMetric 加 rank/percentile；AnomalyEvent 加 root_cause；Vehicle 加 expanded_keywords
- **Pipeline**: scheduler 时序变为"关键词扩展 → 增量采集 → 全文爬取 → URL解析 → 去重 → 评论分离 → 存储"
- **分析**: analyzer.py 重构为双模型并行；batch_runner.py 新增半月窗口 Top 5 评论批处理
- **前端**: index.html 新增分组下拉/分组视图布局；app.js 新增分组数据/搜索 combobox；style.css 新增分组样式
- **依赖**: 新增 trafilatura、crawl4ai、simhash、scikit-learn、tenacity
- **API**: 新增 /api/groups/* 端点族、事件时间线端点；vehicle.py 新增搜索端点
