## Module: vehicle-management

多车型管理，搜索/筛选/多选，生命周期锚点配置，竞品车型配置。

### Inputs
- 用户搜索关键词（车型名、品牌名）
- 生命周期锚点配置（上市日期、改款日期、退市日期）
- 竞品车型列表（用户手动配置）

### Outputs
- 车型配置列表
- 单个车型详情（含采集状态、最新指标、生命周期信息）

### Data Model
```sql
CREATE TABLE vehicles (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,           -- 车型名，如"比亚迪秦PLUS DM-i"
    brand TEXT NOT NULL,          -- 品牌，如"比亚迪"
    search_keywords TEXT,         -- 搜索关键词，JSON 数组
    lifecycle_anchors TEXT,       -- 生命周期锚点，JSON: { "launch": "2024-03", "facelift": null, "retirement": null }
    competitor_ids TEXT,          -- 竞品车型 ID 列表，JSON 数组
    status TEXT DEFAULT 'active', -- active | retired
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);

CREATE TABLE collection_status (
    id TEXT PRIMARY KEY,
    vehicle_id TEXT REFERENCES vehicles(id),
    source TEXT NOT NULL,         -- gopup | mediacrawler | tavily | bocha | anspire | uapis
    mode TEXT NOT NULL,           -- initial | incremental
    last_collected_at TIMESTAMP,
    posts_collected INTEGER DEFAULT 0,
    status TEXT DEFAULT 'pending', -- pending | running | completed | failed
    error_message TEXT,
    updated_at TIMESTAMP
);
```

### Behavior
1. 用户搜索车型 → 显示匹配结果列表
2. 用户选择车型（可多选）→ 创建 vehicle 记录
3. 用户可配置生命周期锚点（上市/改款/退市日期）
4. 用户可添加竞品车型 → 从已选车型中选择或新增
5. 首次添加车型时，自动触发初始采集

### Interfaces
```python
# 后端 API
GET    /api/vehicles/search?q=<keyword>        → 搜索车型
GET    /api/vehicles                            → 车型列表
POST   /api/vehicles                           → 添加车型
PUT    /api/vehicles/<id>                      → 更新车型配置
DELETE /api/vehicles/<id>                      → 删除车型
PUT    /api/vehicles/<id>/lifecycle             → 更新生命周期锚点
PUT    /api/vehicles/<id>/competitors           → 更新竞品列表
```
