## ADDED Requirements

### Requirement: 会话管理
系统 SHALL 支持会话（conversation）的创建、查询和列表。每个会话 MUST 有唯一 ID、标题和创建时间。

#### Scenario: 自动创建会话
- **WHEN** 用户发送第一条消息且无活跃会话
- **THEN** 系统 SHALL 自动创建新会话，标题根据首条消息内容生成

#### Scenario: 会话列表
- **WHEN** 用户请求会话列表
- **THEN** 系统 SHALL 返回所有会话的 ID、标题和最后更新时间，按时间倒序排列

### Requirement: 消息持久化
系统 SHALL 将所有对话消息持久化到 SQLite。每条消息 MUST 包含：会话 ID、角色（user/assistant/system）、内容、时间戳、消息类型（text/visual_report/opinion_report/progress）。

#### Scenario: 用户消息持久化
- **WHEN** 用户发送消息
- **THEN** 系统 SHALL 将消息存入 messages 表，角色为 user

#### Scenario: Agent 消息持久化
- **WHEN** Agent 生成回复
- **THEN** 系统 SHALL 将回复存入 messages 表，角色为 assistant，类型根据内容标记

#### Scenario: 报告消息持久化
- **WHEN** 可视化报告或舆情报告生成完成
- **THEN** 系统 SHALL 将报告 HTML 内容存入 messages 表，类型为 visual_report 或 opinion_report

### Requirement: 上下文记忆
系统 SHALL 在 Agent 处理消息时加载当前会话的对话历史作为上下文。上下文 MUST 包括最近 N 条消息（N 可配置，默认 20）。

#### Scenario: 上下文加载
- **WHEN** Agent 处理新消息
- **THEN** 系统 SHALL 加载当前会话最近 20 条消息作为 LLM 上下文

#### Scenario: 上下文窗口限制
- **WHEN** 对话历史超过 20 条
- **THEN** 系统 SHALL 只保留最近 20 条，更早的消息不纳入 LLM 上下文（但仍持久化在数据库中）

### Requirement: 数据库表结构
系统 SHALL 新增 conversations 表和 messages 表。conversations 表 MUST 包含 id、title、created_at、updated_at 字段。messages 表 MUST 包含 id、conversation_id、role、content、message_type、metadata、created_at 字段。

#### Scenario: 表自动创建
- **WHEN** 系统启动
- **THEN** 系统 SHALL 自动创建 conversations 和 messages 表（如不存在）

### Requirement: 会话恢复
系统 SHALL 支持在页面刷新后恢复最近的会话和对话历史。

#### Scenario: 页面刷新恢复
- **WHEN** 用户刷新页面
- **THEN** 前端 SHALL 从后端加载最近会话的消息历史，恢复聊天界面显示
