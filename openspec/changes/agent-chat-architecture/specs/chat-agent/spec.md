## ADDED Requirements

### Requirement: Agent 意图识别
系统 SHALL 使用 LLM 对用户输入进行意图识别，识别结果 MUST 为以下之一：chat（闲聊）、query（舆情查询）、visual_report（可视化报告）、opinion_report（舆情报告）、drill_down（追问细节）。

#### Scenario: 用户输入舆情查询
- **WHEN** 用户输入"帮我看看比亚迪秦PLUS的舆情"
- **THEN** 系统 SHALL 识别意图为 query，提取参数 car_model="比亚迪秦PLUS"

#### Scenario: 用户请求可视化报告
- **WHEN** 用户输入"生成可视化报告"或"看看数据看板"
- **THEN** 系统 SHALL 识别意图为 visual_report

#### Scenario: 用户请求舆情报告
- **WHEN** 用户输入"生成舆情报告"或"出一份报告"
- **THEN** 系统 SHALL 识别意图为 opinion_report

#### Scenario: 用户闲聊
- **WHEN** 用户输入"你好"或"你能做什么"
- **THEN** 系统 SHALL 识别意图为 chat

#### Scenario: 意图识别降级
- **WHEN** LLM 意图识别失败或超时
- **THEN** 系统 SHALL 默认路由为 query，使用规则提取车型名

### Requirement: Agent 对话管理
系统 SHALL 维护对话上下文，包括当前讨论的车型、已执行的分析、用户偏好等。Agent 回复 MUST 基于上下文生成，而非独立处理每条消息。

#### Scenario: 上下文关联
- **WHEN** 用户先查询"比亚迪秦PLUS的舆情"，再追问"那条负面具体说什么"
- **THEN** 系统 SHALL 理解"那条负面"指的是比亚迪秦PLUS的负面舆情，并给出具体内容

#### Scenario: 车型切换
- **WHEN** 用户在讨论车型A后，输入"看看特斯拉Model 3"
- **THEN** 系统 SHALL 切换上下文到特斯拉Model 3

### Requirement: Agent 路由分发
系统 SHALL 根据意图识别结果路由到不同的处理逻辑：chat → LLM 直接回复；query → 轻量分析 + 对话回复；visual_report → 触发可视化 Workflow；opinion_report → 触发舆情报告 Workflow；drill_down → 基于上下文深入分析。

#### Scenario: 路由到可视化报告
- **WHEN** 意图为 visual_report 且上下文中有车型
- **THEN** 系统 SHALL 触发 visual-report-workflow，并在完成后将看板嵌入聊天消息

#### Scenario: 路由到舆情报告
- **WHEN** 意图为 opinion_report 且上下文中有车型
- **THEN** 系统 SHALL 触发 opinion-report-workflow，并在完成后将 HTML 报告嵌入聊天消息

#### Scenario: 无车型时的处理
- **WHEN** 意图为 visual_report 或 opinion_report 但上下文中无车型
- **THEN** 系统 SHALL 追问用户指定车型

### Requirement: Agent 流式回复
系统 SHALL 通过 SSE 将 Agent 回复逐字推送给前端，用户 MUST 能看到实时打字效果。对于长时间运行的 Workflow，系统 SHALL 通过 SSE 推送进度消息。

#### Scenario: 流式文本回复
- **WHEN** Agent 生成对话回复
- **THEN** 系统 SHALL 通过 SSE 逐 token 推送，前端实时显示

#### Scenario: Workflow 进度反馈
- **WHEN** 可视化报告或舆情报告 Workflow 正在执行
- **THEN** 系统 SHALL 通过 SSE 推送进度消息（如"正在采集数据..."、"正在生成报告..."）
