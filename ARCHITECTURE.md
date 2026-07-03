# AI Course Studio 架构设计

## 设计目标

1. **Course 为中心** — 所有输入路线和输出渲染器共享同一个结构化课程知识模型
2. **双输入路线** — 教案理解（路线 A）和 PPT 保留原样（路线 B）处理不同的输入场景
3. **三路渲染器** — PPTX、MP4、HTML 三种输出共享同一份 Course 数据
4. **增量演进** — 现有视频管线作为 Video Renderer 自然融入新架构
5. **模块化** — 各组件可独立开发、测试、替换

---

## 系统总览

```
┌─────────────────────────────────────────────────────────────────────┐
│                         AI Course Studio                           │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  输入层                                        输出层               │
│  ┌─────────┐   ┌──────────────────┐    ┌──────────────────┐        │
│  │ 路线 B  │   │    路线 A        │    │  PPTX Renderer   │        │
│  │ PPT 文件 │   │ Word/PDF 教案   │    │  (规划中)         │        │
│  │    ↓    │   │    ↓             │    └──────────────────┘        │
│  │PPT Parser│   │ Docling/MinerU  │    ┌──────────────────┐        │
│  │(保留样式)│   │ 文档理解        │    │  Video Renderer  │        │
│  └────┬────┘   └──────┬──────────┘    │  (现有 pipeline)  │        │
│       │               │               └──────────────────┘        │
│       └───────┬───────┘               ┌──────────────────┐        │
│               ▼                       │  Web Renderer    │        │
│      ┌────────────────┐               │  (规划中)         │        │
│      │   Course JSON  │               └──────────────────┘        │
│      │ (核心数据模型)  │                                            │
│      └────────────────┘                                            │
│               │                                                    │
│               ▼                                                    │
│      ┌────────────────┐                                            │
│      │    Web 编排层   │  ← 编辑 Course、选择渲染器、预览、下载    │
│      └────────────────┘                                            │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 核心数据模型

### Course（课程知识模型）

`Course` 是整个平台的枢纽数据结构，定义在 [`vidppt/core/course.py`](vidppt/core/course.py)：

```
Course
 ├── title: str              课程名称
 ├── description: str        课程描述
 ├── source_type: str        来源类型："lesson_plan" | "presentation"
 ├── source_path: Path       原始文件路径
 ├── sections: list<Section> 课程章节/页面列表
 └── metadata: dict          扩展元数据

CourseSection
 ├── id: str                 章节标识
 ├── title: str              章节标题
 ├── script: str             讲解脚本/逐字稿
 ├── knowledge_points[]      知识点列表
 ├── slide_image: Path       幻灯片截图(路线B保留原设计)
 ├── audio: Path             配音音频文件
 ├── duration: float         章节时长(秒)
 └── metadata: dict          扩展元数据

KnowledgePoint
 ├── id: str                 知识点标识
 ├── title: str              知识点标题
 ├── content: str            知识点内容
 └── order: int              排序序号
```

**设计要点：**

- 路线 A（教案）的章节对应教案的"节"，路线 B（PPT）的章节对应幻灯片的一"页"
- `slide_image` 是路线 B 的核心资产——保留原 PPT 的每一页视觉设计
- `script` 是供 TTS 引擎使用的讲解文本，可通过 LLM 改写
- `knowledge_points` 让结构化知识在 HTML/PPTX 渲染器中可以做更多交互展示

### 与旧模型的兼容

现有的 `DocumentContent` / `PageContent` / `ProcessConfig` 模型保留不动，`Course` 是一个新的、语义更丰富的上层模型。

```
路线 B 流程：
  PPT → PPTProcessor → DocumentContent → Course（自动映射）
                                        → Video Renderer（使用现有 pipeline）
```

现有代码在 `vidppt/core/models.py` 中保持不变。

---

## 路线 A — 教案输入（规划中）

```
Word/PDF 教案文档
        │
        ▼
  ┌─────────────────┐
  │ Document        │  Docling: 解析章节结构、标题层级、表格、公式
  │ Understanding   │  MinerU:  中文文档理解，提取知识单元
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ Course Builder  │  将结构化文档映射为 Course JSON
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ Content         │  AI 生成：补充讲解脚本、设计幻灯片主题
  │ Enrichment      │  知识点提取、学习目标识别
  └────────┬────────┘
           ▼
  Course JSON → 三路渲染器（PPTX / MP4 / HTML）
```

**涉及的组件：**

- `vidppt/ingestion/` — 文档理解与 Course 构建
  - `docling_adapter.py` — Docling 集成
  - `mineru_adapter.py` — MinerU 集成
  - `course_builder.py` — 结构化文档 → Course 映射
  - `enrichment.py` — AI 补充生成（讲解脚本、知识点提取）

---

## 路线 B — PPT 直接输入（已实现）

```
PPT (.ppt / .pptx)
        │
        ▼
  ┌─────────────────┐
  │ PPTProcessor    │  提取文本框内容 + 内嵌图片
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ Slide Renderer  │  Spire / LibreOffice → PNG 截图
  └────────┬────────┘
           ▼
  ┌─────────────────┐
  │ Course Mapper   │  PageContent → CourseSection 映射
  └────────┬────────┘
           ▼
  Course JSON → Video Renderer（保持原视觉设计）
