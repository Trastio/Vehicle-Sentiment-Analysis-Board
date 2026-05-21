## Module: dashboard

舆情看板，4 行 + 底部布局，Vue 3 组件化 + ECharts 可视化，支持锚点上下文对话。

### Inputs
- 车型配置（当前选中的车型/竞品）
- `analyzed_posts` 表数据
- `heat_metrics` 表数据
- `anomaly_events` 表数据
- 生命周期锚点

### Outputs
- 看板页面（Vue 3 SPA，含 ECharts 图表）
- 图表交互事件（点击 → 触发锚点对话）

### Layout（4 行 + 底部）

```
┌─────────────────────────────────────────────────┐
│ 第一行 概览区                                      │
│ 舆情总量 | 正/负/中性占比 | 周变化趋势 | 品牌健康度评分  │
├─────────────────────────────────────────────────┤
│ 第二行 趋势区                                      │
│ 时间趋势折线图 + 热度指数叠加                        │
├───────────────┬───────────────┬─────────────────┤
│ 第三行 分析区  │               │                 │
│ 平台声量分布  │ 事件分布       │ 观点 TOP10       │
├───────────────┴───────────────┴─────────────────┤
│ 第四行 异常与竞品区                                │
│ 异常事件时间线 | 竞品对比（用户指定车型）              │
├─────────────────────────────────────────────────┤
│ 底部 帖子详情表                                    │
│ 可按平台/情感/事件/观点筛选，支持分页                  │
└─────────────────────────────────────────────────┘
```

### Interactions
- 点击任何图表元素 → 弹出锚点上下文对话面板（Vue 3 侧边栏组件）
- 对话面板显示被点击元素的上下文信息
- 对话回复采用 Generative UI（可包含图表、表格、文本）

### Interfaces
```python
# 后端 API（FastAPI）
GET  /api/dashboard/{vehicle_id}           → 看板数据
GET  /api/dashboard/{vehicle_id}/trend     → 趋势数据
GET  /api/dashboard/{vehicle_id}/posts     → 帖子列表（支持筛选/分页）
POST /api/dashboard/{vehicle_id}/export    → 导出
```

### Frontend Components（Vue 3）
- `DashboardApp` — 根组件，管理全局状态（车型选择、时间范围）
- `OverviewCards` — 4 个指标卡片（舆情总量、正/负/中性占比、周变化趋势、品牌健康度评分）
- `TrendChart` — 趋势折线图（ECharts，支持缩放，@click 事件触发锚点对话）
- `PlatformPieChart` — 平台声量分布（饼图）
- `EventBarChart` — 事件分布（柱状图）
- `OpinionTop10` — 观点 TOP10（词云/柱状图）
- `AnomalyTimeline` — 异常事件时间线（ECharts timeline）
- `CompetitorCompare` — 竞品对比图（用户指定竞品车型）
- `PostTable` — 帖子详情表（可筛选、分页，Vue 3 响应式）
- `DialogPanel` — 锚点对话面板（侧边滑出，Generative UI 渲染）
