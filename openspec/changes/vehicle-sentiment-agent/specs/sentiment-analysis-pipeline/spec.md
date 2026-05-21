## Module: sentiment-analysis-pipeline

对采集到的帖子进行情感分类 + 事件打标 + 观点提取，使用本地 Qwen3-4B 或临时使用 DeepSeek-V4-Flash。

### Inputs
- 原始帖子文本列表（从 `raw_posts` 表读取，状态为 `pending`）
- 模型选择：`local`（Qwen3-4B）| `api`（DeepSeek-V4-Flash，微调前临时用）

### Outputs
- 情感标签：`positive` | `negative` | `neutral`（文档级）
- 事件标签：1-3 个，从预定义词表选择
- 观点标签：0-N 个，从初始词表提取或自由扩展
- 结果写入 `analyzed_posts` 表

### 事件标签词表（5 大类 + 1 兜底）

| 类别 | 标签 |
|------|------|
| 厂商行为类 | 新车上市、发布会、降价/促销、涨价、改款/换代、召回、官方活动/营销 |
| 产品体验类 | 试驾体验、提车分享、用车感受、续航实测、油耗分享、改装分享 |
| 质量问题类 | 质量投诉、异响/故障、安全事故（自燃/断轴等）、维权投诉 |
| 行业讨论类 | 竞品对比、评测/拆解、销量数据、行业政策 |
| 兜底类 | 日常讨论 |

### 观点标签初始词表（4 维度，开放扩展）

| 维度 | 标签 |
|------|------|
| 价格 | 价格高、溢价、性价比、降价划算 |
| 产品 | 颜值高、外观丑、空间大、空间小、动力强、动力弱、续航好、续航差、油耗低、油耗高、智能化好、智能化差、异响、做工粗糙、舒适、内饰好、内饰差 |
| 服务 | 售后好、售后差、4S店态度差、保养贵、交付快、交付慢 |
| 安全 | 刹车问题、自燃、断轴、辅助驾驶事故 |

### Behavior
1. 批量读取 pending 帖子（每批 50 条）
2. 调用模型进行三合一分析：情感 + 事件 + 观点
3. 结果写入 `analyzed_posts` 表
4. 更新 `raw_posts` 状态为 `analyzed`
5. 低置信度样本标记为 `needs_review`，供后续飞轮回流

### Interfaces
```python
class AnalysisPipeline:
    async def analyze_batch(self, posts: list[RawPost], model: str = "api") -> list[AnalyzedPost]
    def analyze_single(self, text: str) -> AnalysisResult  # 情感+事件+观点
```

### Performance
- 目标吞吐：50 条/批，每批 < 10s（API）或 < 30s（本地）
- 批处理避免逐条调用，减少 API 开销
