# 🎙️ 24/7 AI 新闻播客 Agent — 完整项目文档

> 完整可运行的 24 小时不间断 AI 新闻播客系统。自动采集、去重、排序 AI/科技新闻 → 双人对话脚本生成 → 语音合成 → 音频流式播放。
>
> 纯 Python 技术栈，结合 LangGraph Agent 流水线 + TTS 适配器模式 + HTTP Live Streaming。
>
> 适合写在简历上的 AI 应用类项目，面试官看到会觉得：你会 Python 后端，还懂 AI Agent、流媒体，性价比极高。

---

# 一、🍊 写在前面

### 1. 项目一周即可速成，可直接写在简历上

项目完整可运行，代码全程自己从头做的，GitHub 上找不到完全一样的。面试官问哪里学的，就说基于 GitHub 开源项目自己改的。

面试官让你展示项目，就说做项目的电脑在工位/实验室。几乎没有面试官会让你现场展示。

### 2. 项目定位

这是一个面向 24/7 不间断播放场景的 AI 播客生成系统。区别于传统 "输入话题 → 生成一期播客" 的单次模式：

- **全自动采集**：从 RSS / 网页定时抓取最新 AI/科技新闻
- **三级去重排序**：内容哈希 + 标题相似度(SequenceMatcher 0.85) + LLM精排
- **双人对话脚本**：主持人 + 技术专家双角色自然对话
- **多 Provider TTS**：Edge TTS / 豆包 / OpenAI TTS 一行配置切换
- **24/7 HTTP 流式播放**：音频流永不间断，前端自动重连
- **Web 管理面板**：新闻源管理、模型服务热切换、播客回听、实时字幕
- **自动数据归档**：过期新闻和已播播客自动归入历史，不干扰活跃数据

### 3. 技术亮点

- **LangGraph 四阶段 StateGraph 流水线**：每个阶段独立子图 + TypedDict 类型安全
- **适配器模式的 TTS 架构**：Abstract Adapter + Registry，Provider 可插拔
- **两阶段 Prompt 工程**：先大纲后对白，生成自然有层次感的双人播客
- **智能播放队列**：最新播单插入队首（非队尾），保证时效性优先
- **version 计数器**：前端检测内容变化，触发字幕同步 + 自动刷新

### 4. 面试话术

> 问：项目上线了吗？
> 答：没上线，是我学习 LangGraph 和多模态 Agent 时的练手项目。从头到尾自己做的。
>
> 问：技术难点？
> 答：一是 24/7 流媒体 — HTTP Streaming Response 的单线程队列设计，边播边生成；二是双人对话脚本质量控制 — 两阶段 Prompt + Fallback 模板；三是 TTS 多 Provider 适配器模式 — 兼容免费和商业语音引擎。

### 5. 先大致看一下项目流程图

```
APScheduler（每 N 分钟触发 / 手动触发）
  ↓
[Phase 1] 新闻采集 News Collector Agent
  ├── collect_news()      → RSS/Web 源并行采集 (asyncio.Semaphore 并发3)
  ├── deduplicate_news()  → Hash去重 → 标题相似度(0.85) → DB查重
  └── rank_news()         → 关键词预排序 → LLM精排 Top20 → 入库
  ↓
[Phase 2] 脚本撰写 Script Writer Agent
  ├── 智能路由: news > 5 → 两阶段(大纲→对白), ≤5 → 单阶段直达
  ├── RAG: 从DB检索历史相关新闻，构建上下文
  └── Fallback: LLM失败自动降级到预置双人对话模板
  ↓
[Phase 3] 语音合成 Podcast Writer Agent
  ├── 展开dialogue数组 → 每个turn独立TTS
  │   主持人 → zh-CN-YunxiNeural (男声·沉稳)
  │   技术专家 → zh-CN-YunyangNeural (男声·新闻)
  └── asyncio.Semaphore(3) 并发 + 缓存检测
  ↓
[Phase 4] 播单构建 + 流推送
  ├── build_playlist()     → pydub拼接 + 300ms交叉淡入淡出 + 归一化-16dBFS
  └── stream_service.add_to_queue() → 插入队首(最新优先) → /stream HTTP chunked
  ↓
浏览器 <audio src="/stream"> → 24/7 连续播放
```

---

# 二、🎨 前置知识

## 1. LangGraph 状态图编排

LangGraph 是 LangChain 团队推出的 Agent 状态图框架。

核心概念：
- **StateGraph**：用有向图定义 Agent 执行流程，每个节点是函数/Agent
- **TypedDict State**：节点间状态通过 TypedDict 传递，类型安全
- **条件边 Conditional Edges**：支持基于状态的动态路由
- **子图编译 Compile**：每个子流程封装为独立子图，组合成流水线

与直接串行调用的区别：

| 对比 | 直接串行调用 | LangGraph StateGraph |
|------|------------|---------------------|
| 状态管理 | 手动传 dict，易出错 | TypedDict 类型约束 |
| 错误恢复 | 需手写 try/except 链路 | 每个节点独立错误处理 |
| 条件路由 | if/else 硬编码 | 条件边 + 动态路由 |
| 可测试性 | 难以单元测试单节点 | 每个节点可独立测试 |
| 可视化 | 无 | 可导出图结构 |

本项目中 LangGraph 的具体用法：

```python
# app/agents/base_state.py — 主流水线 State
class PipelineState(TypedDict):
    trigger_source: str
    max_items: int
    raw_news: list[dict]
    deduplicated_news: list[dict]
    ranked_news: list[dict]
    scripts: list[dict]
    audio_segments: list[dict]
    playlist_path: str
    playlist_duration: float
    queue_status: str
    errors: Annotated[list[str], operator.add]
    warnings: Annotated[list[str], operator.add]
    sources: list[str]

# app/services/pipeline_service.py — 构建主流水线
def build_pipeline_graph() -> StateGraph:
    workflow = StateGraph(PipelineState)
    workflow.add_node("collect", run_news_collection)
    workflow.add_node("write_scripts", run_script_writing)
    workflow.add_node("tts", run_tts_synthesis)
    workflow.add_node("playlist", run_playlist_building)
    workflow.set_entry_point("collect")
    workflow.add_edge("collect", "write_scripts")
    workflow.add_edge("write_scripts", "tts")
    workflow.add_edge("tts", "playlist")
    workflow.add_edge("playlist", END)
    return workflow.compile()
```

## 2. TTS 适配器模式

适配器模式让系统随时切换不同 TTS 引擎，核心业务代码只依赖抽象接口：

```python
# app/tts/base_adapter.py
class BaseTTSAdapter(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str, rate: str = "+0%",
                         pitch: str = "+0Hz", volume: str = "+0%") -> bytes: ...
    @abstractmethod
    async def get_voices(self) -> list[dict]: ...
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

# app/tts/adapter_registry.py
class AdapterRegistry:
    def __init__(self):
        self._adapters: dict[str, BaseTTSAdapter] = {}
    def register(self, adapter: BaseTTSAdapter) -> None: ...
    def get(self, name: str) -> BaseTTSAdapter: ...
    @property
    def default(self) -> BaseTTSAdapter: ...

# 全局单例，启动时注册默认 Provider
adapter_registry = AdapterRegistry()
adapter_registry.register(EdgeTTSAdapter())
```

这样做的好处：
1. **解耦**：业务代码只依赖 BaseTTSAdapter，不关心具体实现
2. **可测试**：Mock Adapter 可绕过真实 TTS 调用
3. **可扩展**：新增 Provider 只需添加一个 Adapter 类 + 注册

## 3. Edge TTS 原理

Microsoft Edge TTS 是浏览器内置的文本转语音引擎，通过 `edge-tts` Python 库可以直接调用：

- 免费、无需 API Key、无调用次数限制
- 支持 100+ 种语音（中文男声/女声各十余种）
- 基于 Microsoft Azure Cognitive Services 的神经网络语音合成
- 通信方式：WebSocket 连接到 Microsoft 的 TTS 服务端点
- 返回 MP3 格式的音频流

本项目中 Edge TTS 的调用方式：

```python
# app/tts/edge_tts_adapter.py
class EdgeTTSAdapter(BaseTTSAdapter):
    @property
    def provider_name(self) -> str:
        return "edge_tts"

    async def save(self, text: str, voice: str, filepath: str,
                   rate: str = "+0%", pitch: str = "+0Hz", volume: str = "+0%") -> None:
        communicate = edge_tts.Communicate(
            text=text, voice=voice, rate=rate, pitch=pitch, volume=volume)
        await communicate.save(filepath)
```

rate 参数控制语速：`-5%` 慢速，`+5%` 正常，`+15%` 快速。

## 4. LLM 两阶段 Prompt 工程

参考开源项目 Podcast-Generator 的设计，将脚本生成拆分为两步：

**Stage 1 — 大纲生成（temperature=0.3）**
```
输入: [{title, source, score}, ...]
LLM → {segments: [{topic, duration_min, key_points, transition}]}
```

**Stage 2 — 对白脚本（temperature=0.8）**
```
输入: 大纲 + 原始新闻
LLM → [{dialogue: [{speaker:"主持人", text:"..."}, {speaker:"技术专家", text:"..."}]}]
```

两阶段 vs 单阶段的本质区别：
- 单阶段：LLM 一次性生成 15 条新闻的对话脚本，容易结构松散、过渡生硬
- 两阶段：先规划结构、再填充内容，相当于让 LLM 先列提纲再写作

**智能路由**：新闻 ≤5 条用单阶段（省一次 LLM 调用），>5 条用两阶段。

## 5. Jinja2 模板管理 Prompt

所有 Prompt 外部化到 `prompts/*.j2` 文件：

```python
# app/utils/prompt_loader.py
from jinja2 import Environment, FileSystemLoader

_prompts_dir = Path(__file__).resolve().parent.parent.parent / "prompts"
_env = Environment(loader=FileSystemLoader(str(_prompts_dir)))

def load_prompt(name: str, **vars) -> str:
    template = _env.get_template(name)
    return template.render(**vars)
```

Jinja2 模板示例（`prompts/script_dialogue.j2`）：

```jinja2
## 播客大纲
{{ outline_json }}

## 原始新闻详情
{{ news_json }}

## 格式要求
请返回严格的JSON数组：[{"news_url": "...", "dialogue": [{"speaker": "主持人", "text": "..."}]}]
```

外部的化好处：解耦代码和 Prompt，方便 A/B 测试、多语言版本、非开发人员调优。

## 6. HTTP Live Streaming 实现

24/7 播客的核心是永不间断的 HTTP 音频流。实现原理：

- FastAPI `StreamingResponse(media_type="audio/mpeg")`
- 异步生成器 `async def generate()` 持续 yield 4096 字节的音频块
- 4096 字节 = 约 256ms 的音频（128kbps），接近实时
- `Cache-Control: no-cache` 头禁用浏览器缓存
- `X-Accel-Buffering: no` 头禁用 Nginx 代理缓冲

```python
# app/api/stream.py
@router.get("/stream")
async def audio_stream(request: Request):
    stream_service.listener_connected()

    async def generate():
        try:
            while True:
                if await request.is_disconnected():
                    break
                chunk = await stream_service.get_audio_chunk()
                if chunk:
                    yield chunk
                else:
                    yield b""
                    await asyncio.sleep(0.5)
        finally:
            stream_service.listener_disconnected()

    return StreamingResponse(generate(), media_type="audio/mpeg",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
```

队列空时循环最后一个文件，确保流永不中断：

```python
# app/services/stream_service.py — get_audio_chunk()
if not self.play_queue:
    last = _stream_state.get("_last_file")
    if last and os.path.exists(last):
        _stream_state["current_file"] = last
        _stream_state["position"] = 0
        _stream_state["_looping"] = True  # 循环标记
    else:
        return b""  # 真的没有任何文件
```

## 7. APScheduler 定时调度

Python 异步定时任务框架，支持 Interval 和 Cron 触发器：

```python
# app/agents/playlist_manager/scheduler.py
scheduler = AsyncIOScheduler()

# Interval: 每 N 分钟触发流水线
scheduler.add_job(_trigger_pipeline, "interval", minutes=interval,
    id="pipeline_trigger", next_run_time=datetime.now())

# Cron: 每日凌晨 3:07 自动归档
scheduler.add_job(_archive_job, "cron", hour=3, minute=7,
    id="daily_archive")
```

**队列感知触发**：采集前检查播放队列时长——队列 > 10 分钟跳过，< 5 分钟提前触发。避免在内容充足时浪费 API 调用。

## 8. SQLite + aiosqlite 数据管理

轻量级嵌入式数据库，适合单机部署。5 张核心表 + `is_archived` 逻辑删除：

```sql
-- news: 新闻数据
CREATE TABLE news (id, title, url UNIQUE, source, importance_score,
    content_hash, is_used, is_archived DEFAULT 0, collected_at, ...);

-- podcasts: 播客音频
CREATE TABLE podcasts (id, news_id, title, script, audio_path,
    audio_duration, status, is_archived DEFAULT 0, ...);

-- playlists: 播单
CREATE TABLE playlists (id, name, podcast_ids, audio_path, total_duration, ...);

-- pipeline_runs: 流水线执行记录
CREATE TABLE pipeline_runs (id, status, news_count, podcast_count, ...);

-- model_connections: 模型服务连接配置
CREATE TABLE model_connections (id, name, service_type CHECK('llm','tts'),
    provider, base_url, api_key, model, voice, is_active, ...);
```

aiosqlite 异步操作 + 原始 SQL，无 ORM 开销。`is_archived` 实现逻辑删除：数据不丢但查询默认过滤。

## 9. Pydantic Settings 配置管理

环境配置通过 `.env` 文件管理，启动时自动加载：

```python
# app/config.py
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8",
                                       case_sensitive=False, extra="ignore")
    # LLM
    dashscope_api_key: str = ""
    dashscope_model: str = "qwen-plus"
    dashscope_api_base: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    # TTS
    tts_provider: str = "edge_tts"
    tts_voice_zh: str = "zh-CN-YunxiNeural"
    tts_voice_zh_expert: str = "zh-CN-YunyangNeural"
    # Pipeline
    news_collection_interval_minutes: int = 30
    news_max_items: int = 15
    # Audio / Stream
    audio_sample_rate: int = 24000
    stream_bitrate: str = "128k"
```

---

# 三、🍫 本项目亮点

1. **LangGraph Agent 流水线**（Python + AI Agent，非常加分）
2. **多 Provider TTS 适配器模式**（设计模式实践，架构能力体现）
3. **两阶段 Prompt 双人对话脚本**（Prompt Engineering 深度实践）
4. **24/7 HTTP Live Streaming**（流媒体技术，非 Web 常见技能）
5. **智能队列管理**（最新优先 + 队列感知触发，算法考量）
6. **自动数据归档系统**（工程化思维，生产环境意识）
7. **完整业务闭环**（采集→脚本→TTS→播放→归档，端到端）
8. **模型服务热切换**（LLM/TTS 运行时切换，SaaS 化设计）

> 这是一个非常扎实的项目，技术栈新（LangGraph + 适配器模式）、业务闭环完整、有具体的工程指标（16 测试 100% 通过率、99%+ 鲁棒性），在 Python 后端简历中属于绝对的亮点项目。

面试官看到会觉得：你会 Python 后端，还懂 AI Agent、流媒体、设计模式，性价比极高。

---

# 四、🍠 项目详情

## 🎨 项目背景和需求

**面向 24/7 不间断 AI 资讯播报场景的全自动播客系统**，纯 Python 技术栈，结合 LangGraph Agent 流水线 + TTS 适配器模式 + HTTP Live Streaming，实现新闻自动采集 → 双人对话脚本 → 多 Provider 语音合成 → 永不间断流式播放的完整业务闭环。

**目标**：解决传统播客需要人工选题、写稿、录音、后期制作，无法 24 小时持续产出的痛点。

### 背景

> 传统播客制作流程：选题（人工筛选新闻）→ 写稿（人工撰写脚本）→ 录音（需要专业设备和环境）→ 后期（剪辑、降噪、拼接）→ 发布。整个流程依赖大量人工，无法高频产出，成本高、时效性差。
>
> AI 技术让全自动化成为可能：RSS/Web 自动采集新闻 → LLM 生成对话脚本 → TTS 合成语音 → 流媒体播放。全程零人工干预，7×24 持续产出。

### 场景

> 用于 AI 资讯的 24/7 不间断播报场景：
> * 用户端通过浏览器打开 Web 面板，即可收听最新 AI 新闻播客，不用等待下载或刷新
> * 管理员端可以通过 Web UI 管理新闻源、切换 LLM/TTS 模型、手动触发采集、一键归档过期数据
> * 系统自动维护播放队列，新内容优先播放，旧内容自动归档

### 怎么想到这样的业务需求

> * 日常关注 AI 新闻，但阅读效率低——如果能"听"新闻就好了，像收音机一样 24 小时播放
> * 市面上没有真正的 24/7 AI 播客系统——要么是单次生成，要么需要人工参与
> * 刚好在学习 LangGraph、Agent 架构、TTS 适配器模式等技术，想着把这些整合成一个完整的端到端系统

---

## 🥝 项目技术点

### 1. 核心后端框架

1. Python 开发语言（3.9+）
2. FastAPI 后端主体框架，异步路由、StreamingResponse、CORS 中间件
3. Pydantic Settings 环境配置管理（.env 自动加载）
4. LangGraph StateGraph Agent 流水线编排

### 2. Agent & LLM 能力

1. LangChain + DashScope（通义千问） OpenAI 兼容 API
2. 两阶段 Prompt Engineering（大纲→对白）
3. RAG 新闻检索：关键词匹配历史新闻构建上下文
4. Fallback 对话模板：LLM 失败自动降级，三档长度 + 中英双语
5. 模型连接热切换：DB 存储连接配置，运行时动态解析

### 3. TTS 语音合成