```

**现有实现：**
- `vidppt/processors/ppt_processor.py` — 内容提取与页面渲染
- `vidppt/pipeline.py` — 流程编排（TTS + 视频合成）
- `vidppt/engines/tts/` — TTS 引擎（edge-tts / minimax）
- `vidppt/engines/llm/` — LLM 文本摘要（minimax）
- `vidppt/utils/video_composer.py` — 视频合成
- `vidppt/video_composer/` — 数字人叠加合成

---

## 三路渲染器

所有渲染器消费同一个 `Course` 数据，各自专注产出格式：

### PPTX Renderer（规划中）
- 根据 Course JSON 生成可编辑的 PowerPoint 文件
- 路线 A：AI 生成幻灯片布局和内容
- 路线 B：从原始 PPT 还原编辑能力

### Video Renderer（已实现，当前默认输出）
- 逐页使用 `slide_image` 作为视频帧（路线 B 保留原设计）
- 用 `script` 生成 TTS 音频
- 合成带配音的视频 MP4
- 可选：数字人叠加、字幕生成

### Web Renderer（规划中）
- 生成交互式 HTML 课程页面
- 支持知识点导航、脚本展示、音频同步播放
- 可嵌入 LMS（如 Moodle、Canvas）

---

## Web 编排层

`web/app.py` 提供 REST API 和前端界面：

| 端点 | 功能 | 状态 |
|------|------|------|
| `/api/upload` | 上传 PPT/教案文件 | 已实现 |
| `/api/convert` | 启动路线 B 视频转换 | 已实现 |
| `/api/progress/<task_id>` | SSE 进度推送 | 已实现 |
| `/api/tasks` | 任务列表 | 已实现 |
| `/api/course` | Course JSON 查询/编辑 | 规划中 |
| `/api/render/<format>` | 指定渲染器输出 | 规划中 |

未来 Web 界面将从"上传→转换"演进为"课程编辑工作室"：
1. 上传教案/PPT → 生成 Course JSON
2. 在 Web 中编辑 Course（title、script、knowledge_points）
3. 选择输出格式（PPTX / MP4 / HTML）
4. 预览和下载

---

## 当前代码文件结构

```
vidppt/                   核心 Python 包
├── __init__.py           项目入口，导出版本号和新版 Course 模型
├── cli.py                命令行入口
├── pipeline.py           流程编排（TTS + 视频合成）
│
├── core/                 核心抽象层
│   ├── interfaces.py     抽象基类（DocumentProcessor, TTSEngine...）
│   ├── models.py         旧数据模型（DocumentContent, ProcessConfig）
│   ├── course.py         新数据模型（Course, CourseSection, KnowledgePoint）
│   └── registry.py       处理器注册机制
│
├── processors/           文档处理器
│   ├── ppt_processor.py  PPT 处理器（内容提取 + 页面渲染）
│   └── pdf_processor.py  PDF 处理器
│
├── engines/              引擎实现
│   ├── tts/              TTS 引擎（edge-tts, minimax）
│   ├── llm/              LLM 引擎（minimax）
│   └── ocr/              OCR 引擎
│
├── video_composer/       数字人视频合成
│   └── composer.py       数字人叠加合成引擎
│
└── utils/                工具
    ├── video_composer.py 普通视频合成
    ├── audio_cache.py    音频缓存管理
    ├── config_loader.py  配置文件加载
    ├── config_converter.py 配置转换
    ├── progress.py       进度跟踪
    └── logger.py         日志配置

web/                      Web 服务
├── app.py                Flask 后端
├── templates/index.html  前端页面
├── static/css/main.css   样式
└── static/js/main.js     前端逻辑

tests/                    测试
├── unit/                 单元测试
└── integration/          集成测试

docker/                   Docker 部署配置
datas/                    示例数据
examples/                 示例配置文件
```

---

## 增量演进路线

```
Phase 0（当前）：路线 B 视频输出（PPT → MP4）
├── CLI + Web 转换
├── TTS（edge-tts / minimax）
├── LLM 文本摘要
└── 数字人叠加

Phase 1（近期）：重塑叙事 + Course 模型
├── ✅ 项目命名改为 AI Course Studio
├── ✅ 文档更新（README / ARCHITECTURE）
├── ✅ Course 数据模型上线
├── Course ↔ DocumentContent 映射
└── Web 界面品牌更新

Phase 2：路线 A 初版
├── Docling / MinerU 集成
├── Course Builder
├── AI 内容补全（脚本生成、知识点提取）
└── Web Course 编辑器

Phase 3：三路渲染器
├── PPTX Renderer
├── Web Renderer
└── 统一的渲染器接口抽象
```
