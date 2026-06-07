## ADDED Requirements

### Requirement: 可视化报告 Workflow 触发
系统 SHALL 在 Agent 路由到 visual_report 意图时触发可视化报告 Workflow。Workflow MUST 复用现有数据采集、情感分析、热点提取等节点。

#### Scenario: 触发可视化报告
- **WHEN** Agent 识别意图为 visual_report 且上下文有车型
- **THEN** 系统 SHALL 启动 visual-report-workflow，执行数据采集→情感分析→热点提取→看板构建

#### Scenario: 复用已有数据
- **WHEN** 上下文中已有该车型的分析结果
- **THEN** 系统 SHALL 复用已有数据，跳过数据采集步骤，直接构建看板

### Requirement: 可视化报告内容
可视化报告 MUST 包含：情感分布饼图、热点词云、平台声量柱状图、时间趋势折线图、重大舆情预警、统计概览。报告 SHALL 与当前看板功能等价。

#### Scenario: 完整看板内容
- **WHEN** 可视化报告生成完成
- **THEN** 报告 SHALL 包含情感分布、热点词云、平台声量、时间趋势、重大舆情预警、统计概览

### Requirement: 可视化报告输出格式
可视化报告 SHALL 输出为独立的 HTML 页面，通过 iframe 嵌入聊天消息。HTML 页面 MUST 自包含（内联 CSS/JS），不依赖外部资源。

#### Scenario: 自包含 HTML 输出
- **WHEN** visual-report-workflow 完成
- **THEN** 系统 SHALL 生成一个自包含的 HTML 文件，包含内联的 ECharts 和样式

### Requirement: 可视化报告异步执行
可视化报告 Workflow SHALL 异步执行，不阻塞 Agent 的其他对话。执行过程中 MUST 通过 SSE 推送进度。

#### Scenario: 异步执行与进度推送
- **WHEN** 可视化报告 Workflow 开始执行
- **THEN** Agent SHALL 立即回复"正在为您生成可视化报告..."，同时通过 SSE 推送各阶段进度