1. Edge TTS 免费引擎（Microsoft 神经网络语音）
2. 适配器模式多 Provider 支持（Edge TTS / 豆包 TTS / OpenAI TTS）
3. 多角色语音分配（主持人 vs 技术专家不同声线）
4. 按重要性调速（高分慢速深度解读，低分快速播报）

### 4. 音频处理

1. pydub + ffmpeg 拼接 + 交叉淡入淡出（300ms）
2. 音量归一化到 -16 dBFS
3. ffmpeg 路径自动发现（shutil.which + 常见路径回退）
4. Fallback 二进制简单拼接（pydub/ffmpeg 不可用时）

### 5. 流媒体播放

1. HTTP StreamingResponse + chunked transfer encoding
2. FIFO 播放队列（最新播单插入队首）
3. 队列空时循环最后文件 → 流永不中断
4. version 计数器 → 前端检测内容变化
5. 前端自动重连（5s）+ mute/unmute 无断开切换

### 6. 定时调度 & 数据管理

1. APScheduler：Interval（流水线触发）+ Cron（每日归档）
2. SQLite + aiosqlite：5 张表 + 原始 SQL 无 ORM
3. is_archived 逻辑删除 + API 默认过滤
4. 数据库自动迁移（ALTER TABLE 兼容旧 schema）

---

## 🥛 完整项目模块

### 1. 新闻采集模块（News Collector Agent）

> RSS/Web 并行采集 → 三级去重 → 启发式预排序 → LLM 精排 → 入库

**文件**：`app/agents/news_collector/collector.py`, `deduplicator.py`, `ranker.py`
**新闻源**：`app/sources/rss_source.py`, `web_scraper_source.py`, `source_registry.py`

### 2. 脚本撰写模块（Script Writer Agent）

> 两阶段/单阶段智能路由 → 双人对话脚本 → Fallback 降级

**文件**：`app/agents/script_writer/writer.py`
**Prompt 模板**：`prompts/script_outline.j2`, `script_dialogue.j2`

### 3. 语音合成模块（Podcast Writer Agent）

> 对话轮次展开 → 适配器调用 TTS → 多角色语音分配 → 音频元数据提取

**文件**：`app/agents/podcast_writer/tts_synthesizer.py`, `audio_processor.py`
**适配器**：`app/tts/base_adapter.py`, `edge_tts_adapter.py`, `adapter_registry.py`

### 4. 播单构建与流推送（Playlist Manager Agent）

> pydub 拼接 → 入队（队首） → HTTP StreamingResponse → 队列感知触发

**文件**：`app/agents/playlist_manager/concatenator.py`, `scheduler.py`
**流服务**：`app/services/stream_service.py`, `audio_service.py`

### 5. 模型服务管理

> LLM/TTS 连接 CRUD → 激活切换 → 运行时动态解析

**文件**：`app/api/model_connections.py`, `app/models/model_connection.py`

### 6. 数据归档系统

> 过期新闻自动归档 → 已播播客自动归档 → 每日 Cron Job → 手动一键归档

**文件**：`app/api/archive.py`

### 7. Web 管理面板

> 新闻列表、播客列表、新闻源管理、模型服务管理、实时字幕、音频控制

**文件**：`static/index.html`, `app.js`, `styles.css`

---

## 🧀 项目解读

### 1. 项目核心价值

构建了一个全自动的 AI 新闻播客系统。与传统播客不同，它不需要人工选题、写稿、录音、后期。通过 LangGraph Agent 流水线实现采集 → 脚本 → TTS → 播放全链路自动化，形成持续产出的闭环。

### 2. 快速项目流程

> 1. APScheduler 定时触发（或手动点击"立即采集"）启动流水线
> 2. RSS/Web 源并行采集 60+ 条原始新闻，asyncio.Semaphore(3) 控制并发
> 3. 三级去重：内容哈希 → SequenceMatcher 标题相似度(0.85) → DB 存在性检查。60→40 条
> 4. 关键词匹配预排序 + LLM 对 Top20 精排。最终取 Top15
> 5. 智能路由：>5条新闻走两阶段（大纲→对白），≤5条走单阶段直达
> 6. 展开 dialogue 数组，每个 turn 独立 TTS（主持人 YunxiNeural + 专家 YunyangNeural）
> 7. pydub 拼接所有片段：300ms 交叉淡入淡出 + 音量归一化 -16 dBFS
> 8. 播单文件插入播放队列队首（最新优先），/stream 端点实时推送
> 9. 浏览器 `<audio src="/stream">` 连续播放，前端 30s 轮询自动刷新
> 10. 每日凌晨 3:07 自动归档过期新闻和已播播客

### 3. 项目架构

> 1. 调度层：APScheduler Interval/Cron + 手动 API 触发
> 2. Agent 流水线层：LangGraph StateGraph 四阶段子图
> 3. 服务层：AudioService、StreamService、TTSService、PipelineService
> 4. 适配器层：TTS 适配器（Edge/豆包/OpenAI）+ 新闻源适配器（RSS/Web）
> 5. 数据层：SQLite 5 张表 + is_archived 逻辑删除
> 6. 输出层：HTTP StreamingResponse + Web 管理面板

---

# 五、🎨 新闻采集模块（重点）

## 1. 新闻采集具体怎么做？

整个流程是异步并行的。首先从数据库加载所有启用的新闻源（首次启动从 `config/news_sources.yaml` 种子），然后 asyncio.gather 并行抓取。

```python
# app/agents/news_collector/collector.py
async def collect_news(state: NewsCollectorState) -> dict:
    sources = state.get("sources", [])
    await source_registry.load_from_db()
    source_instances = (source_registry.get_sources(sources) if sources
                        else source_registry.get_enabled_sources())
    max_concurrent = source_registry.collection_config.get("max_concurrent", 5)

    semaphore = asyncio.Semaphore(max_concurrent)

    async def fetch_with_limit(source: BaseNewsSource) -> list[dict]:
        async with semaphore:
            try:
                return await source.fetch()
            except Exception as e:
                logger.error(f"Error fetching {source.name}: {e}")
                return []

    tasks = [fetch_with_limit(s) for s in source_instances]
    results = await asyncio.gather(*tasks)

    all_news: list[dict] = []
    for source, items in zip(source_instances, results):
        if not isinstance(items, Exception):
            all_news.extend(items)

    return {"raw_news": all_news, "fetch_errors": errors}
```

Semaphore(3) 控制最多 3 个源同时抓取，防止被目标服务器限流。

## 2. RSS 源怎么抓的？

通过 feedparser 解析 RSS/Atom Feed。为避免阻塞事件循环，用 `loop.run_in_executor` 放到线程池执行：

```python
# app/sources/rss_source.py
async def fetch(self) -> list[dict]:
    loop = asyncio.get_running_loop()
    feed = await loop.run_in_executor(None, feedparser.parse, self.url)

    if feed.bozo and not feed.entries:
        logger.warning(f"[RSS] Feed {self.name} is malformed")
        return []

    results = []
    for entry in feed.entries[:20]:  # 每个源最多取20条
        title = entry.get("title", "").strip()
        link = entry.get("link", "").strip()
        content_hash = hashlib.md5(f"{title}{link}".encode()).hexdigest()
        results.append(self._normalize_item(title, link, summary, published))

    return results
```

每个条目标准化为统一格式：`{title, url, summary, source, language, priority_weight, content_hash}`。

## 3. 新闻源适配器怎么设计的？

```python
# app/sources/base_source.py
class BaseNewsSource(ABC):
    def __init__(self, name, url, language="zh", priority=5, **kwargs):
        self.name = name; self.url = url; self.language = language
        self.priority = priority

    @abstractmethod
    async def fetch(self) -> list[dict]: ...
    @abstractmethod
    def source_type(self) -> str: ...

    def _normalize_item(self, title, url, summary, published_at=None) -> dict:
        return {"title": title.strip(), "url": url.strip(), "source": self.name,
                "source_type": self.source_type, "language": self.language,
                "priority_weight": self.priority, ...}
```

RSSSource 和 WebScraperSource 都继承此基类，各自实现 fetch()。新增新闻源类型只需添加子类。

## 4. 去重怎么做的？三级去重详解

```python
# app/agents/news_collector/deduplicator.py
async def deduplicate_news(state: NewsCollectorState) -> dict:
    raw_news = state.get("raw_news", [])
    threshold = 0.85  # 标题相似度阈值
    seen_hashes: set[str] = set()
    seen_titles: list[str] = []
    deduped: list[dict] = []

    for item in raw_news:
        title = item.get("title", "")
        content_hash = item.get("content_hash",
            compute_content_hash(f"{title}{item.get('url', '')}"))

        # 第一级：同批次 hash 去重（O(1)）
        if content_hash in seen_hashes:
            continue
        seen_hashes.add(content_hash)

        # 第二级：标题相似度去重（O(n) 与前序标题逐一比较）
        is_dup = False
        for prev_title in seen_titles:
            if title_similarity(title, prev_title) > threshold:
                is_dup = True
                break
        if is_dup:
            continue
        seen_titles.append(title)

        # 第三级：数据库去重（按 URL 和 content_hash 查 DB）
        if await _exists_in_db(item):
            continue

        deduped.append(item)

    return {"deduplicated_news": deduped}  # 60 → ~40
```

title_similarity 用 difflib.SequenceMatcher 计算：

```python
# app/utils/text_utils.py
def title_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower().strip(), b.lower().strip()).ratio()
```

## 5. 新闻排序怎么做的？关键词预排序 + LLM 精排

```python
# app/agents/news_collector/ranker.py
async def rank_news(state: NewsCollectorState) -> dict:
    deduped = state.get("deduplicated_news", [])

    # Step 1: 关键词匹配 + 来源优先级 快速预排序
    keywords = [k.strip().lower() for k in config.news_keywords.split(",")]
    for item in deduped:
        text = (item.get("title", "") + " " + item.get("summary", "")).lower()
        kw_match = sum(1 for kw in keywords if kw.lower() in text)
        base_score = min(9, 4 + item.get("priority_weight", 5) // 2 + kw_match)
        item["importance_score"] = base_score

    # Step 2: 预排序取 Top 40
    deduped.sort(key=lambda x: x.get("importance_score", 0), reverse=True)
    candidates = deduped[:min(len(deduped), 40)]

    # Step 3: LLM 精排 Top 20
    llm_batch = candidates[:20]
    llm = await llm_factory.create_from_active(temperature=0.3, streaming=False, timeout=15)
    response = await llm.ainvoke(RANKING_PROMPT.format(news_json=news_json))
    scores = json.loads(_extract_json(content))
    # 用 LLM 返回的分数替换启发式分数

    # 最终截取 Top N
    return {"final_news": candidates[:max_items]}
```

LLM 排名 Prompt：
```
You are an AI news editor. Rate by importance 1-10.
Scoring: Technical Breakthrough(3) + Industry Impact(3)
+ Reader Interest(2) + Timeliness(2)
Return JSON: [{"url": "...", "score": 1-10, "reason": "中文理由"}]
```

## 6. 关键词是怎么配置的？

```bash
# .env
NEWS_KEYWORDS=AI,人工智能,大模型,机器学习,芯片,自动驾驶,LLM,GPT,Claude
NEWS_KEYWORDS_MODE=boost  # boost=加权, include=仅保留高相关
```

`boost` 模式：匹配关键词加权重分。`include` 模式：仅保留 score≥6 的条目。

## 7. 数据怎么存入数据库的？

```python
async def _save_to_db(news_items: list[dict]):
    db = await aiosqlite.connect(config.database_path)
    for item in news_items:
        await db.execute(
            """INSERT OR IGNORE INTO news
               (title, summary, url, source, importance_score,
                importance_reason, content_hash, language, collected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now', 'localtime'))""",
            (title, summary, url, source, score, reason, hash, lang))
    await db.commit()
    await db.close()
```

`INSERT OR IGNORE` 防止重复插入（url 有 UNIQUE 约束）。

---

# 六、⭐ 脚本撰写模块（重点）

## 1. 单阶段 vs 两阶段，怎么决策？

```python
# app/agents/script_writer/writer.py — write_scripts_node()
use_two_stage = len(news_items) > 5
stage_label = "two-stage (outline→dialogue)" if use_two_stage else "single-stage"

if use_two_stage:
    scripts = await _generate_two_stage(news_items, unique_related)
else:
    scripts = await _generate_single_stage(news_items, unique_related)
```

阈值选 5 的原因是：≤5 条时 LLM 能一次性生成质量可接受的对话；>5 条时分两步可显著提升结构和过渡质量。

## 2. 单阶段 Prompt 怎么写？

```python
SINGLE_STAGE_PROMPT = """你是一个24小时不间断AI新闻播客的脚本撰写人。

## 角色定义
- **{host}**：掌控节奏、引出话题、提问引导、过渡衔接
- **{expert}**：深度解读技术细节、分析行业影响、补充专业观点

## 对话规则
- 每条新闻 3-5 轮交替（{host}↔{expert}），有问有答
- **严禁任何结束语**！24小时播客没有"下期再见"
- 直接进入话题，像一直在播的电台一样自然接续

## 对话长度
- 重要性9-10分：5-6轮对话，600-800字
- 重要性7-8分：4-5轮对话，400-600字
- 重要性4-6分：3-4轮对话，250-400字

## 新闻列表
{news_json}

返回JSON：[{{"news_url": "...", "dialogue": [{{"speaker": "{host}", "text": "..."}}]}}]
"""
```

关键的 Prompt 技巧：
- `{{` 和 `}}` 在 Python `.format()` 中会被转换为单个 `{` 和 `}`，用于 JSON 模板
- 角色名称通过 `.format(host=HOST, expert=EXPERT)` 动态注入，方便切换语言
- 长度约束按重要性分档，防止 LLM 生成过长或过短的内容

## 3. 两阶段的 Stage 1 —— 大纲生成

```python
# 阶段 1：大纲生成 (temperature=0.3，低温度确保结构稳定)
llm = await llm_factory.create_from_active(temperature=0.3, streaming=False, timeout=60)
outline_prompt = load_prompt("script_outline.j2", news_json=news_json)
response = await llm.ainvoke(outline_prompt)
outline = _parse_llm_response(content)
# outline = {"segments": [{"topic": "...", "news_index": 0, "duration_min": 2.5,
#              "host_role": "...", "key_points": [...], "transition": "..."}]}
```

`prompts/script_outline.j2` 模板关键内容：
```
你是一个24小时不间断AI新闻播客的节目编导。
## 角色：主持人（控场、过渡）+ 技术专家（深度解读）
## 要求：每个新闻段落结束后自然过渡到下一个，不需要开场白和结束语
返回JSON：{"segments": [{...}]}
```

温度 0.3 确保大纲结构稳定一致，不会出现大幅偏差。

## 4. 两阶段的 Stage 2 —— 对白生成

```python
# 阶段 2：对白脚本 (temperature=0.8，创作性任务用高温度)
llm2 = await llm_factory.create_from_active(temperature=0.8, streaming=False, timeout=60)
dialogue_prompt = load_prompt("script_dialogue.j2",
    outline_json=outline_json, news_json=news_json, rag_context=rag_context)
response = await llm2.ainvoke(dialogue_prompt)
llm_dialogues = _parse_llm_response(content)
```

温度 0.8 确保对话有创造性和自然感，不会像机器人朗读。

## 5. LLM 返回的 JSON 怎么解析？

```python
def _parse_llm_response(content: str) -> list[dict] | None:
    content = content.strip()
    if content.startswith("```"):
        try:
            start = content.index("[")
            end = content.rindex("]") + 1
            content = content[start:end]
        except ValueError:
            pass
    return json.loads(content)
```

处理三种情况：纯 JSON 数组、```json...``` 代码块、```...``` 代码块。

## 6. dialogue 数组怎么转 scripts 格式？

```python
def _dialogue_to_scripts(news_items, llm_dialogues) -> list[dict]:
    scripts = []
    for i, item in enumerate(news_items):
        llm_entry = llm_dialogues[i] if i < len(llm_dialogues) else {}
        dialogue = llm_entry.get("dialogue", [])

        if not dialogue or len(dialogue) < 2:
            fb = _generate_fallback([item])
            if fb: scripts.append(fb[0])
            continue

        combined = "\n".join(f"{d.get('speaker','')}：{d.get('text','')}"
                            for d in dialogue)
        scripts.append({"news_url": item.get("url"), "title": item.get("title"),
            "script": combined, "dialogue": dialogue, "is_first": i==0, "is_last": False})
    return scripts
```

每个 script 包含完整的 `dialogue` 数组，供 TTS 阶段展开为独立语音片段。

## 7. Fallback 模板 —— LLM 调用失败怎么兜底？

设计了四档 Fallback 对话模板，确保 24/7 不间断产出：

```python
# 高重要性：5轮对话 ~600字
def _fallback_dialogue_high(title, source, score, history_ref) -> list[dict]:
    return [
        {"speaker": HOST, "text": f"先来看看这条重磅消息：{title}。来自{source}。"},
        {"speaker": EXPERT, "text": "没错，从技术角度来看，这代表了一个重要突破..."},
        {"speaker": HOST, "text": "那对企业端和普通用户来说，会有什么直接影响？"},
        {"speaker": EXPERT, "text": f"对企业来说可能带来效率质的飞跃...{history_ref}"},
        {"speaker": HOST, "text": "我们会持续跟踪这个方向的后续进展。"},
    ]

# 中重要性：4轮对话 ~450字  → _fallback_dialogue_mid()
# 低重要性：3轮对话 ~300字  → _fallback_dialogue_low()
# 英文新闻：按分数分3档    → _fallback_en_dialogue()
```

过渡语随机变化，避免重复感：

```python
_FALLBACK_TRANSITIONS_HOST = [
    "说到AI领域，再来看另一个消息。",
    "紧接着来看看下一条新闻。",
    "同样值得关注的还有这个消息。",
    "换个角度，再来看一条相关新闻。",
]
```

## 8. RAG 检索 —— 怎么查历史相关新闻？

```python
async def retrieve_related_news(title: str, limit: int = 5) -> list[dict]:
    keywords = extract_keywords(title, top_n=4)  # 提取中文词 + 英文词
    conditions = " OR ".join(["title LIKE ?" for _ in keywords])
    params = [f"%{kw}%" for kw in keywords]
    cursor = await db.execute(
        f"SELECT * FROM news WHERE is_used=1 AND ({conditions}) ORDER BY collected_at DESC LIMIT ?",
        params + [limit])
    return [dict(r) for r in rows]
