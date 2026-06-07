# Vehicle Sentiment Analysis Board — 汽车舆情分析看板

一个全栈汽车舆情分析系统，自动采集社交媒体数据，通过双模型（本地 LoRA + 云端 LLM）进行情感分析和事件检测，提供可视化看板与 AI 对话式洞察。

## 功能特性

- 🕷️ **多源数据采集** — 小红书 / 微博 / 抖音 / B站 / 百度指数 / 新闻搜索，全链路自动化
- 🧠 **双模型情感分析** — 本地 Qwen3-4B LoRA 微调（ABSA） + 云端 DeepSeek/GLM（事件分析）并行
- 🔥 **热度 & 异常检测** — 基于评论量、互动量计算热度趋势，自动识别异常峰值
- 📊 **事件聚类** — DBSCAN 算法自动将相关帖文聚合为事件组
- 💬 **AI 对话** — 基于车型事件的上下文增强对话，支持 SSE 流式输出
- 📋 **可视化看板** — Vue 3 前端，支持情感趋势、雷达图、事件时间线
- 🔍 **全文爬取** — 帖文正文异步抓取 + SimHash 去重
- 📌 **车型分组** — 支持 vehicle group 聚合对比分析

## 项目结构

```
Vehicle Sentiment Analysis Board/
├── start.py                    # 启动入口
├── requirements.txt            # Python 依赖
│
├── api/
│   ├── main.py                 # FastAPI 应用
│   ├── pipeline_state.py       # 管道状态管理
│   └── routes/
│       ├── vehicle.py          # 车辆 CRUD API
│       ├── collection.py       # 数据采集 API
│       ├── analysis.py         # 分析 API
│       ├── dashboard.py        # 看板数据 API
│       ├── dialog.py           # AI 对话 API
│       ├── group.py            # 分组 API
│       └── reports.py          # 报告 API
│
├── pipeline/
│   ├── scheduler.py            # 采集调度器（全链路编排）
│   ├── collectors/
│   │   ├── media_crawler.py    # 社交媒体采集（小红书/微博/抖音/B站）
│   │   ├── gopup_collector.py  # 百度指数采集
│   │   ├── news_collector.py   # 新闻搜索（Tavily/Bocha/Anspire）
│   │   ├── keyword_expander.py # LLM 关键词扩展
│   │   ├── full_text_crawler.py# 帖文全文爬取
│   │   └── cookie_manager.py   # 百度 Cookie 自动登录
│   └── analysis/
│       ├── analyzer.py         # 双模型分析引擎
│       ├── local_absa.py       # 本地 Qwen3-4B LoRA ABSA 模型
│       ├── model_router.py     # 模型路由（本地/云端）
│       ├── heat_calculator.py  # 热度计算
│       ├── anomaly_detector.py # 异常检测
│       ├── anomaly_explainer.py# 异常原因解释
│       ├── event_tracker.py    # 事件追踪器
│       ├── deduplicator.py     # SimHash 去重
│       └── batch_runner.py     # 批量分析执行器
│
├── models/
│   ├── database.py             # 数据库连接
│   └── schemas.py              # ORM 模型
│
├── utils/
│   ├── config.py               # 配置加载
│   ├── constants.py            # 常量定义
│   └── llm_helpers.py          # LLM 工具函数
│
├── frontend/                   # Vue 3 前端
│   ├── index.html
│   └── static/
│       ├── css/style.css
│       └── js/
│           ├── app.js          # 主应用
│           └── dialog.js       # 对话组件
│
├── scripts/
│   └── run_collection.py       # 采集脚本
│
└── tests/                      # 测试套件（347+ 测试用例）
```

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
playwright install chromium
```

### 2. 配置密钥

创建 `.secrets` 文件（参考下方格式，详见 `.secrets.example`）：

```json
{
  "tavily": { "api_key": "your_tavily_key" },
  "bocha": { "api_key": "your_bocha_key" },
  "glm": { "api_key": "your_glm_key", "base_url": "https://open.bigmodel.cn/api/paas/v4" }
}
```

> ⚠️ `.secrets` 文件已在 `.gitignore` 中排除，不会上传到仓库。

### 3. 启动服务

```bash
python start.py
```

- 看板界面：http://localhost:8000
- API 文档：http://localhost:8000/docs

### 4. 可选：本地情感分析模型

如果需要本地 LoRA 模型（Qwen3-4B 微调），将模型权重放置于 `.secrets` 中 `local_model.path` 指定的路径下。

## 数据采集流程

```
关键词扩展（LLM）
       ↓
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  社交媒体     │     │  百度指数     │     │  新闻搜索     │
│  小红书/微博   │     │  GoUpUp      │     │  Tavily/Bocha│
│  抖音/B站     │     │              │     │  Anspire     │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       ↓                     ↓                     ↓
       └─────────────┬───────┘─────────────────────┘
                     ↓
              全文爬取 + 去重
                     ↓
              ┌──────┴──────┐
              ↓             ↓
        本地 ABSA      云端 LLM
        (LoRA)      (DeepSeek/GLM)
              ↓             ↓
              └──────┬──────┘
                     ↓
          热度计算 / 异常检测 / 事件聚类
                     ↓
              可视化看板展示
```

## 技术栈

| 组件 | 技术 |
|------|------|
| 后端 | FastAPI + SQLAlchemy + aiosqlite |
| 前端 | Vue 3 (CDN) + 原生 JavaScript |
| NLP 本地模型 | Qwen3-4B LoRA (Unsloth) |
| NLP 云端模型 | DeepSeek / 智谱 GLM |
| 数据采集 | MediaCrawler + Playwright + GoUpUp |
| 情感分析 | 双模型并行（ABSA + 事件标签） |
| 去重 | SimHash |
| 聚类 | DBSCAN (scikit-learn) |
| 测试 | pytest (347+ 测试用例) |

## License

MIT
