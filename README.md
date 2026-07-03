# AI Course Studio

**从教案/PPT 到课程视频、幻灯片、HTML 的 AI 课程生产平台。**

AI Course Studio 是一个完整的课程生产流水线。它把一份教学内容（教案 Word/PDF，或演示文稿 PPT）经过 AI 文档理解与知识建模，生成三种格式的教学产出：配音视频（MP4）、教学幻灯片（PPTX）、互动网页（HTML）。

```
                 教案（Word/PDF）          演示文稿（PPT）
                       │                       │
                       ▼                       ▼
              Document Understanding      PPT Parser
             （Docling / MinerU）      （保留内容和样式）
                       │                       │
                       └───────┬───────────────┘
                               ▼
                      Course Knowledge Model
                         （Course JSON）
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       PPTX Renderer    Video Renderer     Web Renderer
       教学幻灯片        配音课程视频        互动 HTML 课程
```

---

## 两条输入路线

| 路线 | 输入 | 处理方式 | 输出适用性 |
|------|------|----------|-----------|
| **A — 教案** | Word/PDF 教案文档 | Docling/MinerU 理解章节结构、知识点 | PPTX + MP4 + HTML 全量输出 |
| **B — PPT** | `.ppt` / `.pptx` 文件 | 保留原内容和视觉样式截图 | 视频优先，保持原作者的设计 |

路线 A 适合"从零生成一门课"，路线 B 适合"把已有的精美 PPT 转为视频"。

---

## 三路渲染器

- **PPTX Renderer** — 生成可编辑的 PowerPoint 教学幻灯片
- **Video Renderer** — 合成配音讲解视频（MP4），支持 TTS + 数字人 + 字幕
- **Web Renderer** — 生成交互式 HTML 课程页面，可嵌入 LMS

现有代码已实现完整的 **路线 B → Video Renderer** 管道。路线 A 和其他渲染器在规划中。

---

## 快速开始（路线 B — PPT 转视频）

```bash
# 安装
pip install ai-course-studio

# 一路默认，PPT 转视频
ai-course-studio input.pptx

# 使用 MiniMax TTS（需设置环境变量 MINIMAX_API）
ai-course-studio input.pptx --tts-engine minimax

# 启用 LLM 文本摘要
ai-course-studio input.pptx --llm

# 启用数字人
ai-course-studio input.pptx --face face.jpg
```

完整参数列表请参见 [CLI_GUIDE.md](CLI_GUIDE.md)。

---

## Web 界面

```bash
cd web && python app.py
```

浏览器打开 `http://localhost:5000`，拖拽上传 PPT 即可在线转换。

---

## 架构

详见 [ARCHITECTURE.md](ARCHITECTURE.md)。

核心数据模型 [`Course`](vidppt/core/course.py) 是整个平台的枢纽，所有输入路线和输出渲染器共享同一个结构化课程表示。

---

## 许可证

MIT