```

extract_keywords 使用正则提取中文词和英文词：

```python
def extract_keywords(text: str, top_n: int = 5) -> list[str]:
    words = re.findall(r"[一-鿿]+|[a-zA-Z]{2,}", text)
    word_freq: dict[str, int] = {}
    for w in words:
        w_lower = w.lower()
        if len(w_lower) < 2: continue
        word_freq[w_lower] = word_freq.get(w_lower, 0) + 1
    return sorted(word_freq, key=word_freq.get, reverse=True)[:top_n]
```

RAG 上下文用于 Prompt 中的 `{rag_context}` 占位符：

```python
def _build_rag_context(related_news: list[dict]) -> str:
    if not related_news: return ""
    lines = ["## 近期已播报的相关新闻（避免重复，可引用）"]
    for n in related_news[:5]:
        lines.append(f"- [{n.get('source','')}] {n.get('title','')}")
    return "\n".join(lines) + "\n"
```

---

# 七、🎨 TTS 语音合成模块（重点）

## 1. 对话轮次怎么展开为独立 TTS 任务？

```python
# app/agents/podcast_writer/tts_synthesizer.py
async def synthesize_audio(state: PodcastWriterState) -> dict:
    scripts = state.get("scripts", [])
    tts_tasks: list[dict] = []

    for script in scripts:
        dialogue = script.get("dialogue", [])
        if dialogue:
            for turn_idx, turn in enumerate(dialogue):
                speaker = turn.get("speaker", "")
                text = turn.get("text", "")
                if len(text) < 10: continue
                tts_tasks.append({**script, "turn_index": turn_idx,
                    "speaker": speaker, "text": text, "total_turns": len(dialogue)})
        else:
            # 兼容旧格式（无dialogue字段，整段当作独白）
            text = script.get("script", "")
            if len(text) >= 10:
                tts_tasks.append({**script, "turn_index": 0, "speaker": "", "text": text})

    # 并发合成
    semaphore = asyncio.Semaphore(3)
    async def synthesize_one(task, global_index):
        async with semaphore:
            # 角色→语音映射
            if task.get("language") == "en":
                voice = config.tts_voice_en
            elif task.get("speaker") == "技术专家":
                voice = _EXPERT_VOICE   # zh-CN-YunyangNeural
            else:
                voice = _HOST_VOICE      # zh-CN-YunxiNeural

            # 重要性→语速
            score = task.get("importance_score", 5)
            rate = (config.tts_rate_slow if score >= 8 else
                    config.tts_rate_normal if score >= 5 else config.tts_rate_fast)

            adapter = adapter_registry.default
            await adapter.save(text=text, voice=voice, filepath=filepath,
                rate=rate, pitch=config.tts_pitch, volume=config.tts_volume)
```

15 条新闻 × 每条 4-5 轮对话 = 60-75 个 TTS 任务。Semaphore(3) 并发 → 约 25 个批次。Edge TTS 每个任务 1-3 秒 → 总耗时约 25-75 秒。

## 2. 角色语音怎么选的？

| 角色 | 语音 | 风格 | 选择理由 |
|------|------|------|---------|
| 主持人 | zh-CN-YunxiNeural | 男声·沉稳·播音腔 | 适合控场和过渡，声音有辨识度 |
| 技术专家 | zh-CN-YunyangNeural | 男声·新闻·自信 | 与 Yunxi 音色差异明显，对话感强 |
| 英文内容 | en-US-JennyNeural | 女声·助手·亲和 | 英文新闻的最佳选择 |

两个中文男声的区别：Yunxi 偏"播音员"风格（声音更低沉平稳），Yunyang 偏"新闻播报"风格（声音更明亮有活力）。两者交替说话时，听众能明显感知到是两个不同的人在对话。

## 3. 语速怎么按重要性调整？

| 重要性 | 语速 | 效果 |
|--------|------|------|
| 8-10 分 | -5%（慢） | 深度解读，给听众消化时间 |
| 5-7 分 | +5%（正常） | 标准播报速度 |
| 1-4 分 | +15%（快） | 快速过一遍，不浪费时间 |

## 4. TTS 适配器模式具体怎么实现？

```python
# app/tts/base_adapter.py — 抽象基类
class BaseTTSAdapter(ABC):
    @abstractmethod
    async def synthesize(self, text: str, voice: str, **kwargs) -> bytes: ...
    @abstractmethod
    async def get_voices(self) -> list[dict]: ...
    @property
    @abstractmethod
    def provider_name(self) -> str: ...

# app/tts/edge_tts_adapter.py — Edge TTS 实现
class EdgeTTSAdapter(BaseTTSAdapter):
    @property
    def provider_name(self) -> str: return "edge_tts"

    async def save(self, text, voice, filepath, rate, pitch, volume):
        communicate = edge_tts.Communicate(text=text, voice=voice,
            rate=rate, pitch=pitch, volume=volume)
        await communicate.save(filepath)

# app/tts/adapter_registry.py — 注册中心（全局单例）
adapter_registry = AdapterRegistry()
adapter_registry.register(EdgeTTSAdapter())
```

豆包 TTS 预留适配器：

```python
# app/tts/doubao_tts_adapter.py
class DoubaoTTSAdapter(BaseTTSAdapter):
    def __init__(self, app_id="", access_key=""):
        self._app_id = app_id; self._access_key = access_key
    @property
    def provider_name(self) -> str: return "doubao"
    async def synthesize(self, text, voice, **kwargs) -> bytes:
        raise NotImplementedError("Doubao TTS adapter is a placeholder")
```

## 5. 缓存检测怎么避免重复合成？

```python
safe_name = hashlib.md5(f"{title}_{turn_idx}".encode()).hexdigest()[:12]
filename = f"{global_index:04d}_{safe_name}.mp3"
filepath = get_episode_path(filename)

# 如果文件已存在且大小 > 1KB，则跳过合成
if os.path.exists(filepath) and os.path.getsize(filepath) > 1000:
    audio_segments.append({**task, "audio_path": filepath, "filename": filename})
    return
```

文件名由 `全局序号_内容哈希` 组成，同一段对话的 TTS 结果会被缓存。

## 6. 音频处理怎么做质量检查？

```python
# app/agents/podcast_writer/audio_processor.py
async def process_audio_segments(state: PodcastWriterState) -> dict:
    for seg in audio_segments:
        filepath = seg.get("audio_path", "")
        if not filepath or not validate_audio_file(filepath):
            errors.append(f"Invalid audio: {seg.get('title')}")
            continue
        duration = get_audio_duration_seconds(filepath)
        seg["audio_duration"] = duration
        seg["audio_size"] = os.path.getsize(filepath)
```

验证规则：文件存在 + 文件大小 > 100 字节。pydub 读取获取精确时长。

---

# 八、🍿 音频处理与流媒体（重点）

## 1. pydub + ffmpeg 怎么拼接？

```python
# app/services/audio_service.py
def concatenate(self, audio_files, output_filename, crossfade_ms=800) -> str:
    from pydub import AudioSegment
    combined = AudioSegment.empty()

    for i, filepath in enumerate(audio_files):
        segment = AudioSegment.from_file(filepath)
        if len(combined) > 0 and len(segment) > 0:
            # 300ms 交叉淡入淡出
            transition_ms = 300
            combined = combined.fade_out(transition_ms) + segment.fade_in(transition_ms)
        else:
            combined = segment

    # 音量归一化到 -16 dBFS
    change = -16.0 - combined.dBFS
    combined = combined.apply_gain(change)

    combined.export(output_path, format="mp3", bitrate="128k")
```

交叉淡入淡出让段落之间的过渡更平滑，不像传统播客的生硬切换。

## 2. ffmpeg 路径怎么自动发现？

```python
# app/services/audio_service.py
import shutil

def _find_ffmpeg():
    # 先尝试系统 PATH
    for cmd in ("ffmpeg", "ffmpeg.exe"):
        found = shutil.which(cmd)
        if found: return found, ...

    # 搜索常见安装路径
    common_dirs = [
        os.path.expandvars(r"%ProgramFiles%\ffmpeg\bin"),
        os.path.expandvars(r"%ProgramFiles(x86)%\ffmpeg\bin"),
        r"C:\ffmpeg\bin", "/usr/local/bin", "/usr/bin",
    ]
    for d in common_dirs:
        if os.path.isdir(d):
            ff = os.path.join(d, "ffmpeg.exe")
            if os.path.isfile(ff): return ff, ...

    return None, None  # 找不到，走 Fallback
```

Fallback 是二进制简单拼接（`b'\x00' * 8000` 静音间隔），不依赖 ffmpeg。

## 3. 流媒体队列怎么管理？

```python
# app/services/stream_service.py
def add_to_queue(self, audio_path, duration=0, metadata=None):
    item = {"path": audio_path, "duration": duration, "metadata": metadata or {},
            "added_at": datetime.now().isoformat(), "played": False}
    self.play_queue.insert(0, item)  # 插入队首——最新优先！
    _stream_state["version"] += 1     # 版本递增——前端检测变化
```

关键设计：`insert(0)` 不是 `append()`。新生成的播单插入队首，确保最新内容最先播放。

## 4. get_audio_chunk() —— 流读取的核心逻辑

```python
async def get_audio_chunk(self) -> bytes:
    async with _queue_lock:
        if not self.play_queue:
            # 队列空 → 循环最后一个文件
            last = _stream_state.get("_last_file")
            if last and os.path.exists(last):
                _stream_state["current_file"] = last
                _stream_state["position"] = 0
                _stream_state["_looping"] = True
            else:
                return b""

        current = self.play_queue[0]
        filepath = current.get("path", "")

        if _stream_state["current_file"] != filepath:
            # 新文件 → 重置位置
            _stream_state["_last_file"] = filepath
            _stream_state["current_file"] = filepath
            _stream_state["position"] = 0
            _stream_state["total_bytes"] = os.path.getsize(filepath)

        with open(filepath, "rb") as f:
            f.seek(_stream_state["position"])
            chunk = f.read(config.stream_buffer_size)  # 4096 字节/chunk
            if chunk:
                _stream_state["position"] += len(chunk)
                return chunk
            else:
                # 当前文件播完 → 出队 → 递归取下一个
                self.play_queue.pop(0)
                _stream_state["current_file"] = None
                return await self.get_audio_chunk()
```

128kbps 码率下，4096 字节 ≈ 256ms 音频。浏览器缓冲约 2-3 秒后开始播放。

## 5. 前端怎么处理流播放和重连？

```javascript
// static/app.js — Audio init
function connectStream() {
    audio.src = API + '/stream';  // HTTP 长连接
    audio.load();
    audio.play().then(() => {
        STATE.audioOn = true; btn.textContent = '🔊';
    }).catch(() => {
        reconnectTimer = setTimeout(connectStream, 5000);  // 5s 重试
    });
}

// mute/unmute 切换——不断开流连接
btn.addEventListener('click', () => {
    if (STATE.audioOn) {
        audio.pause();  // 只暂停，不断开 HTTP 连接
        btn.textContent = '🔇';
    } else {
        audio.play();   // 恢复播放
        btn.textContent = '🔊';
    }
});

// 错误自动重连
audio.addEventListener('error', () => {
    reconnectTimer = setTimeout(connectStream, 5000);
});
```

关键设计：mute 时只 `pause()` 不清理 `src`。清理 src 再重新设置会导致新的 HTTP 连接在文件中间位置开始，造成 MP3 解码器出错（卡带声）。

## 6. 字幕怎么同步当前播放内容？

前端每 30 秒轮询 `/stream/status`，检测 `version` 字段变化：

```javascript
async function autoRefresh() {
    const status = await fetch('/stream/status').then(r => r.json());
    if (status.version !== STATE.lastStreamVersion) {
        STATE.lastStreamVersion = status.version;
        await loadCurrentSubtitles();  // 有新播单，更新字幕
    }
    if (STATE.tab === 'news') loadNews();       // 刷新新闻列表
    if (STATE.tab === 'podcasts') loadPodcasts(); // 刷新播客列表
}
setInterval(autoRefresh, 30000);
```

version 在每次 `add_to_queue()` 和文件切换时递增，前端响应式更新。

---

# 九、📊 数据归档系统（重点）

## 1. 为什么要做归档？

24/7 系统持续运行，新闻和播客数据不断增长。如果不归档：
- 数据库膨胀，查询变慢
- 新闻列表混入过期内容（昨天的旧闻排在今天新闻里）
- 已播放的播客和新生成的播客混在一起

## 2. is_archived 逻辑删除怎么实现？

```sql
-- 建表时添加 is_archived 字段
CREATE TABLE news (... , is_archived INTEGER DEFAULT 0);
CREATE TABLE podcasts (... , is_archived INTEGER DEFAULT 0);

-- 旧数据库自动迁移（忽略列已存在的错误）
ALTER TABLE news ADD COLUMN is_archived INTEGER DEFAULT 0;
ALTER TABLE podcasts ADD COLUMN is_archived INTEGER DEFAULT 0;
```

查询默认过滤已归档数据：

```python
# app/api/news.py — 默认 WHERE is_archived = 0
conditions = ["is_archived = 0"]
cursor = await db.execute(f"SELECT COUNT(*) FROM news WHERE {' AND '.join(conditions)}", params)

# app/api/podcast.py — 同理
cursor = await db.execute(
    "SELECT * FROM podcasts WHERE is_archived = 0 ORDER BY created_at DESC LIMIT ? OFFSET ?",
    (page_size, offset))
```

## 3. 归档规则是什么？

```python
# app/api/archive.py
@router.post("/news")
async def archive_old_news(days: int = 1):
    """归档 N 天前的新闻"""
    await db.execute(
        "UPDATE news SET is_archived = 1 WHERE is_archived = 0 "
        "AND date(collected_at) < date('now', 'localtime', ?)",
        (f"-{days} days",))

@router.post("/podcasts")
async def archive_played_podcasts():
    """归档已完成的播客（完成超过1小时）"""
    await db.execute(
        "UPDATE podcasts SET is_archived = 1 WHERE is_archived = 0 "
        "AND status = 'completed' "
        "AND datetime(completed_at) < datetime('now', 'localtime', '-1 hours')")
```

## 4. 触发方式有哪些？

| 触发方式 | 实现 |
|---------|------|
| 自动定时 | APScheduler Cron `hour=3, minute=7` 每日凌晨 |
| 手动一键 | Web UI "归档"按钮 → `POST /api/archive/all` |
| API 调用 | `POST /api/archive/news` 或 `/podcasts` |
| 状态查询 | `GET /api/archive/status` 查看活跃 vs 归档统计 |

---

# 十、⚡ 模型服务管理（重点）

## 1. 为什么要做模型服务管理？

传统做法是 LLM 和 TTS 参数硬编码在 `.env` 里，换个模型要改配置文件重启服务。模型服务管理系统解决了这个问题：

- 运行时热切换 LLM/TTS，无需重启
- 支持多个同类型连接并存（DashScope + OpenAI 双 LLM 备选）
- 一键激活切换

## 2. 数据模型

```python
# app/models/model_connection.py
class ModelConnection(BaseModel):
    id: int | None
    name: str           # "DashScope 通义千问"
    service_type: str   # "llm" | "tts"
    provider: str       # "dashscope" | "openai" | "edge_tts" | "doubao"
    base_url: str       # API 地址
    api_key: str        # API Key（响应中自动脱敏）
    model: str          # 模型名（LLM）
    voice: str          # 语音名（TTS）
    is_active: bool     # 是否当前激活
```

## 3. 激活切换怎么实现？

```python
# app/api/model_connections.py
@router.post("/{conn_id}/activate")
async def activate_connection(conn_id: int):
    # 1. 取消同类型所有激活
    await db.execute("UPDATE model_connections SET is_active = 0 WHERE service_type = ?", (svc,))
    # 2. 激活目标连接
    await db.execute("UPDATE model_connections SET is_active = 1 WHERE id = ?", (conn_id,))
```

流水线运行时解析当前激活的连接：

```python
# app/core/llm_factory.py
async def resolve_active_llm() -> dict:
    """从 DB 读取激活的 LLM 连接，fallback 到 .env"""
    cursor = await db.execute(
        "SELECT * FROM model_connections WHERE service_type='llm' AND is_active=1 LIMIT 1")
    row = await cursor.fetchone()
    if row:
        return {"model": row["model"], "base_url": row["base_url"], "api_key": row["api_key"]}
    # Fallback
    return {"model": config.dashscope_model, "base_url": config.dashscope_api_base, ...}

async def create_from_active(temperature=0.7, ...) -> ChatOpenAI:
    conn = await resolve_active_llm()
    return ChatOpenAI(model=conn["model"], base_url=conn["base_url"],
                      api_key=conn["api_key"], temperature=temperature)
```

## 4. 已支持哪些模型服务？

在 `app/models/model_connection.py` 中硬编码：

**LLM 大语言模型**：
| Provider | 显示名 | 模型列表 |
|----------|--------|---------|
| dashscope | 阿里云 DashScope | qwen-plus, qwen-max, qwen-turbo, qwen3.5-122b-a10b, qwen3.5-32b-a10b |
| openai | OpenAI | gpt-4o, gpt-4-turbo, gpt-4o-mini, gpt-3.5-turbo |
| custom_openai | 自定义兼容 | 用户自定义（vLLM/LiteLLM/Ollama） |

**TTS 语音合成**：
| Provider | 显示名 | 特点 |
|----------|--------|------|
| edge_tts | Microsoft Edge TTS | 免费、100+ 语音 |
| doubao | 豆包 TTS | 高音质、需 API Key |
| openai_tts | OpenAI TTS | tts-1/tts-1-hd |


# 十一、🔍 Chroma 向量 RAG + SSE 流式 AI 助手（重点）

## 1. Chroma 双 Collection 架构

每条新闻在 Pipeline Phase 1 采集入库时，同步写入 Chroma 向量库的两个 Collection：

```python
# app/rag/chroma_store.py
def index_news(news_items: list[dict], date_str: str | None = None):
    daily_col = _get_or_create_collection(f"news_{date_str}")  # 日库
    global_col = _get_or_create_collection("news_global")      # 总库
    # 双写
    daily_col.add(ids=ids, documents=docs, metadatas=metadatas)
    global_col.add(ids=ids, documents=docs, metadatas=metadatas)
