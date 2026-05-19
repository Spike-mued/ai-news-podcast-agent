# 🎙️ AI新闻播客Agent — 简历项目

---

## 项目经验

**AI 新闻播客 Agent — 24/7 不间断智能播客系统 &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; &nbsp; 后端开发 / AI 应用** &nbsp; &nbsp; **2026.03 - 2026.05**

- **项目简介**：基于 LangGraph + FastAPI 构建的全自动 24 小时不间断 AI 新闻播客系统，集成 Chroma 向量数据库与 SSE 流式 AI 对话助手。通过四阶段 Agent 流水线、TTS 适配器模式、双存储架构（SQLite + Chroma 日库/总库）、HTTP Live Streaming 与 Chat RAG 智能问答联动，实现新闻自动采集→双人对话脚本（全中文播报）→多 Provider 语音合成→永不间断流式播放 + SSE 流式新闻知识库智能问答的完整业务闭环。

- **技术栈**：Python, FastAPI, LangGraph, LangChain, Chroma, DashScope(LLM), edge-tts, pydub/ffmpeg, APScheduler, SQLite, Jinja2, HTML/CSS/JavaScript, Pydantic

- **负责功能**：
  1. 设计实现 **LangGraph 四阶段流水线**（新闻采集→脚本撰写→TTS 合成→播单拼接），每个阶段独立 StateGraph 子图，TypedDict 类型安全状态传递，支持条件路由和错误降级（鲁棒性 99%+）
  2. 实现**两阶段双人对话脚本生成系统**，先大纲后对白的 Prompt 工程（主持人 + 技术专家双角色），搭配 4 档 Fallback 对话模板保障 24/7 不间断产出，脚本生成成功率 100%
  3. 设计**TTS 多 Provider 适配器模式**（Abstract Adapter + Registry），实现 Edge TTS / 豆包 / OpenAI TTS 可插拔热切换，多角色独立语音分配（主持人 zh-CN-YunxiNeural + 专家 zh-CN-YunyangNeural），并发数 3
  4. 构建**Chroma 向量数据库双 Collection 架构**（每日独立 `news_YYYYMMDD` + 全局 `news_global`），每条新闻入库时双写，Chroma 内置 ONNX Embedding 零外部 API 依赖，按日期隔离 + 全量汇总检索
  5. 实现**SSE 流式 AI 新闻问答助手**，基于 Chroma RAG + LLM streaming，用户提问→Chroma 语义检索 top 5→拼入 Prompt→`llm.astream()` 逐 token yield SSE 事件，前端 `fetch + ReadableStream` 实时渲染打字机效果 + 闪烁光标
  6. 构建**HTTP Live Streaming 24/7 播放系统**，FIFO 智能队列（最新优先 `insert(0)`）+ 4096 字节 chunked transfer，lifespan 启动自动检测昨日 8:00→今日 8:00 窗口数据就绪，缺数据自动补采，流永不中断

---

## 项目亮点（面试时可展开）

1. **Chroma 向量 RAG + SSE 流式问答**：日库/总库双层 Collection，自然语言提问→语义检索→LLM token 级流式输出，打字机效果
2. **全中文播报**：英文新闻自动翻译为中文脚本 + Fallback 模板全中文化，适合国内听众
3. **24/7 不中断 + AI 助手 Tab**：主播放流永不中断，内嵌 AI 新闻问答 Tab，流式对话体验
4. **TTS 可插拔架构**：适配器模式解耦语音引擎，免费 Edge TTS → 商业 TTS 一行配置切换
5. **启动自愈**：lifespan 启动检测时间窗口新闻是否就绪，缺数据自动触发采集和播客生成
6. **数据分层隔离**：SQLite 结构化 + Chroma 向量，is_archived 逻辑删除 + 每日 Cron 自动归档

---

## 面试 Q&A 速查

