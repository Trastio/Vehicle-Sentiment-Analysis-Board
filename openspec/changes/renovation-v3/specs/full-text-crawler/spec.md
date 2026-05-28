## MODIFIED Requirements

### Requirement: RawPost 新增 full_content 字段
RawPost 表 SHALL 新增 `full_content: Column(Text)` 字段，存储 Trafilatura 或 Crawl4AI 抓取的全文。当两级抓取均失败时，`full_content` SHALL 为空字符串，分析时 fallback 到 `content`（snippet）。

#### Scenario: Trafilatura 抓取成功
- **WHEN** 新闻帖子的 URL 可正常访问且 Trafilatura 提取到 ≥200 字全文
- **THEN** `full_content` SHALL 存储提取的全文，`status` 为 "success"

#### Scenario: Trafilatura 失败 Crawl4AI 成功
- **WHEN** Trafilatura 抓取失败但 Crawl4AI 成功提取全文
- **THEN** `full_content` SHALL 存储 Crawl4AI 提取的全文，`status` 为 "success"

#### Scenario: 两级均失败
- **WHEN** Trafilatura 和 Crawl4AI 均失败
- **THEN** `full_content` SHALL 为空，`status` 为 "fallback"，分析使用 `content`（snippet）

## ADDED Requirements

### Requirement: 两级全文抓取函数
系统 SHALL 提供 `crawl_full_text(url, snippet)` 异步函数，实现两级抓取策略：
1. 第一级：`trafilatura.fetch_url()` + `trafilatura.extract(favor_precision=True)`，全文 ≥200 字算成功
2. 第二级：`AsyncWebCrawler`（Crawl4AI/Playwright），仅当第一级失败时调用
3. 兜底：返回 `{"url": url, "full_text": snippet, "status": "fallback"}`

#### Scenario: 纯静态新闻页面
- **WHEN** URL 指向静态 HTML 新闻页面
- **THEN** 系统 SHALL 使用 Trafilatura 成功提取全文

#### Scenario: SPA/动态渲染页面
- **WHEN** URL 指向需要 JavaScript 渲染的页面
- **THEN** 系统 SHALL 在 Trafilatura 失败后使用 Crawl4AI 提取全文

### Requirement: analyzer 优先使用全文
`analyzer.py` SHALL 优先使用 `RawPost.full_content` 进行分析，当 `full_content` 为空时 fallback 到 `RawPost.content`。

#### Scenario: 有全文的分析
- **WHEN** `RawPost.full_content` 非空
- **THEN** analyzer SHALL 使用 `full_content` 作为分析输入

#### Scenario: 无全文的 fallback
- **WHEN** `RawPost.full_content` 为空或 None
- **THEN** analyzer SHALL 使用 `RawPost.content`（snippet）作为分析输入