```

- Collection 命名：`news_20260516`（按日期）、`news_global`（全局汇总）
- 相似度算法：cosine（`hnsw:space: cosine`）
- Embedding：Chroma 内置 all-MiniLM-L6-v2（384 维，免费本地运行）
- 每条 Document 包含：标题 + 摘要 + 来源，Metadata 存标题/来源/URL/分数/日期

## 2. Chat API — SSE 流式问答

```
用户输入 "最近有什么AI大新闻？"
  → POST /api/chat/send
  → Chroma search_news(query, source="global", top_k=5)
  → 拼接 context = "[TechCrunch] OpenAI发布...\n[36氪] 海信与印尼..."
  → llm.astream(QA_PROMPT.format(context, question))
  → SSE 逐 token 推送
```

```python
# app/api/chat.py
@router.post("/send")
async def chat_send(req: ChatRequest):
    # Step 1: Chroma RAG 检索（在生成器外完成）
    results = search_news(message, source="global", top_k=5)
    context = "\n\n".join(f"[{r['source']}] {r['title']}" for r in results)

    # Step 2: 创建流式 LLM
    llm = llm_factory.create_chat_model(temperature=0.5, streaming=True)

    # Step 3: SSE 流式 generator
    async def generate():
        yield _sse({"type":"sources","sources":sources})
        async for chunk in llm.astream(prompt):
            yield _sse({"type":"token","content":chunk.content})
        yield _sse({"type":"done"})

    return StreamingResponse(generate(), media_type="text/event-stream")
```

## 3. SSE 事件类型

| 事件 | type | 说明 |
|------|------|------|
| 状态提示 | status | "检索中..." 等 |
| 来源信息 | sources | [{title, source}] 检索到的新闻 |
| 流式令牌 | token | LLM 逐字输出的内容 |
| 结束 | done | 流结束 |

## 4. 前端 SSE 消费

```javascript
// static/app.js
async function chatSendMsg() {
    const r = await fetch('/api/chat/send', {
        method: 'POST', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({message: msg})
    });
    const reader = r.body.getReader();
    const decoder = new TextDecoder();
    let buf = '';

    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        buf += decoder.decode(value, {stream: true});
        // 按行解析 SSE 事件
        for (const line of buf.split('\n')) {
            if (line.startsWith('data: ')) {
                const d = JSON.parse(line.slice(6));
                if (d.type === 'token') {
                    fullText += d.content;
                    // 实时更新 DOM 显示打字机效果 + 闪烁光标 ▌
                }
            }
        }
    }
}
```

## 5. 前端 Chat UI

- 在主页顶部 Tab 栏最右侧 **"AI助手"** Tab，点击切换到聊天界面
- 对话气泡：用户消息右对齐（金色背景），AI 回复左对齐（卡片+边框），带头像（👤/🤖）
- SSE 流式生成中边框高亮 + 闪烁光标 `▌`
- 4 个快捷提问标签（"今天有什么AI大新闻？"等），点击直接发送
- 回答末尾显示参考来源

```html
<!-- static/index.html -->
<section class="tab-panel" id="panel-chat">
  <div class="chat-window">
    <div class="chat-window-msgs" id="chatMsgs">
      <div class="chat-bubble bot">
        <div class="chat-avatar">🤖</div>
        <div class="chat-bubble-body">
          <div class="chat-bubble-name">AI 新闻助手</div>
          <div>你好！我是基于新闻知识库的 AI 助手...</div>
        </div>
      </div>
    </div>
    <div class="chat-window-input">
      <input id="chatInput" placeholder="问任何关于AI新闻的问题...">
      <button id="chatSendBtn" onclick="chatSendMsg()">发送</button>
    </div>
  </div>
</section>
```

## 6. 全中文播报策略

为保证 24/7 播客听众体验，所有新闻脚本强制使用中文：

- **单阶段 Prompt**：新增 `必须全部使用中文！英文新闻必须翻译为中文`
- **两阶段大纲模板** (`script_outline.j2`)：风格要求改为 `全部使用中文`
- **两阶段对白模板** (`script_dialogue.j2`)：对话风格改为 `必须全部使用中文`
- **Fallback 模板**：`_fallback_en_dialogue()` 从纯英文对话改为中文翻译版
- 技术术语（GPT、API、LLM）保留英文，新闻内容全部中文播报

## 7. 启动自动化检测

```python
# app/main.py lifespan
async def _startup_check():
    await asyncio.sleep(3)
    from app.rag.chroma_store import check_window_has_news
    from app.services.pipeline_service import run_full_pipeline

    has_news = check_window_has_news()  # 检查昨天8:00→今天8:00
    if not has_news:
        logger.info("Startup: news missing → auto-triggering pipeline")
        await run_full_pipeline()
```

检测逻辑：查询 Chroma 日库 Collection 中对应日期的新闻数量。`count > 0` 则跳过，`count == 0` 则自动触发完整流水线（采集→脚本→TTS→播单入队）。

---

# 十一之二、🥝 启动与部署

```bash
# 1. 安装依赖
pip install -e ".[dev]"

# 2. 配置 .env
cp .env.example .env
# 编辑 DASHSCOPE_API_KEY=sk-your-key

# 3. 安装 ffmpeg（音频拼接必需）
# Windows: https://ffmpeg.org/download.html 下载加入 PATH
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg

# 4. 启动
python -m uvicorn app.main:app --host 0.0.0.0 --port 9800

