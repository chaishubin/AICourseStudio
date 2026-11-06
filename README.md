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
| **A — 教案** | `.docx` / 文本型 `.pdf` / `.epub` | 提取章节并由 LLM 设计课程 | Course JSON + PPTX + SRT + MP4 |
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
# 千问用于课程结构、逐页要点和讲稿生成；也可设置 OPENAI_API_KEY 后选择 ChatGPT
export DASHSCOPE_API_KEY='你的百炼 API Key'
export QWEN_MODEL='qwen3.7-plus'
export DASHSCOPE_IMAGE_MODEL='wan2.7-image'
export OPENAI_API_KEY='你的 OpenAI API Key'
export VOLCENGINE_TTS_APPID='你的火山 AppID'
export VOLCENGINE_TTS_ACCESS_TOKEN='你的火山 Access Token'

# 可选：把预览阶段的 AI 全课质检单独切换到 DeepSeek
export COURSE_REVIEW_PROVIDER='deepseek'
export DEEPSEEK_API_KEY='你的 DeepSeek API Key'
export DEEPSEEK_REVIEW_MODEL='deepseek-v4-pro'

# 输出 course.json、可编辑 PPTX、SRT 和内嵌字幕的 MP4
ai-course-studio lesson.docx --llm \
  --llm-engine qwen \
  --tts-engine volcengine \
  --voice zh_female_vv_uranus_bigtts \
  -o outputs/course

# 只生成离线草稿 Course JSON 和 PPTX，不调用 LLM/TTS
ai-course-studio lesson.docx --no-tts --no-video -o outputs/draft
```

`COURSE_REVIEW_PROVIDER` 支持 `openai`（默认）和 `deepseek`。该配置只影响
确认课程草稿阶段的 AI 抽检/全课二审，不改变课程生成所选的 LLM。使用私有
兼容网关时还可设置 `DEEPSEEK_API_URL`，默认值为 `https://api.deepseek.com`。
默认质检模型为 `deepseek-v4-pro`；优先控制成本时可改为当前 Flash 名称 `deepseek-flash`。

千问默认使用 `qwen3.7-plus`，可通过 `QWEN_MODEL` 和 `QWEN_API_URL` 覆盖；
配置文件中的 `llm_options.model` / `api_url` 优先于环境变量。默认显式关闭思考模式。
课程插图默认使用 `wan2.7-image` 的同步多模态接口，每次只生成一张横图；
`DASHSCOPE_IMAGE_MODEL` 可切换型号，`DASHSCOPE_IMAGE_BASE_URL` 可指定地域或
业务空间域名（例如 `https://你的业务空间ID.cn-beijing.maas.aliyuncs.com`）。
旧 `wanx2.1-t2i-turbo` 仍使用原异步接口，便于回退。

火山语音根据音色自动选择协议：Vivi 2.0（`zh_female_vv_uranus_bigtts`）使用
V3 和 `seed-tts-2.0`，已有旧音色保留 V1。可用
`VOLCENGINE_TTS_API_VERSION=auto|v1|v3`、`VOLCENGINE_TTS_RESOURCE_ID` 和
`VOLCENGINE_TTS_API_URL` 显式指定。V3 支持新版控制台的
`VOLCENGINE_TTS_API_KEY`，也支持原有 AppID / Access Token；凭证须已授权对应语音资源。

质检保留 API 返回的 token 用量。DeepSeek 分时价格及未知型号不再套用陈旧单价，
页面会显示“费用未核算”；如需估算，可按所用服务的价格同时配置
`COURSE_REVIEW_INPUT_USD_PER_MILLION` 和 `COURSE_REVIEW_OUTPUT_USD_PER_MILLION`
（每百万 token 的美元单价）。该数值仍是估算，不代表厂商账单。

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

课程草稿预览中，每页讲稿下方提供「AI 修改本页」。输入理解纠正或表达改进意见，
点击「根据意见重新生成讲稿」，AI 会结合本页原文、当前讲稿和前后页生成新讲稿。
先预览结果，再点击「应用并保存本页讲稿」；随后播放本页，确认新的配音与字幕并重新审核。
此功能使用该课程生成策略中的文本模型，需要配置对应的 API Key。

### Docker 本地开发

默认 Docker 镜像会把 `web/` 和 `vidppt/` 复制进镜像，修改代码后需要重新构建。开发时可叠加源码挂载配置：

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.dev.yml \
  up -d
```

此模式会把 `web/` 和 `vidppt/` 直接挂载进容器，并启用 Flask 自动重载：

- HTML、JS、CSS 修改后刷新浏览器即可生效，开发模式会关闭静态资源缓存。
- Python 修改后服务进程会自动重载，无需重启容器或重建镜像。
- 修改 `pyproject.toml`、Dockerfile、系统字体或系统依赖时，仍需重新构建镜像。
- 自动重载会中断正在执行的本地生成任务；长视频渲染期间应避免修改 Python 文件。

查看自动重载日志：

```bash
docker compose --env-file .env \
  -f docker/docker-compose.yml \
  -f docker/docker-compose.dev.yml \
  logs -f vidppt
```

---

## 跨任务文件缓存

生成课程草稿时，按文件内容 SHA-256 复用 Word/PDF/EPUB 的章节解析结果、PPT 的原始正文/备注/内嵌图片，以及原始 PPT 页面截图。文件名、上传路径或任务 ID 改变不影响复用；重新生成讲稿仍会调用文本模型。教案新生成的 PPT 预览会随新内容重新渲染。

缓存默认存放在 `~/.cache/vidppt/documents`，可通过环境变量 `VIDPPT_DOCUMENT_CACHE_DIR` 指定目录。多进程应使用同一目录；Docker 部署如需跨容器重建保留缓存，请将该目录挂载为持久卷。缓存资源会复制到当前任务目录，删除旧任务不会影响新任务。缓存缺失、损坏或不可写时自动正常处理；首次生成后才会建立缓存，旧任务产物不会自动导入。

解析器版本变化会使对应解析缓存失效；截图沿用渲染签名校验，原文件、原始页面 ZIP、引擎或字体环境变化后重新渲染。显式设置 `skip_existing=False` 仍会强制重渲染。缓存目前不自动过期，可在停止服务后删除缓存目录释放空间。

## 架构

详见 [ARCHITECTURE.md](ARCHITECTURE.md)。

核心数据模型 [`Course`](vidppt/core/course.py) 是整个平台的枢纽。路线 A 的实现入口为
[`CoursePipeline`](vidppt/course_pipeline.py)。

---

## 许可证

MIT

### 授课场景

生成策略支持大学课堂、中小学课堂、零基础入门、职业技能实训、企业内训、考试辅导、大众科普和学术进阶八种场景，可补充授课对象、已有基础、教学目标、表达风格和授课方式。场景要求统一用于教案课程生成、PPT 讲稿生成、单页重写以及 AI 抽检/全课二审；默认大学课堂、录播。录播讲稿不依赖现场回答或分组讨论。配置随任务策略保存，重新生成沿用该任务的场景。关闭 AI 生成时，场景仅用于后续 AI 重写和质检。
