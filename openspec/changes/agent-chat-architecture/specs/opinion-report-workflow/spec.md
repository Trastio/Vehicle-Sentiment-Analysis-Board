## ADDED Requirements

### Requirement: 舆情报告 Workflow 触发
系统 SHALL 在 Agent 路由到 opinion_report 意图时触发舆情报告 Workflow。Workflow MUST 参考 BettaFish ReportEngine 架构，执行：数据采集→分析→模板选择→章节生成→HTML 渲染。

#### Scenario: 触发舆情报告
- **WHEN** Agent 识别意图为 opinion_report 且上下文有车型
- **THEN** 系统 SHALL 启动 opinion-report-workflow

#### Scenario: 复用已有数据
- **WHEN** 上下文中已有该车型的分析结果
- **THEN** 系统 SHALL 复用已有数据，跳过数据采集步骤

### Requirement: 报告模板选择
系统 SHALL 使用 LLM 根据舆情数据特征自动选择报告模板。模板 MUST 至少包括：日常舆情监测报告、突发事件危机公关报告、企业品牌声誉分析报告。

#### Scenario: 日常监测模板选择
- **WHEN** 舆情数据无明显突发事件，负面占比低于30%
- **THEN** 系统 SHALL 选择"日常舆情监测报告"模板

#### Scenario: 危机公关模板选择
- **WHEN** 舆情数据存在重大负面事件，预警级别为 critical
- **THEN** 系统 SHALL 选择"突发事件危机公关报告"模板

#### Scenario: 模板选择降级
- **WHEN** LLM 模板选择失败
- **THEN** 系统 SHALL 默认使用"日常舆情监测报告"模板

### Requirement: 章节内容生成
系统 SHALL 使用 LLM 根据模板结构和分析数据逐章节生成内容。每个章节 MUST 包含：标题、正文段落、关键数据引用。章节内容 SHALL 基于实际分析数据，不得编造。

#### Scenario: 章节内容生成
- **WHEN** 模板选择完成且分析数据就绪
- **THEN** 系统 SHALL 按模板结构逐章生成内容，引用具体的情感比例、声量数据、热点关键词

#### Scenario: 防幻觉校验
- **WHEN** LLM 生成的章节内容包含无法从分析数据中验证的数据
- **THEN** 系统 SHALL 标记该内容为"待核实"或使用实际数据替换

### Requirement: 报告 HTML 渲染
系统 SHALL 将章节内容渲染为结构化 HTML 报告。报告 MUST 包含：目录导航、章节标题、正文内容、数据图表（ECharts）、重大预警高亮。HTML 报告 SHALL 自包含，可独立浏览。

#### Scenario: HTML 报告渲染
- **WHEN** 所有章节内容生成完成
- **THEN** 系统 SHALL 渲染为包含目录、章节、图表的自包含 HTML

#### Scenario: 报告嵌入聊天
- **WHEN** HTML 报告渲染完成
- **THEN** 系统 SHALL 将报告通过 iframe 嵌入聊天消息

### Requirement: 舆情报告异步执行
舆情报告 Workflow SHALL 异步执行，不阻塞 Agent 的其他对话。执行过程中 MUST 通过 SSE 推送进度。

#### Scenario: 异步执行与进度推送
- **WHEN** 舆情报告 Workflow 开始执行
- **THEN** Agent SHALL 立即回复"正在为您生成舆情报告..."，同时通过 SSE 推送各阶段进度