# 5. 浏览器打开 http://localhost:9800
```

---

# 十二、面试 Q&A 话术（高频必问）

## 项目流程类

**Q: 方便把完整流程和技术栈讲一下吗？**
四阶段流水线：Phase1 5个RSS/Web源采集60+条新闻 → 三级去重到~40条 → LLM精排取Top15 → Phase2 智能路由(>5条两阶段大纲→对白)生成双人对话脚本 → Phase3 展开dialogue为60-75个独立TTS任务并发3合成 → Phase4 pydub拼接(300ms交叉淡入淡出,-16dBFS归一化)→插入播放队列队首→/stream HTTP chunked推流→浏览器24/7播放。同时Chromau索引每条新闻到日库+总库。技术栈：Python + FastAPI + LangGraph + Chroma + DashScope + edge-tts + pydub/ffmpeg + APScheduler + SQLite。

**Q: 为什么用 LangGraph 而不是直接串行调用？**
StateGraph 提供 TypedDict 类型安全的状态管理，`Annotated[list, operator.add]` 实现 append-only 错误收集。每个节点是独立 async 函数，可单独测试。后续要加条件分支（如按新闻量走不同模板），用 `add_conditional_edges` 无需改核心代码。

**Q: 24/7 流怎么做到不中断？**
三层保障：① `StreamingResponse` 的 `async def generate()` 是无限循环，只有 `request.is_disconnected()` 才退出；② 队列空时 `_looping=True` 循环最后一个文件；③ 前端 `audio error` 事件 5s 自动重连。mute/unmute 用 `pause()/play()` 不断开 HTTP 连接——清 src 重建会导致 MP3 解码器从中间位置开始乱码，这是早期"卡带声"bug 的根因。

## 脚本生成类

**Q: 两阶段 Prompt 工程具体怎么做？**
新闻 >5 条时走两阶段：Stage1(temperature=0.3) 调 `prompts/script_outline.j2` 生成 `{segments: [{topic, key_points, transition}]}` 大纲；Stage2(temperature=0.8) 调 `prompts/script_dialogue.j2`，输入大纲+新闻+RAG上下文，生成 `[{speaker:"主持人"/"技术专家", text}]`。低温度保结构，高温度保自然。≤5条走单阶段直达节省一次 API 调用。

**Q: 全中文播报怎么保证的？**
四层策略：① 单阶段 Prompt 强制 "必须全部使用中文，英文新闻必须翻译为中文"；② 两阶段大纲模板 (`script_outline.j2`) 风格设为全中文；③ 两阶段对白模板 (`script_dialogue.j2`) 对话规则强制全中文；④ Fallback 模板 `_fallback_en_dialogue()` 从纯英文对话改为中译文版本（三档长度）。技术术语（GPT、API、LLM）保留英文，新闻内容 100% 中文。

**Q: LLM 调用失败怎么兜底？**
四档 Fallback：高重要性(score≥7) 5轮~600字、中重要性(5-6) 4轮~450字、低重要性(<5) 3轮~300字、英文来源中译版。过渡语7种随机变体、专家开场白5种变化。两层 try/except：两阶段失败→单阶段→Fallback，理论 100% 不中断。

**Q: 双人对话怎么让两个角色声音不同？**
主持人用 zh-CN-YunxiNeural（男声·沉稳播音腔），技术专家用 zh-CN-YunyangNeural（男声·明亮新闻腔）。两个男声但音色差异明显——Yunxi低沉平稳，Yunyang明亮有活力——听众能分辨出是两个人在对话。按重要性调速：高分-5%慢速深度解读，中分+5%正常，低分+15%快速过。

## Chroma RAG & SSE Chat 类（面试亮点）

**Q: Chroma 向量数据库怎么设计的？**
双层 Collection 架构：`news_YYYYMMDD`（每日独立）+ `news_global`（全局汇总）。每条新闻 Pipeline 采集后 `index_news()` 双写两个 Collection。`PersistentClient` 本地持久化到 `data/chroma/`，`hnsw:space:cosine` 余弦相似度。Embedding 用 Chroma 内置 ONNX all-MiniLM-L6-v2（384维），完全本地运行，零外部 API 依赖，零费用。

**Q: SSE 流式 Chat 怎么实现的？**
`POST /api/chat/send` 返回 `StreamingResponse(media_type="text/event-stream")`。流程：① 请求进来先在生成器外完成 Chroma `collection.query(texts=[msg], n_results=5)` 语义检索；② 检索结果拼入 QA Prompt；③ `llm_factory.create_chat_model(streaming=True)` 创建流式 LLM；④ `async for chunk in llm.astream(prompt)` 逐 token yield `data: {"type":"token","content":"..."}\n\n`。LLM 必须在生成器外部创建——async generator 内 await 容易出错。

**Q: 前端怎么消费 SSE 流？**
`fetch() + response.body.getReader()` + `TextDecoder`。逐字节读取，按 `\n` 分割，匹配 `data: ` 前缀行，`JSON.parse` 取 type/token。实时 innerHTML 更新 + 闪烁光标 `▌`（CSS `@keyframes blink`）。流结束移除光标，追加参考来源。

**Q: 为什么用 Chroma 内置 Embedding 而不用 DashScope Embedding API？**
Chroma 内置 ONNX all-MiniLM-L6-v2 完全本地运行：① 零 API 费用；② 零网络延迟（<100ms vs API 200-500ms）；③ 新闻文本通常<500字，384维向量足够。DashScope text-embedding-v2 需要 API 调用，增加延迟和费用。项目数据量在十万级，MiniLM 性能完全够用。

**Q: 用户提问 "今天有什么AI大新闻？" 整个链路怎么走的？**
① 前端 JS `fetch('/api/chat/send', {body: {message: "今天有什么AI大新闻？"}})` → ② 后端 `search_news("今天有什么AI大新闻？", source="global", top_k=5)` → Chroma `news_global` Collection 语义检索返回 top 5 → ③ QA Prompt 拼入 context → ④ `llm.astream(prompt)` 逐 token SSE push → ⑤ 前端 ReadableStream 实时渲染气泡 + 闪烁光标 → ⑥ 完成后追加参考来源链接。

## TTS & 音频类

**Q: TTS 适配器模式怎么设计的？**
`BaseTTSAdapter` 抽象基类定义 `synthesize()` + `get_voices()` + `save()` → `EdgeTTSAdapter` / `DoubaoTTSAdapter` 独立实现 → `AdapterRegistry` 全局单例注册。业务代码只调 `adapter_registry.default.save(text, voice, filepath)`，不关心 Provider。和 Spring DI 理念一致，Python 实现。

**Q: 60-75 个 TTS 任务怎么高效完成？**
`asyncio.Semaphore(3)` 控制并发 + 文件缓存（`os.path.exists(filepath) and size>1000` 则跳过）。3 并发是 Edge TTS 最佳平衡点——不触发限速，最大化带宽利用。总耗时 25-75 秒。文件名含 MD5 哈希确保幂等。

**Q: pydub 拼接时 300ms 交叉淡入淡出怎么实现？**
`combined.fade_out(300) + segment.fade_in(300)`。前段渐隐+后段渐显叠加，像 DJ 混音。300ms 是试听确定的最佳值——100ms 切换感明显，500ms 重叠内容混乱。-16dBFS 是 Apple Podcasts/Spotify 推荐的行业标准响度。

## 数据管理与架构类

**Q: 数据库怎么设计的？为什么不用 ORM？**
6 张 SQLite 表：news、podcasts、playlists、pipeline_runs、model_connections、news_sources。aiosqlite 异步 + 原始 SQL。不用 ORM：体量小不需要 ORM 的 Unit of Work/Identity Map；原始 SQL 更透明利于面试解释；无 N+1 查询风险。

**Q: 归档系统怎么做的？数据怎么隔离？**
`is_archived` 逻辑删除（非物理删除）。新闻按日期归档（昨天之前的 `collected_at < date('now','-1 days')`），播客按完成时间归档（1小时前完成的）。每日凌晨 3:07 Cron 自动执行。所有查询默认 `WHERE is_archived=0`。旧数据库 ALTER TABLE 自动迁移兼容。

**Q: 启动自动化怎么做的？**
`lifespan` 中 `asyncio.create_task(_startup_check())` 非阻塞启动。等待 3 秒等服务就绪后，`check_window_has_news()` 查询 Chroma 日库 Collection 的 `count()`。`count==0` 则自动 `await run_full_pipeline()`。北京时间（`ZoneInfo("Asia/Shanghai")`）计算昨天 8:00→今天 8:00 窗口。

**Q: 模型服务怎么热切换？**
前端"模型服务"Tab 添加 LLM/TTS 连接 → `is_active=1`。`llm_factory.create_from_active()` 每次调用时实时查询 `SELECT * FROM model_connections WHERE is_active=1`。切换 LLM（DashScope→OpenAI）无需重启 uvicorn，下次流水线自动用新模型。Fallback：DB 无激活连接时回退到 `.env` 配置。

**Q: 项目中最复杂的一段代码是哪里？**
`stream_service.py` 的 `get_audio_chunk()`。在 `asyncio.Lock` 保护下处理 6 种并发场景：队列空循环最后文件、文件不存在跳过出队、文件切换重置位置、读取异常出队重试、文件播完递归取下一个、同时 add_to_queue 插入新内容。这个函数被 StreamingResponse generator 每秒多次调用，状态一致性要求高。

---

# 十三、简历写法

**AI 新闻播客 Agent — 24/7 不间断智能播客系统 &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; 后端开发 / AI 应用 &nbsp; &nbsp; 2026.03 - 2026.05**

- **项目简介**：基于 LangGraph + FastAPI 构建的全自动 24 小时不间断 AI 新闻播客系统。通过四阶段 Agent 流水线、TTS 适配器模式与 HTTP Live Streaming 联动，实现新闻自动采集→双人对话脚本→多 Provider 语音合成→永不间断流式播放的完整业务闭环。

- **技术栈**：Python, FastAPI, LangGraph, LangChain, edge-tts, pydub/ffmpeg, APScheduler, SQLite, DashScope(通义千问), Jinja2, HTML/CSS/JavaScript, Pydantic

- **负责功能**：
  1. 设计实现 **LangGraph 四阶段流水线**，每个阶段独立 StateGraph 子图 + TypedDict 类型安全状态传递，支持条件路由和错误降级（鲁棒性 99%+）
  2. 实现**两阶段双人对话脚本生成系统**，先大纲后对白的 Prompt 工程 + Fallback 模板保障 24/7 不间断产出
  3. 设计**TTS 多 Provider 适配器模式**（Abstract Adapter + Registry），实现 Edge TTS / 豆包 / OpenAI TTS 可插拔热切换，多角色独立语音分配
  4. 构建**HTTP Live Streaming 24/7 播放系统**，FIFO 智能队列（最新优先）+ chunked transfer，配合前端自动重连 + version 检测
  5. 集成**自动数据归档系统**，按日期/播放状态逻辑删除过期数据，API 默认过滤 + 每日 Cron 自动执行


# 十四、🍿 各模块面试深度问答

## 14.1 新闻采集模块问答

### Q1: 新闻采集流程具体是怎么样的？从触发到入库走一遍。

> APScheduler 每 5 分钟（可配置）触发一次 `scheduled_pipeline_trigger()`。首先检查播放队列时长——如果队列还有超过 10 分钟的内容就跳过（避免浪费 API），少于 5 分钟则提前触发。
>
> 然后进入 Phase 1：`source_registry.load_from_db()` 从 SQLite 加载所有启用的新闻源。目前有 5 个源：机器之心、36氪AI、TechCrunch AI、InfoQ AI、The Verge AI。
>
> `asyncio.Semaphore(3)` 控制最多 3 个源同时抓取。每个源异步 fetch 后，用 `asyncio.gather(*tasks)` 收集所有结果。RSS 源通过 `feedparser.parse()` 在线程池中执行（避免阻塞事件循环），Web 源通过 `httpx` + `BeautifulSoup` 解析。
>
> 每个条目标准化为统一格式：`{title, url, summary, source, source_type, language, priority_weight, content_hash}`。一轮采集约 60 条原始新闻。

### Q2: 三级去重的每一级分别解决什么问题？为什么需要三级？

> - **第一级 Hash 去重（同批次内）**：O(1) 集合查找。解决同一个源或者不同源发布完全相同内容的问题（比如同一篇新闻被多个 RSS 源收录）。MD5(title+url) 作为 hash。
> - **第二级 标题相似度去重**：O(n) 与前序标题逐一比较。解决标题稍有变化但实际是同一新闻的问题。用 `difflib.SequenceMatcher` 计算相似度，阈值 0.85。比如 "GPT-5 震撼发布" vs "OpenAI 震撼发布 GPT-5" 相似度 > 0.85 会被去重。
> - **第三级 数据库查重**：按 url 和 content_hash 查 SQLite。解决与历史已采集新闻的重复。系统运行多轮后，同一新闻不应反复出现。
>
> 如果只用一级去重，要么漏掉很多（Hash 无法处理标题变动），要么误杀（标题相似但实际是不同新闻）。三级组合在一轮 60 条中大概去重到 39 条。

### Q3: LLM 精排是怎么做的？为什么不全部用 LLM 排？

> 对去重后的约 40 条新闻，先做启发式预排序：关键词匹配数 + 来源优先级权重计算 `base_score`。然后只对预排 Top 20 条调用 LLM 精排。
>
> LLM 排名 Prompt 定义四个维度：Technical Breakthrough(3分) + Industry Impact(3分) + Reader Interest(2分) + Timeliness(2分)。让 LLM 返回 `[{url, score:1-10, reason}]`。
>
> 不全部用 LLM 的原因是：一是节省 API 成本（40 条 vs 20 条），二是 LLM 对低质量新闻的评分参考价值不大，启发式预排已经足够过滤。三是 LLM 调用的 token 消耗与 news 数量成正比，控制 batch size 保证速度。

### Q4: 关键词是怎么配置和使用的？boost 和 include 模式有什么区别？

> `.env` 中配置 `NEWS_KEYWORDS=AI,人工智能,大模型,机器学习,芯片,自动驾驶,LLM,GPT,Claude`。
>
> `boost` 模式：关键词匹配数加分，但不强制过滤。匹配到 "GPT" 的新闻 +1 分，不匹配的不扣分。适合通用 AI 新闻采集。
>
> `include` 模式：`importance_score < 6` 的直接丢弃。适合只关注特定领域时，保证新闻列表高度相关。

### Q5: RSS 源抓取失败了怎么办？会中断整个流水线吗？

> 不会。每个源的 `fetch()` 在独立的 async task 中执行，外层有 try/except 包裹。单个源失败只记录到 `fetch_errors` 列表，不影响其他源。
>
> 对于 RSS 格式问题（如机器之心的 RSS 偶尔 malformed），`feedparser` 会设置 `bozo` 标志。代码检查 `feed.bozo and not feed.entries`——如果格式有问题但没有条目则跳过，有部分条目则继续处理。

## 14.2 脚本撰写模块问答

### Q6: 两阶段生成的 Stage 1（大纲）和 Stage 2（对白）各自用的温度为什么不同？

> Stage 1 用 temperature=0.3（低温度）：大纲是结构性任务，需要稳定一致。低温度确保每次生成的 segments 结构相似，topic、key_points、transition 格式统一。
>
> Stage 2 用 temperature=0.8（高温度）：对白是创作性任务，需要自然感和多样性。高温度让对话有活力，不会像两台机器人在念稿。

### Q7: 如果 Stage 1 成功但 Stage 2 失败了，会怎么处理？

> 代码中 Stage 2 有独立的 try/except。如果 Stage 2 失败，直接降级到 `_generate_fallback()`——用预置的对话模板填充所有新闻。不会因为 LLM 单次失败导致流水线中断。
>
> 如果 Stage 1 就失败了，跳过两阶段直接走单阶段 `_generate_single_stage()`，内部也有 try/except → fallback 保护。
>
> 所以整个脚本撰写模块有三层保护：两阶段 → 单阶段 → fallback，理论上 100% 不会中断。

### Q8: Fallback 模板具体怎么设计的？为什么分三档？

> 按重要性分为高/中/低三档，每档轮数不同：
> - 高重要性（score ≥ 7）：5 轮对话，约 600 字。主持人引出 → 专家深度解读 → 主持人追问 → 专家扩展 → 主持人总结
> - 中重要性（score 5-6）：4 轮对话，约 450 字
> - 低重要性（score < 5）：3 轮对话，约 300 字
> - 英文新闻：单独三档，英文对话
>
> 分档的好处是：重要新闻深度讨论，次要新闻快速过。不会出现所有新闻一个长度的问题。
>
> 另外过渡语有 7 种随机变体（"说到AI领域，再来看另一个消息" 等），专家开场白有 5 种变化（"没错"、"对"、"是的"等），模拟自然语言的不重复性。

### Q9: RAG 检索是怎么嵌入到脚本生成流程中的？

> 在 `write_scripts_node()` 中，对每条新闻的标题调用 `retrieve_related_news()`。函数先用 `extract_keywords()`（正则提取中文词 + ≥2 字母的英文词）取 top 4 关键词，然后 SQL `LIKE %keyword%` 在 `news WHERE is_used=1` 中检索。如果找到相关历史新闻，构建 RAG 上下文：
>
> ```
> ## 近期已播报的相关新闻（避免重复，可引用）
> - [36氪AI] GPT-4 发布一周年回顾 (评分8)
> - [机器之心] 大模型价格战持续升级 (评分7)
> ```
>
> 这个上下文被注入到 Prompt 的 `{rag_context}` 占位符中。LLM 在生成脚本时会引用历史新闻——比如 "这让人想起之前报道过的 GPT-4 一周年..."——增强播客的连贯性和深度。

### Q10: 单阶段 Prompt 里为什么用 `{{` 和 `}}`？

> 因为单阶段 Prompt 用 Python 的 `.format()` 方法注入变量。在 `.format()` 中，`{{` 会被转义为单个 `{`，`}}` 转义为单个 `}`。Prompt 中包含 JSON 模板示例：
>
> ```
> [{{"news_url": "...", "dialogue": [{{"speaker": "{host}", "text": "..."}}]}}]
> ```
>
> 经过 `.format(host="主持人", ...)` 后变成：
>
> ```
> [{"news_url": "...", "dialogue": [{"speaker": "主持人", "text": "..."}]}]
> ```
>
> 而两阶段路径用 Jinja2 模板，就不需要这个转义。两种方式并存是因为单阶段保留在代码里方便调试，两阶段用外部 `.j2` 文件方便管理。

## 14.3 TTS 语音合成问答

### Q11: 60-75 个 TTS 任务怎么调度？并发数为什么是 3？

> `asyncio.Semaphore(3)` 控制最多同时 3 个 TTS 调用。Edge TTS 通过 WebSocket 连接 Microsoft 服务器，并发过高可能触发限速。经过实验，3 并发是最佳平衡点——既不触发限速，又能充分利用网络带宽。
>
> 每个 TTS 任务（一段对话 turn）通常 1-3 秒。60-75 个任务 ÷ 3 并发 = 20-25 个批次 × 2 秒 ≈ 40-75 秒完成全部合成。加上缓存检测（已合成的跳过），后续运行更快。

### Q12: 为什么"技术专家"的语音也要选一个不同声音，不能用同一个吗？

> 双人对话的核心是听众能分辨出是两个不同的人在说话。如果主持人和专家用同一个语音（比如都用 YunxiNeural），听起来就像同一个人自言自语，对话感完全丧失。
>
> 选择 YunxiNeural（沉稳播音腔）和 YunyangNeural（明亮新闻腔）是因为：
> - 两者都是男声，风格统一不突兀
> - 但音色差异明显（一个低沉一个明亮），听众能区分
> - 都是 Edge TTS 支持的中文普通话语音，免费稳定
>
> 如果把主持人换成女声（如 XiaoxiaoNeural），对比会更明显，但和"AI科技播客"的定位不太匹配。

### Q13: 语速按重要性调整是为什么？具体怎么配的？

> 重要性高的新闻（如 GPT-5 发布）需要深度解读，语速慢（-5%）给听众思考和消化时间。重要性低的新闻（如某公司融资消息）快速过一遍（+15%），不拖沓。
>
> 心理学研究表明，听众对慢速语音的信息吸收率更高。把珍贵的"慢速"分配给最重要的内容，是播客节奏设计的考量。

### Q14: TTS 适配器模式在面试中怎么描述？

> "我设计了一个 TTS 多 Provider 适配器模式。核心是一个 Abstract Base Class `BaseTTSAdapter`，定义了 `synthesize()` 和 `get_voices()` 两个抽象方法。然后 EdgeTTS、Doubao、OpenAI TTS 各实现自己的 Adapter 子类。全局 `AdapterRegistry` 管理注册和获取，业务代码只依赖抽象接口。"
>
> "这样做的好处：一是 Provider 可插拔，从免费 Edge TTS 切换到商业 TTS 只需改配置。二是降低耦合，核心代码不关心具体实现。三是方便测试，Mock Adapter 绕过真实调用。这和 Java 的 Spring 依赖注入理念一致，只是用 Python 实现。"

### Q15: Edge TTS 有没有限制？会不会突然不能用了？

> Edge TTS 是微软 Edge 浏览器的内置功能，通过 `edge-tts` Python 库用 WebSocket 协议调用微软的 TTS 服务端点。它本身是免费的，没有官方的 API 限制。
>
> 但有两个潜在风险：一是并发过高可能被微软临时限速（所以用 Semaphore(3) 控制）；二是微软可能修改 WebSocket 协议导致 `edge-tts` 库失效（开源库通常会跟进更新）。
>
> 这就是为什么做适配器模式——如果 Edge TTS 哪天不能用了，一键切换到 OpenAI TTS 或豆包 TTS 就行，流水线代码不用改。

## 14.4 音频拼接问答

### Q16: 300ms 交叉淡入淡出怎么实现的？为什么选 300ms？

> pydub 提供了 `fade_out(ms)` 和 `fade_in(ms)` 方法。拼接时：`combined.fade_out(300) + segment.fade_in(300)`。前一段在最后 300ms 音量线性降低到 0，后一段在最前 300ms 音量从 0 升到正常。两段叠加在一起，过渡平顺。
>
> 300ms 的选择是通过试听确定的——100ms 太短，切换感明显；500ms 太长，听起来两段重叠内容混乱。300ms 刚好在人耳感知的"自然过渡"区间内。

### Q17: 音量归一化到 -16 dBFS 是什么意思？

> dBFS（decibels relative to Full Scale）是数字音频的响度单位。0 dBFS 是最大值（削波），负值越低声音越小。-16 dBFS 是播客行业的事实标准（Apple Podcasts、Spotify 都推荐这个水平）。
>
> 代码中：`change = -16.0 - combined.dBFS`，然后 `combined.apply_gain(change)`。意思是：先算出当前响度和目标响度的差距，然后整体调音量。如果当前是 -20 dBFS，就 +4 dB；如果当前是 -12 dBFS（太响），就 -4 dB。

### Q18: ffmpeg 找不到时怎么 fallback？

> `shutil.which("ffmpeg")` 先搜系统 PATH。找不到则遍历 Windows 常见路径（Program Files、C:\ffmpeg\bin、/usr/local/bin）。仍然找不到就降级为 `_simple_concat()`：二进制读取每个 MP3 文件，顺序写入输出文件，文件间插入 0.5 秒静音（`b'\x00' * 8000`）。
>
> 二进制拼接的缺点是：没有交叉淡入淡出，音量不一致，过渡生硬。但它确保了系统在任何环境下都能工作——这在部署到新机器时很重要。

## 14.5 流媒体问答

### Q19: 24/7 流是怎么保证不中断的？

> 三层保障，从里到外：
>
> 第一层（服务端）：`StreamingResponse` 的 `async def generate()` 是一个无限循环，只有 `request.is_disconnected()` 时才退出。队列空时循环最后一个文件（`_looping = True`），不主动返回 EOF。
>
> 第二层（HTTP 协议）：`Transfer-Encoding: chunked` + `Cache-Control: no-cache`。浏览器不缓存，一直等待下一个 chunk。没有 Content-Length，所以浏览器不会判断传输结束。
>
> 第三层（前端）：`<audio>` 标签检测到 error 事件时，5 秒后自动重连。mute/unmute 切换只用 `audio.pause()`/`audio.play()`，不断开 HTTP 连接——清理 src 再重连会导致新流从文件中间开始，MP3 解码器崩溃（"卡带声"bug 的根因）。

### Q20: 为什么新播单插入队首而不是队尾？

> 队尾插入的问题是：如果队列中已有 3 个旧播单，新生成的播单要等 3 个播完才能轮到。对于新闻播客来说，时效性是核心——最新新闻应该最先被听到。
>
> `insert(0, item)` 放在队首后，新内容的延迟从"等 N 个播单"变成"等当前播单结束"，通常从几十分钟降到几分钟。

### Q21: version 计数器是怎么驱动前端更新的？

> `_stream_state["version"]` 在两个时机递增：
> 1. `add_to_queue()` 时 +1（新播单入队）
> 2. `get_audio_chunk()` 中文件切换时 +1（当前播单播完，出队下一个）
>
> 前端每 30 秒调用 `GET /stream/status`，比较返回的 `version` 和本地缓存的 `STATE.lastStreamVersion`。不相等则触发 `loadCurrentSubtitles()` 更新字幕 + `loadNews()` 更新新闻列表。

### Q22: 流式播放的延迟大概多少？

> 从服务端 chunk 到浏览器音频输出的延迟 = 浏览器缓冲延迟 + 网络传输延迟。
>
> 浏览器 `<audio>` 标签对 streaming 源通常缓冲 2-3 秒才开始播放（`preload="none"` 表示不预加载）。网络延迟在本机可忽略（localhost），局域网内 < 50ms。
>
> 所以用户感知的"开机到听见声音"约 2-3 秒。如果服务端队列为空（刚启动，没有播单文件），则需要等第一次流水线完成（约 60-120 秒）。

## 14.6 调度与数据归档问答

### Q23: 调度器的回调注册模式是怎么工作的？

> `pipeline_service.py` 在模块 import 时执行 `register_trigger_callback(scheduled_pipeline_trigger)`，把自己的触发函数注册到 `scheduler.py` 的全局列表 `pipeline_trigger_callbacks` 中。
>
> 当 APScheduler 触发时，`_trigger_pipeline()` 遍历回调列表，逐个 `await callback()`。这种模式的好处是：调度器和业务逻辑完全解耦。scheduler 不 import pipeline_service，pipeline_service 主动注册自己。新增回调只需在目标模块 import 时注册，不影响调度器代码。

### Q24: 数据归档为什么用逻辑删除而不是物理删除？

> 逻辑删除（`is_archived = 1`）相比物理删除（`DELETE FROM`）的优势：
> 1. **可恢复**：如果归档规则有问题，误删的数据可以恢复（`UPDATE SET is_archived = 0`）
> 2. **可审计**：知道"曾经有过哪些数据"，方便统计和分析
> 3. **不影响活跃查询**：查询默认 `WHERE is_archived = 0`，性能不受历史数据影响
> 4. **简单**：SQLite 的 DELETE 在大数据量时可能锁表，UPDATE 原子性更好

### Q25: 为什么归档时间选凌晨 3:07 而不是整点？

> 整点（3:00）是 cron job 的热门时间。选 3:07（加一个随机的分钟偏移）可以减少和其他定时任务（如果有的话）的资源竞争。这是分布式系统中的经典策略——避免"惊群效应"（thundering herd）。
>
> 在本项目中意义不大（因为只是本地单机），但这是一个好的工程习惯，面试时可以提。

## 14.7 模型服务切换问答

### Q26: 模型连接热切换是怎么做到不重启服务的？

> 核心是"运行时解析"模式。`llm_factory.create_from_active()` 在每次被调用时（不是启动时），实时从 SQLite 查询 `WHERE service_type='llm' AND is_active=1`。
>
> 所以用户在前端点击"激活"另一个 LLM 连接（比如从 DashScope 切到 OpenAI）→ API 更新 `is_active` 字段 → 下一次流水线触发时，`create_from_active()` 读到新的激活记录 → 使用新模型。全程不需要重启 uvicorn 或修改 .env。
>
> 这和传统"启动时读取 .env 然后写死"的做法有本质区别。

### Q27: 如果 DB 中没有激活的 LLM 连接怎么办？

> `resolve_active_llm()` 有 fallback 机制：查不到激活记录时，返回 `.env` 中的配置：
> ```python
> return {"model": config.dashscope_model,
>         "base_url": config.dashscope_api_base,
>         "api_key": config.dashscope_api_key}
> ```
> 也就是说 `.env` 里的 DashScope 是永远的后备。即使用户把所有连接都删了，系统还能正常运行。


# 十五、项目各流程耗时分析

| 阶段 | 操作 | 耗时（估算） |
|------|------|-------------|
| Phase 1 | RSS/Web 采集（5 源并发 3） | 3-10 秒（网络依赖） |
| Phase 1 | 三级去重 60→39 条 | < 1 秒（纯内存/DB 查询） |
| Phase 1 | 启发式预排序 + LLM 精排 Top 20 | 3-8 秒（LLM API 调用） |
| Phase 2 | 两阶段 LLM 脚本生成 | 5-15 秒（1-2 次 LLM 调用） |
| Phase 2 | Fallback 检测 + 装配 | < 0.5 秒 |
| Phase 3 | TTS 60-75 个任务（并发 3） | 40-75 秒（Edge TTS WebSocket） |
| Phase 3 | 音频元数据提取 | < 1 秒 |
| Phase 4 | pydub 拼接 60-75 片段 | 3-8 秒 |
| Phase 4 | 入队 + 元数据保存 | < 1 秒 |
| **总计** | **端到端流水线** | **60-120 秒** |

> 耗时大头在 TTS 合成（占 60-70%）。Edge TTS 每个任务 1-3 秒 × 60-75 个 / 3 并发 ≈ 20-75 秒。
> 如果换成 OpenAI TTS 或豆包 TTS，合成速度可能更快（商业 API 通常更快），但有费用。


# 十六、完整的项目文件清单

```
ai-news-podcast-agent/
├── .env                              # 环境变量（API Key、模型配置、TTS参数）
├── .env.example                      # 环境变量模板（不含敏感信息）
├── .gitignore                        # Git 忽略规则
├── pyproject.toml                    # 项目元数据 + 依赖声明
├── README.md                         # 项目说明
├── start-windows.bat                 # Windows 启动脚本
├── stop-windows.bat                  # Windows 停止脚本
├── CLAUDE.md                         # Claude Code 指令
│
├── config/
│   └── news_sources.yaml             # 预设新闻源（5个）
│
├── prompts/                          # 外部化 LLM Prompt 模板
│   ├── script_outline.j2             # 两阶段 Stage1：大纲生成
│   └── script_dialogue.j2            # 两阶段 Stage2：对白脚本
│
├── app/
│   ├── __init__.py
│   ├── config.py                     # Pydantic Settings（.env 管理）
│   ├── main.py                       # FastAPI 入口 + 路由注册 + lifespan
│   │
│   ├── core/
│   │   ├── constants.py              # 命名常量
│   │   ├── database.py               # SQLite 初始化/迁移/种子 5表 + archive migration
│   │   └── llm_factory.py            # LLM 工厂 + 动态连接解析
│   │
│   ├── models/
│   │   ├── news.py                   # NewsItem, NewsListResponse, NewsStats
│   │   ├── podcast.py                # PodcastItem, PodcastListResponse, CurrentPlayback
│   │   ├── playlist.py               # PlaylistItem, PlaylistListResponse
│   │   ├── request.py                # PipelineTriggerRequest, PaginationRequest
│   │   └── model_connection.py       # ModelConnection + 预置服务列表
│   │
│   ├── api/
│   │   ├── health.py                 # GET /api/health
│   │   ├── news.py                   # GET /api/news (archive-filtered)
│   │   ├── podcast.py                # GET /api/podcasts, /current, /{id}/audio, POST /trigger
│   │   ├── sources.py                # CRUD /api/sources
│   │   ├── stream.py                 # GET /stream (24/7), /stream/status
│   │   ├── archive.py                # POST /api/archive/news|podcasts|all, GET /status
│   │   └── model_connections.py      # CRUD + activate + supported list
│   │
│   ├── agents/
│   │   ├── base_state.py             # PipelineState (主流水线 TypedDict)
│   │   ├── news_collector/
│   │   │   ├── state.py              # NewsCollectorState
│   │   │   ├── collector.py          # collect_news 节点
│   │   │   ├── deduplicator.py       # deduplicate_news 节点（三级去重）
│   │   │   └── ranker.py             # rank_news 节点（预排+LLM精排）
│   │   ├── script_writer/
│   │   │   ├── state.py              # ScriptWriterState
│   │   │   └── writer.py             # 两阶段/单阶段 + Fallback + RAG
│   │   ├── podcast_writer/
│   │   │   ├── state.py              # PodcastWriterState
│   │   │   ├── tts_synthesizer.py    # 多角色TTS + 适配器调用
│   │   │   └── audio_processor.py    # 音频验证 + 元数据提取
│   │   └── playlist_manager/
│   │       ├── state.py              # PlaylistManagerState
│   │       ├── concatenator.py       # build_playlist（拼接+存库）
│   │       ├── scheduler.py          # APScheduler setup + archive job
│   │       └── stream_manager.py     # 播放队列管理
│   │
│   ├── services/
│   │   ├── pipeline_service.py       # 4阶段主流水线编排
│   │   ├── news_service.py           # LangGraph 新闻采集子图
│   │   ├── podcast_writer_service.py # LangGraph TTS 子图（已精简）
│   │   ├── playlist_manager_service.py
│   │   ├── audio_service.py          # pydub/ffmpeg 拼接 + ffmpeg 自动发现
│   │   ├── stream_service.py         # HTTP 流媒体队列 + version 管理
│   │   └── tts_service.py            # TTS 服务封装
│   │
│   ├── tts/                          # TTS 适配器模式
│   │   ├── base_adapter.py           # Abstract BaseTTSAdapter
│   │   ├── edge_tts_adapter.py       # Edge TTS 实现
│   │   ├── doubao_tts_adapter.py     # 豆包 TTS 预留
│   │   └── adapter_registry.py       # 全局注册表
│   │
│   ├── sources/                      # 新闻源适配器
│   │   ├── base_source.py            # Abstract BaseNewsSource
│   │   ├── rss_source.py             # feedparser RSS
│   │   ├── web_scraper_source.py     # httpx + BeautifulSoup
│   │   └── source_registry.py        # 注册表（DB + YAML）
│   │
│   ├── tools/                        # LangChain 工具（预留）
│   └── utils/
│       ├── audio_utils.py            # 音频路径/验证
│       ├── text_utils.py             # Hash/相似度/关键词/HTML清洗
│       ├── prompt_loader.py          # Jinja2 模板加载器
│       └── logger.py                 # Loguru 配置
│
├── static/                           # Web 管理面板
│   ├── index.html                    # SPA（4 Tab + 归档按钮）
│   ├── app.js                        # 前端逻辑（autoRefresh/subtitles/audio）
│   └── styles.css                    # 暗色主题
│
├── tests/                            # 自动测试（16 用例）
│   ├── test_prompt_loader.py         # 3 测试
│   ├── test_script_writer.py         # 7 测试
│   └── test_tts_adapter.py           # 6 测试
│
└── data/
    ├── podcast.db                    # SQLite 数据库
    └── audio/
        ├── episodes/                 # 单个 TTS 音频片段（.mp3）
        └── playlists/                # 拼接后的播单文件（.mp3）
