## ADDED Requirements

### Requirement: VehicleGroup 表
系统 SHALL 新增 VehicleGroup 表，字段：id, name, description, vehicle_ids (JSON), created_at, updated_at。

#### Scenario: 创建分组
- **WHEN** 用户创建"10万级紧凑SUV"分组，包含"元PLUS、零跑B10、银河E5"
- **THEN** 系统 SHALL 创建 VehicleGroup 记录，vehicle_ids 存储三个车型 ID

### Requirement: 分组 CRUD API
系统 SHALL 提供分组 CRUD 端点：
- POST /api/groups — 创建分组
- GET /api/groups — 列出所有分组
- GET /api/groups/{id} — 获取分组详情
- PUT /api/groups/{id} — 更新分组
- DELETE /api/groups/{id} — 删除分组

#### Scenario: 创建和查询
- **WHEN** 用户创建分组后查询
- **THEN** 系统 SHALL 返回包含完整信息的分组列表

### Requirement: 分组概览 API
GET /api/groups/{id}/overview SHALL 返回分组内各车型的汇总数据（总量、健康度、周变化），标注各车型帖子数量级。

### Requirement: 分组对比 API
GET /api/groups/{id}/comparison SHALL 返回组内各车型的情感/热度/维度对比数据。

### Requirement: 分组趋势 API
GET /api/groups/{id}/trend SHALL 返回组内各车型的热度/情感趋势叠加数据。

### Requirement: 分组看板前端
前端 SHALL 新增分组视图模式：
- header 区域新增"分组"下拉（与"车型"下拉并列），两种模式互斥
- 概览区：横向排列各车型 mini 卡片（帖子量级 + 健康度 + 周变化）
- 趋势图：多车型曲线叠加
- 情感对比：分组条形图
- 维度雷达图：多车型叠加
- Top 5 热门帖子：组内跨车型，含帖子 vs 评论情感差异

#### Scenario: 切换到分组模式
- **WHEN** 用户在分组下拉选择一个分组
- **THEN** 前端 SHALL 切换到分组视图，显示多车型对比

#### Scenario: 切换回单车型
- **WHEN** 用户在车型下拉选择一个车型
- **THEN** 前端 SHALL 切换回单车型视图

## MODIFIED Requirements

### Requirement: 可搜索 combobox
前端 header 的车型 `<select>` SHALL 改为可搜索 combobox，支持输入过滤、↑↓ 选择、Enter 确认、Esc 关闭。下拉显示车型名 + 品牌 + 帖子数量。

#### Scenario: 输入搜索
- **WHEN** 用户在 combobox 输入"海豚"
- **THEN** 下拉 SHALL 只显示包含"海豚"的车型

### Requirement: vehicle 搜索 API
`vehicle.py` SHALL 新增 GET /api/vehicles/search?q=xxx 端点，返回匹配车型列表（含帖子数量）。
