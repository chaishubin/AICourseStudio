# AI Course Studio

**从教案/PPT 到课程视频、幻灯片、HTML 的 AI 课程生产平台。**

AI Course Studio 把 Word/PDF 教案经过内容理解与课程建模，生成可编辑
PPTX、逐页讲稿、配音、SRT 字幕和 MP4 课程视频；也可以直接把已有 PPT
转换为视频。

```
                 教案（Word/PDF）          演示文稿（PPT）
                       │                       │
                       ▼                       ▼
              Document Ingestion          PPT Parser
              + AI Course Builder      （保留内容和样式）
                       │                       │
                       └───────┬───────────────┘
                               ▼
                      Course Knowledge Model
                         （Course JSON）
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
       PPTX Renderer    Video Renderer
       可编辑幻灯片       配音+字幕视频
```

---

## 两条输入路线

| 路线 | 输入 | 处理方式 | 输出适用性 |
|------|------|----------|-----------|
| **A — 教案** | `.docx` / 文本型 `.pdf` | 提取章节并由 LLM 设计课程 | Course JSON + PPTX + SRT + MP4 |
| **B — PPT** | `.ppt` / `.pptx` 文件 | 保留原内容和视觉样式截图 | 视频优先，保持原作者的设计 |

路线 A 适合"从零生成一门课"，路线 B 适合"把已有的精美 PPT 转为视频"。

---

## 三路渲染器

- **PPTX Renderer** — 生成可编辑的 PowerPoint 教学幻灯片
- **Video Renderer** — 合成配音讲解视频（MP4），支持 TTS + 数字人 + 字幕
扫描版 PDF 当前需要先经过 OCR；Web 课程编辑器仍在规划中。

---

## 快速开始（路线 A — 教案生成课程）

```bash
# MiniMax 用于课程结构、逐页要点和讲稿生成
export DASHSCOPE_API_KEY='你的百炼 API Key'
export VOLCENGINE_TTS_APPID='你的火山 AppID'
export VOLCENGINE_TTS_ACCESS_TOKEN='你的火山 Access Token'

# 输出 course.json、可编辑 PPTX、SRT 和内嵌字幕的 MP4
ai-course-studio lesson.docx --llm \
  --llm-engine qwen \
  --tts-engine volcengine \
  --voice zh_female_cancan_mars_bigtts \
  -o outputs/course

# 只生成离线草稿 Course JSON 和 PPTX，不调用 LLM/TTS
ai-course-studio lesson.docx --no-tts --no-video -o outputs/draft
```

路线 A 的主要产物：

```text
outputs/course/
├── course.json
├── lesson.pptx
├── lesson.srt
├── lesson.mp4
└── 1..N/audio.mp3
```

也可以直接使用
[`examples/config_qwen_volcengine.yaml`](examples/config_qwen_volcengine.yaml)。

---

## Web 账号与数据隔离

Web 工作台默认使用 `VIDPPT_AUTH_USERNAME` / `VIDPPT_AUTH_PASSWORD`
配置一个超级管理员账号。需要多账号时，可以在 `.env` 中设置
`VIDPPT_USERS`，普通账号只能查看和操作自己创建的任务，`super_admin`
可以查看全部任务和操作日志。

```bash
VIDPPT_USERS='{
  "admin": {"password": "admin-password", "role": "super_admin"},
  "teacher": {"password": "teacher-password", "role": "user"}
}'
```

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

### Docker 本地开发

默认 Docker 镜像会把 `web/` 和 `vidppt/` 复制进镜像，修改代码后需要重新构建。开发时可叠加源码挂载配置：

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.dev.yml \
  up -d
```

此模式下，前端模板、JS、CSS 修改后刷新浏览器即可生效；Python 后端修改后重启容器即可，无需重新构建镜像。

---

## 架构

详见 [ARCHITECTURE.md](ARCHITECTURE.md)。

核心数据模型 [`Course`](vidppt/core/course.py) 是整个平台的枢纽。路线 A 的实现入口为
[`CoursePipeline`](vidppt/course_pipeline.py)。

---

## 许可证

MIT