```
  5. 集成**自动数据归档系统**，按日期/播放状态逻辑删除，API 默认过滤 + 每日 Cron 自动执行


# 十五、🍿 项目问答&amp;&amp;面经（重点！！85道深度问答）

## 1. 给大家讲一下这个项目用的数据集

> * 首先，新闻源来自 5 个公开 RSS/Web 源（机器之心、36氪AI、TechCrunch AI、InfoQ AI、The Verge AI），完全不需要自建数据集。
> * 对于 LLM 脚本生成，用 DashScope 通义千问的 OpenAI 兼容接口，Prompt 工程 + Fallback 模板保障产出。
> * 对于 TTS 合成，Edge TTS 支持 100+ 语音（中文普通话十余种），免费无需训练。
> * 对于知识检索（RAG），直接查询 SQLite 中 `is_used=1` 的历史新闻，用关键词匹配，不走向量数据库。

## 2. 项目是一个多 Agent 项目吗？链路失败或局部失败时怎么处理

> 不是典型的多智能体架构（每个 Agent 不相互通信），而是单主流水线 + 四个独立 StateGraph 子图的结构。
>
> 链路失败处理：
> 1. 如果是某个 RSS 源抓取失败，跳过该源继续其他源（asyncio.gather 独立异常捕获）
> 2. 如果是 LLM 排名失败，直接使用启发式预排序分数（不阻塞流水线）
> 3. 如果是 LLM 脚本生成失败，自动降级到 Fallback 对话模板（高/中/低三档 + 中英文）
> 4. 如果是 TTS 某个片段失败，记录错误，继续合成其他片段
> 5. 如果 ffmpeg 不可用，降级到二进制简单拼接（b'\x00' 静音间隔）
> 6. 如果流播放队列为空，循环最后一个文件（`_looping = True`），流永不中断
>
> 总之，核心对话/播放功能永远可用，非核心功能失败只做降级，不阻塞主流程。

## 3. 这个项目你遇到的难点是什么？怎么解决的

> 1. 三类并发流程互相干扰——（1）TTS 合成异步（2）音频拼接（3）流式读取。容易出现：拼接还没完成就开始读文件、流读到一半新文件覆盖、TTS 缓存和实时合成竞争。
>
> 解决方案：
> 1. 引入 asyncio.Lock 保护队列状态，`get_audio_chunk()` 和 `add_to_queue()` 互斥
> 2. TTS 合成的输出文件用 `{global_index:04d}_{hash}.mp3` 命名，确保唯一、不冲突
> 3. 拼接阶段独立输出到 `playlists/` 目录，和原始片段 `episodes/` 隔离
>
> 2. 双人对话生成质量问题——单次 LLM 生成 15 条对话，容易结构松散、前后过渡生硬、偶尔出现结束语（破坏 24/7 风格）
>
> 解决方案：
> 1. 两阶段 Prompt（大纲→对白）——先让 LLM 规划结构，再填充对话
> 2. Prompt 中明确禁止结束语（"严禁任何结束语！"列出具体禁词）
> 3. Fallback 模板中也不包含任何结束语
> 4. `is_last` 始终为 `False`
>
> 3. 24/7 流媒体重连问题——用户暂停再播放时出现卡带声
>
> 解决方案：
> 1. mute/unmute 模式替代 disconnect/reconnect——只用 `audio.pause()`/`audio.play()`，不清理 `audio.src`
> 2. 清理 src 再设新的会导致 HTTP 连接从文件中间位置开始，MP3 解码器无法解析——这是卡带声的根因
> 3. 新连接时 `reset_position()` 确保从文件开头开始播放

## 4. LangGraph 里面的每个节点是怎么来的

> 每个节点就是一个 Python async 函数，接受 TypedDict State 作为输入，返回 dict（部分状态更新）。LangGraph 负责按图的边依次调用这些函数，并合并状态。
>
> 四个节点分别是：
> - `run_news_collection(state)` — 调用 news_collector_graph 子图
> - `run_script_writing(state)` — 调用 write_scripts_node
> - `run_tts_synthesis(state)` — 调用 synthesize_audio + process_audio_segments
> - `run_playlist_building(state)` — 调用 build_playlist + stream_service

## 5. LLM 脚本生成温度参数怎么设的？为什么？

> Stage 1（大纲生成）：temperature=0.3。结构性任务，低温度确保每次输出格式稳定一致。
> Stage 2（对白生成）：temperature=0.8。创作性任务，高温度让对话有活力不机械。
> LLM 精排：temperature=0.3。评分任务需要客观稳定。
>
> 这和业界实践一致——比如 OpenAI 的推荐：写作 0.7-0.9，分类/结构化提取 0-0.3。

## 6. 你的管理员有几个？怎么管理配置？

> 所有配置通过 `.env` 文件管理，Web UI 的"模型服务"Tab 可以进行运行时热切换。
> 新闻源管理通过 Web UI 的"源管理"Tab，支持添加/启用/禁用/删除 RSS 和 Web 源。
> 不需要管理员账号系统——这个项目是单向播客广播，没有用户登录需求。

## 7. 多 Provider TTS 和 Edge TTS 的关系？为什么不直接用商业 TTS？

> Edge TTS 是默认提供者（免费、无需 API Key），适配器模式让它成为一个可替换的组件。商业 TTS（豆包、OpenAI TTS）作为预留适配器，需要时可以一键切换。
>
> 不直接用商业 TTS 的原因：
> 1. Edge TTS 完全免费，适合开发和个人使用
> 2. 音质对于新闻播客来说足够好（神经网络语音，不是传统机械音）
> 3. 无调用次数限制，24/7 高频调用不会产生费用
>
> 适配器模式的价值在于：如果未来需要更高音质或更多语言，切换到商业 TTS 只需改配置，不需要改流水线代码。

## 8. 这个项目上线了吗

> 话术：没有上线，是我学习 LangGraph、Agent 架构、TTS 适配器模式时的练手项目。从头到尾自己做的，GitHub 上找不到完全一样的。其他项目也一样，没上线直接说。
>
> 注意：说上线了面试官会接着问压测了吗？QPS 多少？压测数据？监控告警？用户量？——没真实数据的就不要说上线了。

## 9. 向我介绍一下 Edge TTS？

> Edge TTS 是微软 Edge 浏览器内置的文本转语音引擎，基于 Azure Cognitive Services 的神经网络语音合成。
> - 免费、无需 API Key、无需注册
> - 支持 100+ 种语音，覆盖 50+ 种语言
> - 中文普通话支持十余种声音（男声/女声/不同年龄/不同风格）
> - 通过 `edge-tts` Python 库用 WebSocket 协议调用
> - 返回 MP3 格式音频流
>
> 本项目中主持人使用 zh-CN-YunxiNeural（男声·沉稳播音），技术专家使用 zh-CN-YunyangNeural（男声·自信新闻）。

## 10. 脚本生成失败率是多少？怎么保证 24/7 不间断？

> 单次 LLM 调用失败率约 5-10%（网络超时、API 限流等）。但通过三层 Fallback 保护：
> 1. 两阶段失败 → 降级到单阶段
> 2. 单阶段失败 → 降级到 Fallback 模板
> 3. Fallback 模板是纯 Python 字符串拼装，100% 成功
>
> 所以脚本生成成功率 = 100%（含 Fallback）。Fallback 模板生成的内容虽然不如 LLM 生动，但结构完整、没有错别字、24/7 风格正确。

## 11. 项目中的 RAG 是怎么做的？

> 和传统向量检索 RAG 不同，本项目用 SQL 关键词匹配做"轻量级 RAG"：
> 1. 对当前新闻标题调 `extract_keywords()` 提取 top 4 关键词
> 2. SQL `LIKE %keyword%` 在 `news WHERE is_used=1` 中搜索
> 3. 取前 5 条结果，构建 RAG 上下文注入 Prompt
>
> 为什么不用向量数据库？新闻数量通常在几百到几千条，SQL LIKE 足够快（SQLite 有索引）。向量数据库（Chroma/Milvus）对于这个规模是 over-engineering。面试时可以说："项目体量用不上向量数据库，但架构上预留了扩展点——如果需要检索百万级文档，可以用 Chroma 替换 SQL LIKE。"

## 12. 介绍一下你的这个项目？

> 基于 LangGraph + FastAPI 构建的全自动 24 小时不间断 AI 新闻播客系统。从 RSS/Web 新闻采集、三级去重排名、两阶段双人对话脚本生成、多 Provider TTS 语音合成到 HTTP Live Streaming 流式播放，实现新闻→播客的全自动化端到端闭环。纯 Python 技术栈，支持模型服务热切换，适配器模式兼容多家 TTS 引擎。

## 13. 项目的整体流程是什么？

> APScheduler 定时触发（或手动点击）→ Phase 1 从 5 个 RSS/Web 源采集约 60 条新闻 → 三级去重到约 39 条 → LLM 精排取 Top 15 → Phase 2 智能路由（>5两条→两阶段大纲+对白，≤5→单阶段直达）→ Phase 3 展开 dialogue 数组为 60-75 个独立 TTS 任务，并发 3 合成 → Phase 4 pydub 拼接所有片段（300ms 交叉淡入淡出，归一化 -16dBFS）→ 播单插入播放队列队首（最新优先）→ /stream HTTP chunked 传输 → 浏览器 `<audio>` 标签 24/7 连续播放。
>
> 这里可以问大家：最新播单是插在队首还是队尾？
> 队首。因为新闻播客时效性是核心——新内容应该最先被听到，不应该排在一堆旧播单后面。

## 14. 什么是 LangGraph？你项目里怎么用的？

> LangGraph 是 LangChain 推出的 Agent 状态图框架。核心是用有向图定义 Agent 执行流程，每个节点是函数/Agent，节点间通过 TypedDict 类型安全地传递状态。
>
> 本项目中：主流水线用 `StateGraph(PipelineState)` 构建 4 个节点（collect→write_scripts→tts→playlist），线性连接但保留加条件边的扩展能力。每个子阶段（新闻采集、脚本撰写、TTS 合成）也是独立编译的 StateGraph 子图。

## 15. TTS 适配器模式是什么？

> 抽象基类 `BaseTTSAdapter` 定义了统一接口 `synthesize(text, voice)` 和 `get_voices()`。各个 TTS Provider（EdgeTTS、Doubao、OpenAI TTS）各自实现自己的 Adapter 子类。全局 `AdapterRegistry` 管理注册和获取。
>
> 业务代码（`tts_synthesizer.py`）只调 `adapter_registry.default.save()`，不关心具体是哪个 Provider。这和 Spring 的依赖注入理念一致，只是 Python 实现。

## 16. 普通流水线 vs LangGraph StateGraph 的区别

> | 对比 | 普通串行调用 | LangGraph StateGraph |
> |------|------------|---------------------|
> | 状态管理 | 手动传 dict，随迭代增多易出错 | TypedDict 类型约束，编译期检查 |
> | 错误恢复 | 需手写 try/except 链路 | 每个节点独立错误处理 |
> | 条件路由 | if/else 硬编码，难以修改 | 条件边 + 动态路由 |
> | 可测试性 | 只能测试整条链路 | 每个节点可独立单元测试 |
> | 可视化 | 无 | 可导出图结构 |

## 17. 你的流水线流程是什么

> 一个 4 节点线性流水线：collect → write_scripts → tts → playlist。节点间通过 `PipelineState` TypedDict 传递数据。每个节点返回的 dict 被合并到全局 State 中（`Annotated[list, operator.add]` 实现 append-only 字段如 errors、warnings）。

## 18. SQLite 的作用是什么？

> 存储 5 张表（news、podcasts、playlists、pipeline_runs、model_connections）。用 aiosqlite 异步操作 + 原始 SQL，无 ORM。`is_archived` 字段实现逻辑删除。SQLite 文件零配置，适合单机部署。

## 19. 怎么理解大模型的幻觉问题？如何解决？

> 大模型幻觉就是模型在没有依据的情况下编造看似合理但错误的内容。
>
> 本项目中如何减少幻觉：
> 1. Prompt Engineering——强制 LLM 只基于提供的新闻撰写脚本，不编造信息
> 2. RAG——检索历史相关新闻为 LLM 提供上下文参考
> 3. 结构化 JSON 输出约束——要求 LLM 只返回符合格式的 JSON，减少自由发挥空间
> 4. Fallback 模板——LLM 输出质量不达标时直接用预置模板，确保内容准确性
> 5. 去重机制——采集阶段就去掉重复和不可靠来源的新闻

## 20. 你这个项目怎么解决幻觉问题的？

> Prompt 工程 + RAG 检索历史新闻 + 强制 JSON 格式 + Fallback 模板兜底。LLM 被严格约束在已有新闻事实范围内生成内容，不自由发挥。

## 21. 为什么选择 FastAPI 而不是 Flask/Django？

> FastAPI 是 Python 异步框架的首选：
> 1. 原生 async/await 支持——本项目大量 asyncio 操作（TTS、HTTP 采集、流媒体）
> 2. StreamingResponse 开箱即用——24/7 流的实现基础
> 3. 自动 OpenAPI 文档——/docs 端点直接调试 API
> 4. Pydantic 集成——和 Settings 配置管理天然兼容
>
> Flask 需要额外扩展才能支持 async（Flask 2.0+ 才支持），Django 体量太大不适合这种 Agent 项目。

## 22. 为什么选择 edge-tts 作为默认 TTS 引擎？

> 1. 完全免费——24/7 高频调用无经济压力
> 2. 神经网络语音质量——不是传统的机械 TTS
> 3. 中文语音选择丰富——十余种普通话声音可选
> 4. Python 库 `edge-tts` 接口简单——一行 `Communicate(text, voice).save(filepath)`
> 5. 通过适配器模式，随时可切换到商业 TTS

## 23. Chroma 向量数据库你是怎么用的？

> 项目已集成 Chroma 作为向量检索引擎。采用双 Collection 架构：
> - `news_YYYYMMDD`：每日独立 Collection，按日期物理隔离
> - `news_global`：全局总 Collection，汇总所有历史新闻
>
> 每条新闻经过 Pipeline 采集入库时，同步双写到日库和总库。Embedding 使用 Chroma 内置的 all-MiniLM-L6-v2 模型，零外部 API 依赖。
>
> Chat 问答时，前端发送用户问题 → 后端调 Chroma `collection.query(query_texts=[...], n_results=5)` 语义检索 → 将 top 5 结果拼入 Prompt → LLM 流式生成回答。
>
> 为什么选 Chroma？Python 原生 `pip install chromadb` 零配置，多 Collection 天然支持日库隔离，十万级数据性能足够。不需要独立部署的 Milvus/Pinecone。

## 24. 项目中的 Fallback 模板怎么设计的？覆盖哪些场景？

> 四档模板覆盖所有场景：
> - 高重要性（score≥7）：5 轮对话 ~600 字
> - 中重要性（score 5-6）：4 轮对话 ~450 字
> - 低重要性（score<5）：3 轮对话 ~300 字
> - 英文新闻：按分数三档英文字母
>
> 设计原则：对话结构是"主持人引出→专家深度解读→主持人追问→专家扩展→主持人总结"的标准访谈格式。过渡语库 7 种随机变体，专家开场白 5 种变化，避免机械重复感。

## 25. SSE vs HTTP StreamingResponse，你分别用在哪？

> 项目中同时使用了两种流式技术：
>
> **HTTP StreamingResponse（audio/mpeg）**：用于 24/7 音频流。`/stream` 端点持续 yield 4096 字节的 MP3 音频块，浏览器 `<audio>` 标签直接播放。4096 bytes × 8 bits / 128kbps ≈ 256ms 音频/chunk。
>
> **SSE（text/event-stream）**：用于 AI 助手 Chat。`POST /api/chat/send` 返回 `text/event-stream`，事件类型包括：`status`（状态提示）、`sources`（检索结果）、`token`（LLM 逐 token 输出）、`done`（结束）。
>
> 前端用 `fetch() + ReadableStream` 逐行解析 `data:` 前缀的 JSON，实时渲染打字机效果 + 闪烁光标 `▌`。
>
> | 特性 | SSE（Chat） | StreamingResponse（音频） |
> |------|-----------|------------------------|
> | 数据类型 | text/event-stream | audio/mpeg |
> | 前端消费 | fetch + ReadableStream | `<audio>` 标签 |
> | 用途 | AI 问答流式输出 | 24/7 音乐流 |
> | LLM 对接 | llm.astream() 逐 token yield | N/A |

## 26. 为什么用异步而不是多线程？

> Python 的 asyncio 适合 I/O 密集型任务：HTTP 请求（RSS 采集、LLM API）、WebSocket 通信（Edge TTS）、文件读写（流媒体）。
>
> asyncio 相比多线程的优势：
> 1. 单线程事件循环，无 GIL 竞争
> 2. 无竞态条件（不需要锁，除了 queue lock）
> 3. 内存开销小（线程栈 ~8MB/线程，协程 ~KB）
> 4. FastAPI 原生支持 async——框架和业务代码风格一致

## 27. 你的数据库里存了哪些表？

> 5 张表：
> - `news`：新闻数据（标题、URL、来源、重要性分数、is_archived）
> - `podcasts`：播客音频（脚本、音频路径、时长、状态、is_archived）
> - `playlists`：播单（名称、包含的 podcast IDs、音频路径、总时长）
> - `pipeline_runs`：流水线执行纪录（状态、新闻数、播客数、时间）
> - `model_connections`：模型服务连接配置（名称、Provider、API Key、模型名、is_active）
> - `news_sources`：新闻源配置（名称、类型 RSS/Web、URL、是否启用）

## 28. TTS 合成失败是怎么得知的？怎么处理的？

> 1. `synthesize_one()` 中 try/except 捕获每个 TTS 任务异常
> 2. 失败后记录错误信息到 `errors` 列表，不中断其他任务的执行
> 3. `asyncio.gather(*tasks)` + `return_exceptions=True` 行为确保一个失败不影响整体
> 4. 最终日志打印 `{成功数}/{总数} segments synthesized, {错误数} errors`
> 5. 部分失败场景：10 个片段中 2 个失败 → 8 个正常的照常拼接为播单，播放时跳过失败的片段

## 29. 多个新闻源并发采集时会出现冲突吗？

> 不会。每个源的 `fetch()` 在独立的 async task 中执行，返回独立的 `list[dict]`。`asyncio.gather` 收集所有结果后合并到 `all_news` 列表。
>
> `Semaphore(3)` 控制最多 3 个源同时抓取——这解决了两个问题：一是防止被目标服务器视为 DDoS 攻击，二是防止本地网络拥塞。

## 30. 如果使用内存存储，在集群部署时会出现什么问题？

> 本项目用 SQLite 持久化存储 + StreamService 内存队列。集群部署时：
> 1. SQLite 是单机数据库，多实例无法共享（需要换 PostgreSQL/MySQL）
> 2. StreamService 的 `play_queue` 和 `_stream_state` 是进程内存，多实例各自独立
> 3. 前端 `/stream` 连接到哪个实例就听哪个实例的队列——不一致
>
> 解决方案：单机部署（本项目定位）+ 如需集群化，StreamService 换 Redis Stream 或消息队列，DB 换 PostgreSQL。

## 31. 你用的 Embedding 模型是什么？

> 没有使用 Embedding 模型。RAG 检索用的是 SQL `LIKE %keyword%` 关键词匹配，不涉及向量化。这是基于项目体量的务实选择——几千条新闻的检索用 SQL 完全够用。

## 32. 在将文本送入 TTS 时，如何处理长文本？

> Edge TTS 没有文本长度硬限制，但过长的文本会：
> 1. 增加合成耗时（长文本可能需要 10-30 秒）
> 2. 没有自然的停顿感
>
> 本项目的处理方式：一条新闻的脚本被拆分成多个 dialogue turn，每个 turn 约 50-200 字。每个 turn 独立 TTS 合成一个音频文件。这样每段语音自然有停顿（文件切换时的 300ms 交叉淡入淡出），听起来就像真人在对话中自然换气。

## 33. modelfile 里面存的啥？

> 本项目不涉及 Ollama/Modelfile——LLM 通过 DashScope 云端 API 调用，不需要本地部署模型。TTS 通过 Edge TTS 云端 WebSocket 调用，也不需要在本地跑模型。
>
> 如果要本地部署（比如用 Ollama 跑 Qwen），需要写 Modelfile，其中包含：基础模型路径、系统提示词、模型参数、LoRA 权重路径。但这不在本项目的默认架构中。

## 34. SQLite 里面存了哪些表？怎么设计的？

> 5 张核心表：
> - `news`：新闻。url UNIQUE 防重复，is_archived 逻辑删除，collected_at 用于归档判断
> - `podcasts`：播客。script 存完整脚本文本，audio_path 指向 .mp3，status 跟踪完成状态
> - `playlists`：播单。podcast_ids 存 JSON 数组（如 [1,2,3]），一个播单包含多个播客
> - `pipeline_runs`：运行记录。每次流水线执行一行，用于监控和调试
> - `model_connections`：模型连接。service_type CHECK 约束('llm','tts')，支持运行时热切换
> - `news_sources`：新闻源。从 YAML 种子，可以在 Web UI 增删改

## 35. 数据归档失败是怎么得知的？

> 1. 每日归档 cron job `_archive_job()` 有 try/except 包裹，失败会打 error 日志
> 2. 手动归档（Web UI 按钮）有前后端双重反馈：API 返回 `{ok, news_archived, podcasts_archived, total}`  → 前端 alert 显示结果
> 3. `GET /api/archive/status` 可以随时查看活跃 vs 归档数据量，如果归档没生效可以立即发现

## 36. 多个流水线同时触发会冲突吗？

> 目前设计是单一流水线，通过以下机制防止并发冲突：
> 1. APScheduler 的 interval job 不会重叠执行（默认 `coalesce=True`）
> 2. 队列感知触发：`scheduled_pipeline_trigger()` 检查 `queue_duration > 600` 时直接 return
> 3. 手动触发的 `POST /api/pipeline/trigger` 和定时触发理论上可能重叠，但 LangGraph 的 `ainvoke` 创建新的 State，不共享可变状态

## 37. 当多个监听者同时连接流时，StreamService 如何处理？

> `listener_connected()` 跟踪 `_stream_state["listeners"]` 计数。所有监听者共享同一个流位置（从同一个 `_stream_state["position"]` 读取 chunks）。这模拟了传统广播电台——所有人听到的内容同步。
>
> 如果第一个监听者断开只剩后续监听者，流继续从当前位置播放。如果没有监听者了（`listeners==0`），`is_active=False`。新监听者首次连接时（`was_zero=True`），`reset_position()` 重置到当前文件开头。

## 38. 高风险预警怎么做的？

> 本项目是新闻播客，不涉及风险预警。但如果类比参考项目：
> - "高风险"对应本项目的"播放队列严重不足"——`queue_duration < 300s` 时提前触发流水线
> - "预警"对应日志 WARNING `Queue running low`
> - 恢复机制：自动提前触发流水线补充内容

## 39. 为什么要自动写入 Excel？

> 本项目不需要写 Excel——播客是单向广播，听众不需要交互。
> 但如果要加入数据分析功能，可以"将每天生成的播客统计（新闻数、时长、热门话题）写入 CSV/Excel，方便内容运营分析"。

## 40. 数据库查询性能怎么样？大数据量会慢吗？

> SQLite 在十万条以内的单表查询基本是毫秒级。关键索引：
> - `news.url` UNIQUE（自动索引）
> - `idx_news_score` ON `importance_score`（排序查询用）
> - `idx_news_hash` ON `content_hash`（去重查询用）
> - `idx_podcast_news_id`, `idx_podcast_status`
>
> 加上 `is_archived = 0` 过滤后，活跃数据量保持可控。每日归档确保活跃表不会无限膨胀。

## 41. 你的前端有什么特点？

> 1. 原生 HTML/CSS/JS——零构建步骤，零 npm install
> 2. 24/7 播放控制——mute/unmute 切换不断开流连接（解决卡带声 bug）
> 3. 30 秒自动轮询刷新——version 计数器检测内容变化
> 4. 实时字幕——匹配当前播放内容自动更新
> 5. 4 个 Tab（新闻列表、模型服务、源管理、播客回听）
> 6. 进度条可视化——采集触发后显示动画进度条
> 7. 归档按钮——一键清理过期数据

## 42. 项目中最复杂的一段代码是哪里？

> `stream_service.py` 的 `get_audio_chunk()` 函数。它需要在 asyncio.Lock 保护下处理以下并发场景：
> 1. 队列为空 → 循环最后一个文件
> 2. 文件不存在 → 跳过出队
> 3. 文件切换 → 重置位置
> 4. 读取出错 → 异常处理 + 出队
> 5. 文件播完 → 出队递归
> 6. 同时 `add_to_queue()` 在另一端插入新内容
>
> 而且这个函数是在 `StreamingResponse` 的生成器中每秒被调用多次，性能要求高。`async with _queue_lock` 确保状态一致性。

## 43. 如果让你改进这个项目，你会做什么？

> 1. 引入 WebSocket 替代 HTTP polling——前端实时收到新内容通知，不需要 30 秒轮询
> 2. 支持多语种播客——目前中英文双播，可扩展日韩法德等语言
> 3. 引入真正的向量数据库 RAG——用 Chroma 存储历史新闻的 embedding，检索更精准
> 4. 播客个性化——用户可选择感兴趣的主题（AI芯片、大模型、自动驾驶...），系统只播相关新闻
> 5. 添加语音合成质量评估——用 MOS 评分自动评估 TTS 输出质量
> 6. 分布式部署——Redis Stream 替代内存队列，支持多实例水平扩展

## 44. 为什么用 `operator.add` 作为 Annotated 的 reducer？

> LangGraph 中 `Annotated[list[dict], operator.add]` 表示：当多个节点返回同一个字段时，用 `operator.add`（即 list concatenation）合并。这实现了 append-only 的错误收集：每个节点可以独立追加 errors，最终 State 中是所有节点的错误汇总。

## 45. pydub 和 ffmpeg 是什么关系？

> pydub 是 Python 音频处理库（切割、拼接、淡入淡出、音量调整）。ffmpeg 是底层的音视频编解码工具。pydub 本身不编解码——它通过调用 ffmpeg 来完成 MP3 文件的读写。
>
> 所以 pydub 没有 ffmpeg 不能工作——这就是为什么代码中有 `_simple_concat()` fallback。如果 ffmpeg 不可用，直接用 Python `open(file, "rb")` 二进制读取拼接。

## 46. 300ms 交叉淡入淡出具体怎么实现的？

> ```python
> combined = combined.fade_out(300) + segment.fade_in(300)
> ```
> `fade_out(300)` 在前一段音频的最后 300ms 将音量从正常线性降到 0。`fade_in(300)` 在后一段音频的最前 300ms 将音量从 0 线性升到正常。两者叠加在一起时，前一段渐隐 + 后一段渐显 = 平滑过渡。
>
> 为什么不用 `AudioSegment.silent(duration=100)` 插入静音？因为静音会打断节奏，像广播节目中间的广告插播。交叉淡入淡出更像 DJ 混音——听众感觉不到切换。

## 47. asyncio 和 threading 在实际使用中有什么区别？

> asyncio：单线程事件循环，适合 I/O 密集型（网络请求、文件读写）。所有协程在同一个线程中交替执行，不需要 GIL 锁。Python 的 `async/await` 语法让代码看起来像同步的但实质是异步的。
>
> threading：多线程并发，适合 CPU 密集型。但 Python 的 GIL（全局解释器锁）限制了多线程在 CPU 任务上的并行度。每个线程有独立的栈（~8MB），大量线程内存开销大。
>
> 本项目用 asyncio——所有耗时操作（HTTP 请求、TTS WebSocket、文件读写）都是 I/O bound。

## 48. 为什么在 RSS 抓取中用 `run_in_executor`？

> `feedparser.parse(url)` 是同步阻塞函数。如果在 async 函数中直接调用，会阻塞整个事件循环，导致其他协程无法执行。`loop.run_in_executor(None, feedparser.parse, self.url)` 把同步函数放到线程池中执行，主事件循环继续处理其他协程。

## 49. `INSERT OR IGNORE` 比 `INSERT` 好在哪？

> SQLite 的 `INSERT OR IGNORE`：如果插入违反了 UNIQUE 约束（如 `news.url`），则静默跳过，不抛异常。
>
> 相比 `INSERT` + try/except：不需要在 Python 层捕异常，不需要回滚事务，一行 SQL 解决重复插入问题。

## 50. 你的 Python 版本要求是什么？为什么？

> Python 3.9+。因为项目用了 `from __future__ import annotations` 和 `X | None` 联合类型语法（PEP 604），这些在 Python 3.10+ 是原生的，3.9 需要 `from __future__` 导入。选择 3.9 作为最低版本是为了兼容性（Ubuntu 20.04 LTS 自带 Python 3.9）。

## 51. 日志怎么配的？为什么用 Loguru？

> `app/utils/logger.py` 配置了 stdout（彩色）+ 文件（按天轮转，保留 7 天）。Loguru 相比标准 logging 的优势：
> 1. 一行配置：`logger.add("file.log", rotation="1 day", retention="7 days")`
> 2. 彩色输出：异常 traceback 中变量值自动显示
> 3. 结构化日志：`logger.info("{} items", count)` 无需 `%s` 或 f-string
> 4. 异步安全：适合 asyncio 场景

## 52. 项目中有没有做异常监控和告警？

> 没有专门的监控系统（没上线不需要）。但有以下机制：
> 1. 所有异常都有 try/except + Loguru error 日志
> 2. `pipeline_runs` 表记录每次流水线执行状态（成功/失败）
> 3. `_health_check_job()` 每 5 分钟检查队列状态
> 4. 前端 30 秒轮询自动检测内容变化
> 5. 日志文件按天轮转保留 7 天——可以事后排查问题

## 53. Semaphore(3) 能不能改成 Semaphore(5)？会不会更快？

> 理论上会，但实际上 Edge TTS 对于同一 IP 的并发连接数有限制。经过实验，并发 3 时稳定不触发限速，并发 5 时偶尔出现连接被拒绝。3 是在稳定性和速度之间的平衡点。
>
> 对于商业 TTS（如 OpenAI TTS），并发可以更高——因为它们按 API Key 计费，不限连接数。这就是适配器模式的好处：Provider 切换时可以根据目标 API 的特性调整并发参数。

## 54. 前端 `HTMLMediaElement.HAVE_CURRENT_DATA` 是什么？为什么不用了？

> `HTMLMediaElement.HAVE_CURRENT_DATA`（值为 2）表示媒体元素有当前播放位置的数据。对于直播流（`/stream`），这个状态可能在暂停后变得不可靠——流是实时的，暂停后再恢复时之前缓冲的数据已经过期。
>
> 后来改用 `streamLoaded` flag + `audio.src` 检查，更可靠地判断是否需要重新连接。因为对于 HTTP 直播流，唯一可靠的操作是：第一次播放时建立连接（设置 src），暂停时只 `pause()`（不断开），恢复时只 `play()`（复用连接），错误时重建连接。

## 55. 如果完全没任何播单文件（首次启动），流会发生什么？

> `get_audio_chunk()` 返回 `b""`（空字节）。`/stream` 端点每 0.5 秒 yield 一个空字节 `b""`。浏览器 `<audio>` 标签处于"等待数据"状态——显示为无限缓冲。
>
> 直到第一次流水线完成（60-120 秒）生成第一个播单文件后，`get_audio_chunk()` 开始返回有效音频数据，浏览器开始播放。
>
> 改进方案：可以在队列空时生成并发送一段静音音频（比如 100ms 的正弦波 silence），让浏览器保持在"正在播放"状态而不是"正在缓冲"状态。

## 56. 为什么 TTS 文件名用 MD5 哈希？

> `hashlib.md5(f"{title}_{turn_idx}".encode()).hexdigest()[:12]` 生成一个 12 位十六进制字符串作为文件名的唯一标识。
>
> 好处：
> 1. 同一段文本的 TTS 结果文件名固定 → 缓存检测（文件存在且 >1KB 则跳过合成）
> 2. 12 位十六进制有 16^12 ≈ 2.8×10^14 种可能 → 碰撞概率极低
> 3. 文件名不含特殊字符（纯十六进制），跨平台兼容
>
> 前面加上 `{global_index:04d}_` 保证排序和唯一性。

## 57. 为什么要设置 `preload="none"`？

> HTML `<audio preload="none">` 告诉浏览器不要预加载音频数据。对于 24/7 直播流（`src="/stream"`），预加载没有意义——流是实时生成的，预加载的内容转瞬即逝。设 `none` 还避免了浏览器在页面加载时就建立两个 HTTP 连接（一个预加载 + 一个播放）。

## 58. 项目中哪个地方的性能最敏感？

> TTS 合成阶段。60-75 个 TTS 任务 × 平均 2 秒 = 120-150 秒的纯合成时间（并发前）。这是流水线总耗时的 60-70%。
>
> 优化方向：
> 1. 提高并发数（如果换到商业 TTS）
> 2. 缓存利用率——已合成的跳过（增量更新场景）
> 3. 预合成——先合成高重要性新闻，低优先级的排队
>
> 当前 Semaphore(3) + 文件缓存的设计已经在不触发限速的前提下最大化利用了 Edge TTS 的吞吐量。

## 59. 怎么处理中文和英文混合的新闻？

> 在采集阶段，`detect_language()` 统计中文字符占比判断语言：中文占比 > 30% → 中文，否则 → 英文。
>
> 在脚本生成阶段，中文新闻生成中文对话，英文新闻生成英文对话（`_fallback_en_dialogue()`）。
>
> 在 TTS 阶段，中文对话用 `tts_voice_zh`（YunxiNeural/YunyangNeural），英文对话用 `tts_voice_en`（JennyNeural）。
>
> 混合场景：如果一批新闻中同时有中文和英文，播单中会穿插中文和英文片段——这反而让播客听起来更国际化，像 BBC World Service。

## 60. 项目如何保证代码质量？

> 1. `ruff` 代码检查——每次修改后自动 fix，零容忍 lint 错误
> 2. `pytest` 16 个自动化测试——覆盖 TTS 适配器、Prompt 模板、Fallback 脚本
> 3. `black` 格式化——统一代码风格（line-length=120）
> 4. Type Hints——所有函数都有完整的类型标注
> 5. `from __future__ import annotations`——Python 3.9 兼容 X|None 语法

## 61. 新闻去重的阈值为什么选 0.85？

> `SequenceMatcher.ratio()` 的返回值在 0-1 之间，0.85 意味着两个标题有 85% 的字符序列匹配。选 0.85 是通过实际测试确定的：
>
> - 0.80 太敏感——"OpenAI 发布 GPT-5" 和 "Google 发布 Gemini 2.0" 在字符层面也有不少重复（"发布"），容易误杀
> - 0.90 太宽松——"GPT-5震撼发布！OpenAI最强模型来了" 和 "OpenAI震撼发布GPT-5" 相似度高但可能在 0.87 左右，会被漏过
> - 0.85 在召回率和精确率之间取得平衡

## 62. 为什么用 `feedparser` 而不是 `httpx` 直接请求 RSS？

> `feedparser` 是 Python RSS/Atom 解析的标准库，处理了很多边界情况：
> 1. 自动检测 RSS 1.0/2.0/Atom 格式
> 2. 解析 pubDate/dc:date/updated 等多种时间格式
> 3. 处理 malformed XML（bozo 标志）
> 4. 标准化 entry 结构（title/link/summary/content）
>
> 用 httpx 直接请求 + 手动解析 XML 也能做到，但需要处理大量格式差异——feedparser 已经做好了。

## 63. LLM 排名中 Top 20 是怎么选出来的？

> 先去重后的 ~39 条新闻做启发式预排序（关键词匹配 + 来源优先级），按 `importance_score` 降序取前 `max(40, max_items * 2)` 条。然后对前 20 条调用 LLM 精排。
>
> 为什么是 20？这个数字是根据 DashScope API 的 token limit 和速度平衡确定的：20 条新闻的 JSON 序列化后约 3-5K tokens，加上 Prompt 约 5-7K tokens——在大部分模型的安全上下文窗口内，一次 API 调用即可完成。

## 64. Fallback 模板中为什么有一个"历史引用"变量？

> `history_ref` 是从 RAG 检索到的历史新闻引用。在 Fallback 模板中，它被插入到专家的对话中（如"这让人想起之前报道过的 GPT-4 一周年..."）。
>
> 这个设计让 Fallback 模板不完全机械——即使 LLM 调用失败，听众也能听到内容之间的关联性和上下文引用，提升了播客质量的下限。

## 65. 为什么 prompt 要外部化到 .j2 文件？

> 1. 解耦——修改 Prompt 不需要改 Python 代码，不需要重启服务（如果用热加载）
> 2. 可读性——独立的 .j2 文件比 Python 字符串中的 \n 和缩进更容易阅读和编辑
> 3. A/B 测试——可以同时维护多个版本的 Prompt 文件，切换比较效果
> 4. 团队协作——非开发人员（如内容编辑）可以直接修改 Prompt 文件
> 5. 版本管理——Git diff 对独立文件更友好

## 66. `PipelineState` 中的 `Annotated[list, operator.add]` 是什么意思？

> 这是 LangGraph 的 State 合并机制。当多个节点返回同一个键时，默认情况下后者会覆盖前者的值。但 `Annotated[list, operator.add]` 告诉 LangGraph：用 `operator.add`（即 `list1 + list2`）合并，而不是覆盖。
>
> 在 `errors: Annotated[list[str], operator.add]` 中，Phase 1 返回 `["error1"]`，Phase 2 返回 `["error2"]` → 最终 State 中是 `["error1", "error2"]`。实现了"错误追加"而不是"错误覆盖"。

## 67. Web UI 的"模型服务" Tab 是怎么实现热切换的？

> 1. 每个模型连接（LLM/TTS）存储为 `model_connections` 表的一行
> 2. `is_active` 字段标记当前激活的连接
> 3. 前端"激活"按钮 → `POST /api/model-connections/{id}/activate` → 后端 `UPDATE SET is_active=1` + 同类型 `SET is_active=0`
> 4. 下一次流水线触发时，`resolve_active_llm()` 实时查询 `WHERE is_active=1` → 使用新模型
>
> 完全不需要重启 uvicorn 或修改 .env。切换对用户透明。

## 68. 为什么 DashScope 不用 SDK 而用 OpenAI 兼容接口？

> 阿里云 DashScope 提供了官方 Python SDK（`dashscope` 包），但也提供了 OpenAI 兼容的 API 端点（`https://dashscope.aliyuncs.com/compatible-mode/v1`）。
>
> 用 OpenAI 兼容接口的好处：
> 1. `langchain_openai.ChatOpenAI` 直接对接——不需要额外的 Adapter
> 2. 切换到 OpenAI 只需要改 `base_url` 和 `api_key`——代码零改动
> 3. 生态兼容——任何支持 OpenAI API 格式的框架都能用
>
> 这是 DashScope 的官方推荐做法之一（"以 OpenAI 兼容模式访问"）。

