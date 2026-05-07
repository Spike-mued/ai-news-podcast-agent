# AI News Podcast Agent

24/7 不间断 AI 新闻播客系统，基于 FastAPI + LangChain + LangGraph 构建。

## 架构

```
[新闻采集 Agent] → [播客转译 Agent] → [音频拼接 Agent] → 24h 不间断播放
     (a.agent)         (b.agent)          (c.agent)           (播放器)
```

## 快速启动

### 1. 配置

编辑 `.env` 文件，填入 DashScope API Key：

```
DASHSCOPE_API_KEY=sk-your-api-key-here
```

### 2. 安装依赖

```bash
pip install -e .
```

### 3. 启动

**Windows:**
```bash
start-windows.bat
```

**手动启动:**
```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 9800
```

### 4. 访问

- Web 播放器: http://localhost:9800
- API 文档: http://localhost:9800/docs
- 健康检查: http://localhost:9800/api/health
- 24h 音频流: http://localhost:9800/stream

## 技术栈

| 组件 | 技术 |
|------|------|
| 框架 | FastAPI + Uvicorn |
| Agent 编排 | LangGraph (Plan-Execute-Replan) |
| LLM | DashScope (通义千问) |
| TTS | edge-tts |
| 音频处理 | pydub + ffmpeg |
| 新闻采集 | httpx + feedparser + BeautifulSoup |
| 调度 | APScheduler |
| 数据库 | SQLite (aiosqlite) |
| 日志 | Loguru |
| 流媒体 | HTTP Chunked Stream |

## 项目结构

```
ai-news-podcast-agent/
├── app/
│   ├── main.py              # FastAPI 入口
│   ├── config.py             # 配置管理
│   ├── api/                  # API 路由
│   ├── agents/               # 三 Agent 模块
│   │   ├── news_collector/   # 新闻采集与排序
│   │   ├── podcast_writer/   # 脚本生成与 TTS
│   │   └── playlist_manager/ # 播单管理与流媒体
│   ├── services/             # 业务服务层
│   ├── sources/              # 新闻源适配器
│   ├── models/               # 数据模型
│   ├── core/                 # 核心组件
│   ├── tools/                # Agent 工具
│   └── utils/                # 工具类
├── static/                   # Web 前端
├── config/                   # 配置文件
├── data/                     # 数据目录
└── logs/                     # 日志
```

## API 端点

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/` | Web 播放器 |
| GET | `/api/health` | 健康检查 |
| GET | `/api/news` | 新闻列表 |
| GET | `/api/news/stats` | 新闻统计 |
| GET | `/api/podcasts` | 播客列表 |
| GET | `/api/podcasts/current` | 当前播放 |
| GET | `/api/podcasts/{id}/audio` | 音频下载 |
| POST | `/api/pipeline/trigger` | 触发采集 |
| GET | `/stream` | 24h 音频流 |
| GET | `/stream/status` | 流状态 |
