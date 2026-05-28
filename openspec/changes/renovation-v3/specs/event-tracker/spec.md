## ADDED Requirements

### Requirement: DBSCAN 事件聚类
系统 SHALL 对已分析的帖子按 event_tag 分桶后，使用 DBSCAN 密度聚类按时间戳自动分组。eps=7 天，min_samples=1。同组的帖子归入同一个 EventGroup。

#### Scenario: 同一事件的多篇报道
- **WHEN** 7 天内有 3 篇帖子都标记了 "维权投诉" 标签
- **THEN** 系统 SHALL 将 3 篇帖子归入同一 EventGroup

#### Scenario: 跨月的不同事件
- **WHEN** 两个月前有 "维权投诉" 帖子，本月又有 "维权投诉" 帖子，间隔 > 7 天
- **THEN** 系统 SHALL 归入两个不同的 EventGroup

#### Scenario: 帖子有多个 event_tag
- **WHEN** 帖子有 event_tags=["异响/故障", "维权投诉"]
- **THEN** 系统 SHALL 将帖子分别归入 "异响/故障" 和 "维权投诉" 对应的 EventGroup

### Requirement: EventGroup 表
系统 SHALL 新增 EventGroup 表，字段：id, vehicle_id, event_tag, start_date, end_date, post_count, post_ids (JSON), summary, sentiment_distribution (JSON), created_at。

#### Scenario: 单帖子事件组
- **WHEN** 某个 event_tag 下只有 1 篇帖子
- **THEN** 系统 SHALL 仍创建 EventGroup，post_count=1

### Requirement: 事件时间线 API
`dashboard.py` SHALL 新增事件时间线端点，返回指定车型的 EventGroup 列表（按时间排序）。

#### Scenario: 查询事件时间线
- **WHEN** 前端请求 GET /api/vehicles/{id}/events
- **THEN** 系统 SHALL 返回该车型所有 EventGroup，按 start_date 倒序

### Requirement: EventGroup 摘要生成
系统 SHALL 为每个 EventGroup 调用 LLM 生成一句话摘要。

#### Scenario: 多帖子事件组
- **WHEN** EventGroup 包含 3 篇帖子
- **THEN** LLM SHALL 根据 3 篇帖子的 event_description 生成一句话摘要
