╔══════════════════════════════════════════════════════════════╗
║  AI Course Studio - 自定义字体目录                          ║
║                                                             ║
║  将字体文件 (.ttf / .ttc / .otf) 放入此目录，               ║
║  Docker 构建时会自动安装到容器中，                           ║
║  解决幻灯片渲染时字体不匹配的问题。                         ║
╚══════════════════════════════════════════════════════════════╝

使用方法
────────

1. 把需要的字体文件复制到这里：
     cp /path/to/PingFang.ttc docker/fonts/

2. 确认文件扩展名为 .ttf、.ttc 或 .otf

3. 重新构建镜像：
     docker compose -f docker/docker-compose.yml build

4. 重新启动服务：
     docker compose -f docker/docker-compose.yml up -d

常见 PPT 字体
──────────────

macOS 制作的 PPT 常用：
  - PingFang SC (苹方)  →  PingFang.ttc
  - Heiti SC (黑体)      →  STHeiti Light.ttc / STHeiti Medium.ttc
  - STSong (宋体)        →  Songti.ttc

Windows/Office 制作的 PPT 常用：
  - Microsoft YaHei (微软雅黑)
  - SimSun (宋体)
  - SimHei (黑体)

提示
────
容器默认已安装 Noto Sans CJK SC 和 Noto Serif CJK SC，
这是一款高质量的开源中文字体，外观接近 PingFang / 微软雅黑。
如果 PPT 使用了专有字体，放入此目录后重建即可。
