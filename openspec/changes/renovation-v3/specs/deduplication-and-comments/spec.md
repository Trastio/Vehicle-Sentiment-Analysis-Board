## ADDED Requirements

### Requirement: SimHash 去重
系统 SHALL 使用 SimHash 64 位指纹对帖子进行去重，Hamming 距离 ≤ 3 的帖子标记为同组。同组保留最早一条，其余标记 `duplicate_group_id`。

#### Scenario: 同事件多来源重复
- **WHEN** 不同来源（Bocha、Anspire）返回同一事件的不同报道，文本相似度 > 90%
- **THEN** 系统 SHALL 识别为重复，保留最早一条

#### Scenario: 不同事件的帖子
- **WHEN** 两条帖子涉及不同事件
- **THEN** 系统 SHALL 不标记为重复

#### Scenario: RawPost 新增 duplicate_group_id
- **THEN** RawPost 表 SHALL 新增 `duplicate_group_id: Column(String)` 字段

### Requirement: PostComment 独立存储
系统 SHALL 新增 PostComment 表，MediaCrawler 的评论独立存储而非拼接进 RawPost.content。

#### Scenario: MediaCrawler 帖子有评论
- **WHEN** MediaCrawler 返回的帖子包含评论
- **THEN** 系统 SHALL 将评论存入 PostComment 表（每条一行），帖子 content 只保留主帖文本

#### Scenario: PostComment 表结构
- **THEN** PostComment 表 SHALL 包含: id, post_id, vehicle_id, content, author, likes, platform, published_at, collected_at
- **AND** PostComment 不做逐条情感分析，仅存原始评论

### Requirement: XHS 短链解析
系统 SHALL 将 xhslink.com 短链解析为完整 URL 并提取 note_id，用于跨来源匹配同一帖子。

#### Scenario: xhslink.com 短链
- **WHEN** URL 包含 "xhslink.com"
- **THEN** 系统 SHALL 通过 HTTP 重定向获取最终 URL，再用正则提取 note_id

#### Scenario: 标准 XHS URL
- **WHEN** URL 已包含 /explore/ 或 /discovery/item/ 路径
- **THEN** 系统 SHALL 直接正则提取 note_id

### Requirement: 增量采集
系统 SHALL 只拉取新帖，不全量重拉。通过 published_at + platform + source_url 判断帖子是否已存在。

#### Scenario: 已存在的帖子
- **WHEN** 数据库中已存在相同 source_url + vehicle_id 的帖子
- **THEN** 系统 SHALL 跳过该帖子，不重复存储

#### Scenario: 新帖子
- **WHEN** 数据库中不存在相同 source_url 的帖子
- **THEN** 系统 SHALL 正常存储

### Requirement: heat_calculator 同步修改
`heat_calculator.py` SHALL 移除 `SOCIAL_SOURCES` 中的 "mediacrawler_comment"，互动烈度改为加权 `likes×1 + comments×5 + shares×10`。

#### Scenario: 社交媒体帖子热度计算
- **WHEN** 计算社交媒体帖子的互动烈度
- **THEN** 公式 SHALL 为 `likes×1 + comments×5 + shares×10`

### Requirement: scheduler 时序调整
scheduler 的数据采集时序 SHALL 变为：关键词扩展(如需) → 增量采集(只拉新帖) → 全文爬取(news) → URL解析(xhs短链) → 内容去重 → 评论分离 → 存储帖子+评论