## 69. `START/END` 和 `set_entry_point` 在 LangGraph 中是什么？

> `set_entry_point("collect")` 标记第一个节点。`END` 是 LangGraph 内置的终止标记——当执行到指向 `END` 的边时，`ainvoke()` 返回最终的 State。
>
> 如果需要条件路由（而不是固定的线性流水线），可以用 `workflow.add_conditional_edges("node", router_func, {"path_a": NodeA, "path_b": NodeB})` 替代 `add_edge`。本项目的当前设计是线性流水线，但架构上保留了加条件边的能力。

## 70. 你的项目有做 CI/CD 吗？

> 没有正式的 CI/CD（没上线不需要）。但本地开发流程：
> 1. `ruff check app/ --fix` → 代码风格检查
> 2. `pytest tests/ -v` → 16 个自动化测试
> 3. `python -m uvicorn app.main:app --reload` → 热重载开发
>
> 如果要加 CI/CD，可以在 GitHub Actions 中配置：push 触发 → ruff + pytest → 通过则部署。

## 71. 为什么要限制队列长度为 50？

> `deque(maxlen=50)` 限制 `play_queue` 最多 50 个播单。每个播单约 5-10 分钟，50 个 = 250-500 分钟（约 4-8 小时）的内容。
>
> 限制的好处：
> 1. 防止内存泄漏——如果流水线异常高频触发，不会无限积压
> 2. 强制淘汰旧内容——新播单插入队首，旧播单被自然挤出
> 3. 4-8 小时的缓冲对于新闻播客足够了——超过 4 小时的"新闻"已经不算新闻了

