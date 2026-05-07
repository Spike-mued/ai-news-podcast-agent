# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 通用命令

```bash
# 安装依赖（需要先安装 greenlet 二进制包）
pip install --only-binary :all: greenlet
pip install -e .

# 启动开发服务器（端口 9800）
python -m uvicorn app.main:app --host 0.0.0.0 --port 9800 --reload

# 运行测试
pytest tests/ -v

# 格式化 / Lint
ruff check app/ --fix
black app/ --line-length 120
```

## 架构概述

三 Agent 线性流水线，每个 Agent 是一个独立的 LangGraph StateGraph 子图：

```
APScheduler (每30分钟触发)
  → pipeline_service.run_full_pipeline()
    → [Phase 1] news_collector_graph: collect → deduplicate → rank
    → [Phase 2] podcast_writer_graph: write_scripts → synthesize → process_audio
    → [Phase 3] playlist_manager_graph: build_playlist → manage_stream
    → 音频入队列 → /stream 端点 chunked 输出
```

- **主流水线** (`app/services/pipeline_service.py`) 使用 `PipelineState` 编排三个子图，不通过 LangGraph 编译子图，而是直接调用子图节点的 async 函数
- 每个子图有独立的 `StateGraph` 和 `TypedDict` State，编译后的 graph 作为模块级单例

## Python 3.9 兼容性

- **必须**在需要 `X | None` 语法的文件开头添加 `from __future__ import annotations`
- 所有模型文件、服务文件、source 文件已添加此导入
- 新增文件如果使用 `|` 联合类型语法，同样需要添加

## 配置系统

`app/config.py` — 所有配置来自 `.env` 文件，通过 `pydantic-settings` 的 `Settings` 类管理。模块级单例 `config = Settings()` 在应用启动时即完成加载。

关键配置项：
- `DASHSCOPE_API_KEY` — 必须配置，否则 LLM 调用失败
- `news_collection_interval_minutes` — 流水线触发间隔（默认 30 分钟）
- TTS 使用 `edge-tts`，免费无需 API key，默认声音 `zh-CN-XiaoxiaoNeural`

## LLM 调用

通过 `langchain_openai.ChatOpenAI` 调用 DashScope 的 OpenAI 兼容接口（`https://dashscope.aliyuncs.com/compatible-mode/v1`）。`app/core/llm_factory.py` 提供 `create_chat_model()` 静态方法。

LLM 仅在两处使用：
1. `app/agents/news_collector/ranker.py` — 新闻重要性评分（temperature=0.3，非流式）
2. `app/agents/podcast_writer/script_writer.py` — 播客脚本生成（temperature=0.8，非流式）

## 数据库

SQLite，通过 `aiosqlite` 直接写原始 SQL（无 ORM）。四张表：`news`、`podcasts`、`playlists`、`pipeline_runs`。`init_database()` 在 FastAPI lifespan 启动时调用，自动建表和索引。

## 全局单例模式

以下模块在 import 时即创建单例实例：
- `config = Settings()` — `app/config.py`
- `source_registry = SourceRegistry()` — `app/sources/source_registry.py`
- `news_collector_graph` — `app/services/news_service.py`
- `podcast_writer_graph` — `app/services/podcast_writer_service.py`
- `playlist_manager_graph` — `app/services/playlist_manager_service.py`
- `pipeline_graph` — `app/services/pipeline_service.py`
- `stream_service = StreamService()` — `app/services/stream_service.py`
- `audio_service = AudioService()` — `app/services/audio_service.py`
- `tts_service = TTSService()` — `app/services/tts_service.py`

调度器通过回调注册模式工作：`pipeline_service.py` 在模块加载时调用 `register_trigger_callback(scheduled_pipeline_trigger)`，FastAPI lifespan 启动时调用 `start_scheduler()`。

## 流媒体

`/stream` 端点返回 `audio/mpeg` chunked response。`StreamService` 维护播放队列（FIFO），当队列为空时等待新内容。默认 buffer size 4096 字节，码率 128k。
