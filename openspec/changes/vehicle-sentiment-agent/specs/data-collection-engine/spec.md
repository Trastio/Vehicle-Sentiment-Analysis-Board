## Module: data-collection-engine

按需数据采集引擎，用户打开 Agent 时触发。

### Inputs
- 车型配置（车型名、生命周期锚点、竞品列表）
- 采集模式：`initial`（首次，3 个月历史）| `incremental`（增量，只拉新数据）
- 上次采集时间戳（增量模式用）

### Outputs
- 原始帖子/文章数据，写入 `raw_posts` 表
- 采集状态记录，写入 `collection_status` 表
- 采集完成后触发 Pipeline 层分析

### Behavior
1. 检查 `collection_status` 表判断是首次还是增量
2. 首次采集：按月份分 3 批拉取（3 个月前~2 个月前、2 个月前~1 个月前、1 个月前~今天）
3. 增量采集：只拉 `last_collected_at` 之后的数据
4. 各数据源并行采集（asyncio.gather），互不阻塞

### 数据源采集策略

| 数据源 | 用途 | 历史覆盖 | 采集方式 |
|--------|------|---------|---------|
| gopup | 百度/微博/头条/谷歌指数 | 100%（指定日期范围） | 指定 90 天日期范围，Cookie 通过 Playwright 自动获取 |
| MediaCrawler | 小红书/B站/知乎/微博/抖音等 | 60-80%（按时间排序翻页） | 关键词搜索 + 翻页，直接集成子模块调用 |
| Tavily/Bocha/Anspire | 新闻搜索 | 90%+（按月份分 3 次搜索） | 关键词 + 日期过滤 |
| uapis.cn | 热搜热榜 | 仅实时 | 实时接口 |
| justoneapi（可选） | 大规模声量统计 | 取决于 API | 关键词搜索 |

### Cookie 管理
- gopup 百度指数 Cookie 通过 Playwright 自动登录获取（复用 MediaCrawler 的 Playwright 依赖）
- 账号凭证存储在 `.secrets` 文件（已加入 .gitignore）
- Cookie 缓存到本地，有效期 7 天，过期自动重新登录
- 登录失败时 fallback 到手动配置模式
- 控制登录频率（同一账号 24h 内最多登录 3 次），避免触发风控

### Interfaces
```python
class CollectionEngine:
    async def collect(self, vehicle_config: VehicleConfig) -> CollectionResult
    async def collect_initial(self, vehicle_config: VehicleConfig) -> CollectionResult
    async def collect_incremental(self, vehicle_config: VehicleConfig) -> CollectionResult
```

### Error Handling
- 单数据源失败不阻塞其他数据源
- 失败记录写入日志，下次采集时重试
- 采集超时（单源 30s）自动跳过
- Cookie 获取失败时标记该数据源为 degraded，其他数据源正常工作