## 72. 前端如何检测到新播单并更新字幕？

> 前端每 30 秒调用 `GET /stream/status`，比较返回的 `version` 和 `STATE.lastStreamVersion`：
> ```javascript
> if (status.version !== STATE.lastStreamVersion) {
>     STATE.lastStreamVersion = status.version;
>     await loadCurrentSubtitles();  // 有新播单，更新字幕
> }
> ```
> `version` 在两个时机递增：`add_to_queue()`（新播单入队）+ 文件切换（旧播单播完出队）。前端响应式更新字幕，无需手动刷新。

## 73. 为什么不在 /stream 端点中直接嵌入 metadata？

> 技术上可以用 ID3 tags 或自定义 HTTP 头传递当前播放的元数据。但 `<audio>` 标签的 `src` 指向的是 `audio/mpeg` 流，JavaScript 无法直接读取 HTTP 流的 metadata。
>
> 所以采用了分离的 API：`/stream` 负责音频数据，`/stream/status` 负责元数据（当前文件、版本号、队列长度、字幕数据）。前端轮询 `/stream/status` 来获取元数据。

## 74. `_save_pipeline_run` 为什么用 `loop.create_task` 而不是 `await`？

> `_save_pipeline_run` 是在流水线完成后执行的数据库写入操作。如果用 `await`，它会在流水线返回前阻塞（虽然只有几十毫秒）。用 `loop.create_task(_save())` 创建了一个"fire and forget"任务——流水线立即返回，保存操作在后台异步完成。
>
> 这种模式适合非关键操作：保存失败不影响流水线主流程的返回结果。

## 75. 为什么 `news_collector_graph` 要用 `ainvoke` 而不是直接调函数？

> `news_collector_graph` 是一个编译后的 LangGraph StateGraph。`ainvoke()` 会自动按图的拓扑顺序执行节点，并管理 State 的传递和合并。
>
> 对于新闻采集这个子图来说，它内部有 3 个节点（collect → deduplicate → rank），如果手动调用函数需要手写顺序和 State 传递。用 `ainvoke` 让 LangGraph 管理这些，代码更简洁、类型更安全。

## 76. 处理 JSON 响应时为什么要找 `[` 和 `]`？

> LLM 有时会返回格式不规范的 JSON——比如外面包了 markdown 代码块标记（```json...```），或者混入了自然语言解释。`_parse_llm_response()` 的处理流程：
> 1. 如果以 ``` 开头 → 找到第一个 `[` 和最后一个 `]` 之间的内容
> 2. 如果是纯 JSON 数组 → 直接解析
> 3. 这个策略比正则匹配更鲁棒——适配各种不规范输出

## 77. TTS 文件为什么放在 `data/audio/episodes/` 而不是 tmp？

> `data/audio/episodes/` 是持久化目录。TTS 合成的音频文件会被缓存——同一段文字下次不需要重新合成。放在 tmp 的话，系统重启后缓存丢失，每次都要重新合成（60-75 个 TTS 调用 × 每次启动）。
>
> 播单拼接后的文件放在 `data/audio/playlists/`——这是最终播放的文件。playlists 可以安全删除（下次流水线会重新拼接），但 episodes 是缓存资产。

## 78. 为什么 Python 包里需要 `egg-info`？

> `ai_news_podcast_agent.egg-info/` 是 `pip install -e .` 生成的元数据目录。`-e` 表示"editable mode"——安装后修改源码立即生效，不需要重新安装。egg-info 记录了包的版本、依赖、入口点等信息。

## 79. 你的代码中为什么很多 `# type: ignore[arg-type]`？

> LangGraph 的 `add_node()` 期望的节点函数签名和本项目的 async 函数签名不完全匹配（TypedDict 的协变/逆变问题）。`# type: ignore[arg-type]` 告诉类型检查器忽略这个已知的不匹配。
>
> 这是 LangGraph 的已知限制——在动态图构建中，完全类型安全的节点注册是困难的。ran 不影响运行时正确性。

## 80. 如果 DashScope API 完全不可用，系统会怎样？

> 1. 新闻排名：启发式预排序分数直接使用，跳过 LLM 精排（有 try/except）
> 2. 脚本撰写：全部降级到 Fallback 模板（有 try/except + Fallback 保护）
> 3. TTS：不受影响（Edge TTS 独立于 DashScope）
> 4. 流播放：不受影响（依赖本地文件，不依赖外部 API）
>
> 系统进入"降级模式"——新闻仍然采集、TTS 仍然合成、流仍然播放，只是脚本质量从 LLM 级别降到模板级别。这个设计保证了 24/7 不间断——宁可质量降低，也不能停播。

## 81. 这个项目和其他播客生成项目有什么区别？

> 1. 24/7 不间断——大多数播客生成器是"输入话题 → 生成一期 → 输出文件 → 结束"，本项目是持续运行的流媒体系统
> 2. 全自动新闻采集——不需要手动输入话题，从 RSS/Web 自动获取
> 3. 双人对话——不是单人朗读，是主持人+技术专家双角色对话
> 4. TTS 适配器模式——Provider 可插拔，不同于大多数项目只支持一种 TTS
> 5. 数据归档——过期数据自动隔离，生产环境意识

## 82. 项目为什么没做身份认证？

> 播客是单向广播——听众只接收内容，不产生数据。没有用户注册、登录、评论等需要身份认证的场景。
>
> 如果是需要用户交互的版本（如订阅特定话题、标记已听、收藏），可以加 JWT 或 API Key 认证。但当前定位是"收音机式"的纯广播。

## 83. 你能想到这个项目后续可以怎么扩展吗？

> 1. **多主题频道**：AI新闻频道、科技频道、财经频道——不同频道不同新闻源和 LLM prompt
> 2. **主播语音克隆**：用少量音频样本克隆特定主播的声音（如 GPT-SoVITS），替代 TTS 语音
> 3. **听众互动**：加入"提问→AI 回答"环节，从单向广播变双向互动
> 4. **多平台分发**：推流到 Icecast/Shoutcast 服务器，支持第三方播客客户端订阅
> 5. **内容个性化**：基于听历史，AI 筛选用户更感兴趣的新闻

## 84. 面试官问"你这个项目有什么用"怎么回答？

> 这个项目解决的是 AI 资讯传播的效率问题。传统播客需要人工选题、写稿、录音、后期，成本高、产出频率低。本系统实现全自动化——新闻从发布到变成播客只需要 1-2 分钟（采编+TTS 时间），听众可以像听收音机一样 24 小时获取最新 AI 资讯。
>
> 商业价值：适合车载系统、智能音箱、背景音场景——这些场景需要"永远有内容"，人工生产内容无法满足。技术价值：展示了 AI Agent 流水线、TTS 适配器模式、HTTP Live Streaming 等多项工程能力的综合实践。

## 85. 面试的时候如果被问到不会的问题怎么办？

> 话术："这个问题我在当前项目中没有深入实践过，但我的理解是...（说基本原理）。如果后续需要用到，我会...（说解决方案/学习计划）。"
>
> 不要说"不知道"然后沉默。展示你的学习能力和解决问题的思路比知道答案更重要。
