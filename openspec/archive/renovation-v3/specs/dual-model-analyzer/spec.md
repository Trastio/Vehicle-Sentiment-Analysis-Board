## MODIFIED Requirements

### Requirement: 双模型并行分析
`analyzer.py` SHALL 使用双模型并行调用：一个模型负责 sentiment + dim_sentiment，另一个负责 is_event + event_tags + event_description + opinion_tags。两模型通过 `asyncio.gather()` 并行调用，结果合并写入 AnalyzedPost。

#### Scenario: 两个模型均成功
- **WHEN** 双模型并行调用均返回有效结果
- **THEN** 系统 SHALL 合并两个结果写入 AnalyzedPost

#### Scenario: sentiment 模型失败
- **WHEN** sentiment 模型（Qwen3-4B/GLM-4.7）调用失败
- **THEN** 系统 SHALL 保留 event 通道结果，sentiment 相关字段设为默认值

### Requirement: 预定义事件标签池
系统 SHALL 维护 17 个预定义事件标签（质量问题/异响故障/安全事故/召回/新车发布/降价促销/交付延迟/提车分享/续航争议/充电问题/智能驾驶事故/OTA升级/维权投诉/售后服务/4S店纠纷/政策法规/行业动态/企业人事变动），LLM 从池中选最多 3 个。opinion_tags 不受标签池限制，LLM 自由提取。

#### Scenario: 事件帖子的标签
- **WHEN** 帖子涉及刹车异响和维权
- **THEN** event_tags SHALL 为 ["异响/故障", "维权投诉"]（从标签池选择）

#### Scenario: 非事件帖子
- **WHEN** 帖子是日常提车分享
- **THEN** is_event SHALL 为 false，event_tags SHALL 为 []，event_description SHALL 为 ""

### Requirement: GLM-4.7 事件标注 Prompt
GLM-4.7 的事件标注 prompt SHALL 要求 LLM 输出 JSON：`{"is_event": bool, "event_description": str, "event_tags": [str], "opinion_tags": [str], "confidence": float}`。使用智谱 JSON mode + Pydantic 校验兜底。

#### Scenario: JSON 输出合法
- **WHEN** GLM-4.7 返回合法 JSON
- **THEN** 系统 SHALL 用 Pydantic 校验字段类型和取值范围

#### Scenario: JSON 输出非法
- **WHEN** GLM-4.7 返回非法 JSON
- **THEN** 系统 SHALL 使用 tenacity 重试，最多 3 次

### Requirement: sentiment + dim_sentiment 模型
sentiment 通道 SHALL 输出 `{"sentiment": "positive/negative/neutral", "dim_sentiment": {"维度名": 分数}}`。可选维度（-1 到 1）：动力/加速、续航里程、电耗、充电体验、智能化/车机、辅助驾驶/智驾、价格/性价比、舒适性、操控、安全性、内饰、外观、空间、售后服务。未涉及的维度不输出。

#### Scenario: 涉及多维度
- **WHEN** 帖子涉及空间、续航、价格
- **THEN** dim_sentiment SHALL 包含 {"空间": 1, "续航里程": -1, "价格/性价比": 1}，其他维度不出现

## ADDED Requirements

### Requirement: AnalyzedPost 新增字段
AnalyzedPost 表 SHALL 新增：
- `is_event: Column(Boolean, default=False)` — 是否事件相关
- `event_description: Column(Text)` — 自由文本事件描述
- `dim_sentiment: Column(Text)` — 维度情感 JSON
- `comment_summary: Column(Text)` — 评论批处理总结 JSON

### Requirement: 评论批处理总结（半月窗口 Top 5）
系统 SHALL 对半月窗口内 Top 5 热门帖子（按热度分排序，不区分事件/非事件）的评论区做批处理总结。每个帖子取前 30 条评论（按 likes 倒序），评论数 < 5 跳过。输出 JSON：`{"is_argumentative": bool, "argument_detail": str, "genuine_themes": [str], "genuine_sentiment": str, "genuine_sentiment_score": float, "summary": str}`。

#### Scenario: 热门帖子有足够评论
- **WHEN** Top 5 帖子的评论数 ≥ 5
- **THEN** 系统 SHALL 调用 GLM-4.7 做批处理总结，结果存入 `comment_summary`

#### Scenario: 热门帖子评论过少
- **WHEN** 帖子的评论数 < 5
- **THEN** 系统 SHALL 跳过批处理，`comment_summary` 为 null

#### Scenario: 半月窗口边界重叠
- **WHEN** 当前日期在月末最后 5 天
- **THEN** 系统 SHALL 同时将帖子归入下月前半段

### Requirement: 半月窗口计算
系统 SHALL 提供半月窗口计算函数：每月 1-15 日为前半段，16-月末为后半段。5 天边界重叠规则：月末最后 5 天同时计入下月前半段，月初前 5 天同时计入当月后半段。
