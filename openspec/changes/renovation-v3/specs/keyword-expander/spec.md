## ADDED Requirements

### Requirement: Vehicle 新增 expanded_keywords 字段
Vehicle 表 SHALL 新增 `expanded_keywords: Column(Text)` 字段，存储 AI 扩展的关键词 JSON 数组。

#### Scenario: 首次采集时扩展
- **WHEN** Vehicle 的 `expanded_keywords` 为空且首次触发采集
- **THEN** 系统 SHALL 调用 LLM 从新闻标题中提取扩展关键词并存入 `expanded_keywords`

#### Scenario: 后续采集复用
- **WHEN** Vehicle 的 `expanded_keywords` 非空
- **THEN** 系统 SHALL 直接使用已有扩展关键词，不重新扩展

### Requirement: AI 关键词扩展函数
系统 SHALL 提供 `expand_keywords(vehicle_name, base_keywords, news_titles)` 函数，使用 LLM 从新闻标题中提取扩展关键词，优化为网民语言。

#### Scenario: 扩展"比亚迪海豚"
- **WHEN** 输入车型名"比亚迪海豚"和基础关键词 ["比亚迪海豚"]
- **THEN** 系统 SHALL 输出 10+ 扩展关键词，如 "海豚冠军版降价"、"海豚荣耀版续航"、"比亚迪海豚投诉"

#### Scenario: LLM 扩展失败
- **WHEN** LLM 调用失败
- **THEN** 系统 SHALL fallback 到原始 `search_keywords`，不阻塞采集流程

### Requirement: scheduler 采集前检查扩展
`scheduler.py` SHALL 在采集前检查 Vehicle 的 `expanded_keywords` 是否为空，为空则触发扩展。

#### Scenario: 未扩展过的车型
- **WHEN** 采集触发时 Vehicle.expanded_keywords 为空
- **THEN** scheduler SHALL 先调用关键词扩展，再使用扩展后的关键词进行采集