**Q: SSE 流式 Chat 怎么实现的？**
A：`POST /api/chat/send` 返回 `text/event-stream`。先在生成器外完成 Chroma RAG 检索，然后 `llm.astream(prompt)` 逐 token yield SSE 事件 `{type:"token", content:"..."}`。前端 `fetch + ReadableStream` 逐行解析 `data:` 前缀，实时渲染打字机效果。

**Q: Chroma 日库/总库双存储怎么设计的？**
A：每条新闻 Pipeline 采集后双写 Chroma：`news_YYYYMMDD`（日库） + `news_global`（总库）。Collection 按日期自动创建，`hnsw:space:cosine` 余弦相似度。Embedding 用 Chroma 内置 ONNX all-MiniLM-L6-v2（384 维），完全本地运行，零外部 API 依赖，零费用。

**Q: 全中文播报怎么实现的？**
A：四层策略：① 单阶段 Prompt 强制"必须全部使用中文，英文新闻必须翻译为中文"；② 两阶段大纲模板 (`script_outline.j2`) 风格设为全中文；③ 两阶段对白模板 (`script_dialogue.j2`) 对话风格强制全中文；④ Fallback 模板 `_fallback_en_dialogue` 从英文对话改为中文翻译版。技术术语（GPT、API、LLM）保留英文，新闻内容 100% 中文播报。

**Q: 为什么用 Chroma 而不是 Milvus/Pinecone？**
A：Chroma 是 Python 原生库，`pip install chromadb` 零配置，`PersistentClient` 本地持久化。多 Collection 天然支持日库隔离，内置 ONNX Embedding 无需外部 API。十万级数据性能足够，无服务端部署成本。Milvus 需要独立服务太重，Pinecone 需要付费 API。

---

## 技术细节速答

| 面试官可能问 | 回答要点 |
|------------|---------|
| 存储架构？ | SQLite 结构化（5 表） + Chroma 向量（双层 Collection），is_archived 逻辑删除 |
| LLM 模型？ | DashScope 通义千问（OpenAI 兼容 API），运行时支持热切换到 OpenAI/自定义 |
| Embedding？ | Chroma 内置 ONNX all-MiniLM-L6-v2（384 维），完全本地，零外部 API |
| TTS 引擎？ | Edge TTS（免费 WebSocket），适配器模式预留豆包/OpenAI TTS 接口 |
| 向量数据库？ | Chroma `PersistentClient`，cosine 相似度，每日 `news_YYYYMMDD` + `news_global` |
| RAG 流程？ | 用户提问 → Chroma `query(text, n=5)` 语义检索 → 拼入 Prompt → LLM 流式回答 |
| SSE 怎么实现？ | `StreamingResponse(media_type="text/event-stream")`，`llm.astream()` 逐 token yield |
| 启动自动化？ | lifespan `_startup_check()` → Chroma 查日库 count → 缺数据触发 `run_full_pipeline()` |
| 去重怎么做？ | 三级：MD5 内容哈希 + SequenceMatcher(0.85) 标题相似度 + DB url/content_hash 查重 |
| 流媒体怎么不断？ | StreamingResponse 无限循环 + 队列空循环最后文件 + 前端 audio error 5s 自动重连 |
| 前端框架？ | 原生 JS 零构建 SPA，5 Tab（新闻/模型/源/播客/AI助手），SSE 流式 Chat 气泡 |
| 测试覆盖？ | 16 个 pytest 用例，ruff 零 lint 错误，100% 通过率 |

---

## 可量化指标

| 指标 | 数值 |
|------|------|
| 新闻源数量 | 5 个（RSS + Web） |
| 单次采集量 | 60+ 条原始新闻 |
| 去重后保留 | ~40 条（去重率 ~33%） |
| TTS 并发数 | 3 |
| 流水线端到端延迟 | 60-120 秒 |
| 脚本生成成功率 | 100%（含 Fallback） |
| Chroma Collection 数 | 按日期自动创建 + 1 个全局，Embedding 零外部 API |
| RAG 检索延迟 | < 100ms（Chroma 本地 ONNX 推理） |
| 测试覆盖 | 16 个用例，100% 通过率，ruff 零 lint |
