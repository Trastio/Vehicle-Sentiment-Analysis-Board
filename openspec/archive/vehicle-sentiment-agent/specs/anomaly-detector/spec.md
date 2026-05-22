## Module: anomaly-detector

24h 声量异常检测，触发事件推送。

### Inputs
- 当天声量（讨论声量 + 媒体声量之和）
- 昨天声量（同上）
- 阈值：±60%（暂定）

### Outputs
- 异常事件记录，写入 `anomaly_events` 表
- 推送通知（触发看板更新 + 简报/报告生成入口）

### Behavior
1. 每次数据采集+分析完成后，计算当天声量
2. 对比昨天声量：(today - yesterday) / yesterday
3. 超过 +60% 或低于 -60% → 标记为异常
4. 异常事件记录包含：车型、日期、声量变化率、相关帖子样本、情感分布变化
5. 去重：同一车型同一天只记录一次异常
6. 推送给用户，用户点击后可生成事件简报或深度报告

### Interfaces
```python
class AnomalyDetector:
    def check(self, vehicle_id: str, today_volume: float, yesterday_volume: float) -> AnomalyEvent | None
    async def generate_event_summary(self, anomaly: AnomalyEvent) -> EventBrief
```

### Threshold Adjustment
- 初期固定 ±60%
- 后续可按车型基准声量动态调整（低声量车型阈值放宽，高声量车型收紧）
