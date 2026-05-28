## MODIFIED Requirements

### Requirement: 互动烈度加权
`heat_calculator.py` 的互动烈度计算 SHALL 改为加权公式：`likes×1 + comments×5 + shares×10`。

#### Scenario: 社交媒体帖子
- **WHEN** 帖子有 likes=100, comments=20, shares=5
- **THEN** 互动烈度 SHALL 为 100×1 + 20×5 + 5×10 = 250

### Requirement: 热度指标标准化
HeatMetric 表 SHALL 新增 `rank: Column(String)` 和 `percentile: Column(Float)` 字段，分别表示近 30 天排名（如"近30天最高"/"前10%"）和历史百分位。

#### Scenario: 声量达近 30 天最高
- **WHEN** 当前声量为近 30 天内最高
- **THEN** rank SHALL 为 "近30天最高"，percentile SHALL 为 99.0

## ADDED Requirements

### Requirement: 异常根因解释
系统 SHALL 在异常事件发生时自动查询当日事件标签分布和热门帖子，生成一句话根因解释，存入 `AnomalyEvent.root_cause`。

#### Scenario: 声量异常 spike
- **WHEN** 24h 声量较昨日增长 ≥ 60%
- **THEN** 系统 SHALL 查询当日 AnalyzedPost 的 event_tags 分布，找到最高频标签，生成如"5/20刹车异响事件引发负面集中"的根因

#### Scenario: 声量异常 drop
- **WHEN** 24h 声量较昨日下降 ≥ 60%
- **THEN** 系统 SHALL 生成如"5/21无重大事件，自然回落"的根因

### Requirement: AnomalyEvent 新增字段
AnomalyEvent 表 SHALL 新增 `root_cause: Column(Text)` 字段。
