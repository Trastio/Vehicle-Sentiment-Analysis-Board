## Module: heat-metric-system

4 层热度指标计算与聚合，为看板和异常检测提供数据基础。

### Inputs
- `analyzed_posts` 表数据（带时间戳、平台、情感标签、互动数据）
- `collection_status` 表的采集时间范围
- 车型配置（含生命周期锚点）

### Outputs
- 热度指标时序数据，写入 `heat_metrics` 表
- 4 层指标：

| 层级 | 指标名 | 数据来源 | 粒度 |
|------|--------|---------|------|
| 1 | 注意力指数 | gopup（百度/微博/头条/谷歌指数） | 日 |
| 2 | 讨论声量 | MediaCrawler 帖子数 | 日 |
| 3 | 媒体声量 | Tavily/Bocha/Anspire 新闻数 | 日 |
| 4 | 互动烈度 | 点赞+评论+转发总和（归一化） | 日 |

### Behavior
1. 采集完成后，从各数据源提取对应指标
2. 注意力指数：直接取 gopup 指数数据，按日存储
3. 讨论声量：按日期 + 平台统计帖子数
4. 媒体声量：按日期统计新闻数
5. 互动烈度：sum(点赞+评论+转发) / max(当天所有帖子互动数)，归一化到 0-100
6. 支持按周/月聚合（为看板趋势图用）

### Interfaces
```python
class HeatMetricCalculator:
    async def calculate_daily(self, vehicle_id: str, date: date) -> HeatMetric
    async def calculate_range(self, vehicle_id: str, start: date, end: date) -> list[HeatMetric]
    async def aggregate(self, vehicle_id: str, period: str) -> AggregatedMetric  # period: daily/weekly/monthly
```

### Lifecycle Tagging
- 根据车型生命周期锚点，标记各时间段属于哪个阶段
- 看板趋势图可按生命周期阶段着色展示
