## Context

项目是一个车型舆情 Agent，当前架构为 FastAPI + SQLAlchemy + Vue 3 + ECharts。数据通道有 3 条（新闻 Bocha/Anspire、社交媒体 MediaCrawler、百度指数 gopup），分析流程为单次 GLM-4.7 调用输出 sentiment + 22 标签。

核心痛点集中在：
1. 新闻只有 snippet ~100 字，分析精度低
2. 评论拼接进 content 污染分析结果
3. 同事件多来源重复
4. 22 标签强制分类，非事件帖子硬贴标签
5. 热度只有原始数字，异常无原因
6. 单车型视角无法对比
7. 关键词手配覆盖面有限

技术栈约束：
- 后端：Python + FastAPI + SQLAlchemy + SQLite
- LLM：GLM-4-Flash（免费，日常分析）/ GLM-4-Plus（复杂任务） / Qwen3-4B（本地，待部署）
- 前端：Vue 3 CDN + ECharts
- 数据采集：gopup + MediaCrawler + Bocha/Anspire
- 硬件：RTX 4080 12GB VRAM

## Goals / Non-Goals

**Goals:**
- 提升数据质量：全文抓取覆盖 80%+ 新闻、SimHash 去重、评论独立存储
- 提升分析精度：双模型并行、预定义标签池、维度情感、事件/非事件区分
- 提升产品洞察：Top 5 评论批处理总结、异常根因、事件脉络追踪、热度标准化
- 提升交互体验：车型分组对比、可搜索 combobox、事件时间线
- 控制成本：GLM-4-Flash 免费、批处理省 token、增量采集减压力

**Non-Goals:**
- 不做用户认证/权限系统（单用户模式）
- 不做 PDF/Word 导出（后续迭代）
- 不做热榜接入、专题聚合、MCP Server、多通道推送
- 不做报告生成（已推迟，等真实需求）
- 不做全量评论分析（只做 Top 5 半月窗口批处理总结）
- 不做逐条评论情感分析
- 不做水军独立检测模块（批处理总结时自然识别）
- 不做分组数据归一化（标注数量级即可）
- 不做图片内容分析（OCR/多模态成本高）
- 不做微调模型训练（独立项目，本项目只预留接口）

## Decisions

### Decision 1: 双模型分工
**选择**: Qwen3-4B 本地做 sentiment + dim_sentiment；GLM-4.7 API 做 is_event + event_tags + event_description + opinion_tags。两模型并行调用。
**理由**: 本地模型做结构化输出更稳定，API 模型做复杂语义理解更灵活。并行调用无串行延迟。
**过渡期**: Qwen3-4B 未就绪时，GLM-4.7 兼任全部任务。
**替代方案**: 单模型全做——缺少本地推理能力；多 Agent 协作——过度复杂。

### Decision 2: 预定义事件标签池
**选择**: 17 个预定义标签（质量问题/异响故障/安全事故/召回/新车发布/降价促销/交付延迟/提车分享/续航争议/充电问题/智能驾驶事故/OTA升级/维权投诉/售后服务/4S店纠纷/政策法规/行业动态/企业人事变动），LLM 从池中选最多 3 个。
**理由**: 可控可聚合，避免自由提取碎片化。opinion_tags 仍自由提取。
**替代方案**: LLM 自由提取——标签碎片化严重，无法跨帖子聚合。

### Decision 3: 评论批处理总结
**选择**: Top 5 热门帖子（半月窗口，不区分事件/非事件）的评论区做一次 LLM 调用，输出 is_argumentative + genuine_themes + genuine_sentiment + summary。评论数 < 5 跳过。
**理由**: 省 token（30 条逐条 vs 1 次批处理，成本降 ~30 倍），抗噪音（吵架/水军自然过滤），产品价值更高（用户关心整体风向）。
**替代方案**: 逐条评论情感分析——成本高且噪音大。

### Decision 4: 半月窗口 + 边界重叠
**选择**: 固定半月窗口（1-15日 / 16-月末），5 天边界重叠（月末最后 5 天计入下月前半段，月初前 5 天计入当月后半段）。
**理由**: 稳定可预期，边界重叠避免跨窗口事件被拆分。

### Decision 5: SimHash 去重
**选择**: SimHash 64 位指纹，Hamming 距离 ≤ 3。
**理由**: 实现简单（simhash 库一行调用），O(n) 比较，适合近似重复检测。学术上 MinHash 在短文本更优，但 SimHash 足够且已验证。
**替代方案**: Jaccard（原方案）——只适合精确匹配；MinHash——理论更优但实现更复杂。

### Decision 6: DBSCAN 事件聚类
**选择**: 同 event_tag 内按时间戳 DBSCAN 密度聚类，eps=7 天，min_samples=1。
**理由**: 无需预设 K（事件数量不可预知），自动处理噪声点，7 天半径适合汽车行业事件传播周期。
**替代方案**: K-Means——需要预设 K；SBERT + HDBSCAN——需要 embedding 成本，纯时间维度足够。

### Decision 7: 全文抓取两级策略
**选择**: Trafilatura（纯 Python，无浏览器）优先 → Crawl4AI（Playwright）兜底 → snippet fallback。
**理由**: Trafilatura 成功率 80%+ 且轻量；Crawl4AI 处理 SPA/动态页面；snippet 兜底保证不丢数据。

### Decision 8: 增量采集
**选择**: 只拉新帖，通过 published_at + platform + source_url 判断是否已存在。
**理由**: 减少重复采集压力，SimHash 去重兜底。

### Decision 9: 热度加权 + 不归一化
**选择**: 互动烈度 likes×1 + comments×5 + shares×10。跨平台不归一化，标注数量级。时间衰减 score × 0.95^days。
**理由**: 相对权重反映"讨论深度 > 传播广度 > 浅层互动"。归一化引入失真，标注量级更透明。

### Decision 10: DB 重建策略
**选择**: 开发阶段 drop_all + create_all 重建。
**理由**: 6 表改字段 + 3 新表，迁移脚本成本高于重建。生产上线前引入 alembic。

## Risks / Trade-offs

- [Risk] Trafilatura 全文抓取成功率可能低于 80% → Mitigation: Crawl4AI 兜底 + snippet fallback 保证不丢数据
- [Risk] DBSCAN eps=7 天参数可能不适合所有事件类型 → Mitigation: 作为可配置参数，后续实测调优
- [Risk] 预定义标签池可能遗漏新类型事件 → Mitigation: 标签池可扩展，定期根据 opinion_tags 高频词更新
- [Risk] 评论批处理总结在评论区极短时可能无价值 → Mitigation: 评论数 < 5 跳过
- [Risk] GLM-4-Flash 免费版速率限制 → Mitigation: tenacity 指数退避重试，日均调用量远低于限制
- [Trade-off] SimHash vs MinHash：SimHash 实现更简单但短文本精度略低，可接受
- [Trade-off] DBSCAN min_samples=1 意味着单帖子也成簇，可能碎片化 → 后续可调为 2
- [Trade-off] 不归一化导致跨平台热度值差异大 → 标注数量级缓解，如需对比可在 UI 层做平台筛选
