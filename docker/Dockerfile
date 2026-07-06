 FROM docker.m.daocloud.io/library/ubuntu:24.04
 
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=zh_CN.UTF-8
ENV LC_ALL=zh_CN.UTF-8
ENV PYTHONIOENCODING=utf-8
ENV PYTHONUTF8=1

# 1. 系统基础包 + 中文 locale + 字体 + LibreOffice + poppler
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3-pip python3-venv \
    locales \
    fonts-noto-cjk fonts-droid-fallback fonts-wqy-zenhei fonts-wqy-microhei \
    libreoffice-impress libreoffice-common \
    libreoffice-writer libreoffice-gtk3 \
    poppler-utils \
    ffmpeg \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# 2. 生成中文 locale
RUN locale-gen zh_CN.UTF-8 && update-locale LANG=zh_CN.UTF-8

# 3. 字体配置（Noto Sans CJK SC 优先，回退 Droid Sans）
RUN rm -f /etc/fonts/conf.d/40-wqy-microhei.conf /etc/fonts/conf.d/90-non-tt-wqy-microhei.conf
COPY docker/99-vidppt-fonts.conf /etc/fonts/conf.d/99-vidppt-fonts.conf

# 4. 安装自定义字体（放入 docker/fonts/，留空则跳过）
COPY docker/fonts/ /usr/local/share/fonts/custom/
RUN fc-cache -fv

# 5. 创建工作目录
WORKDIR /app

# 6. 安装 Python 依赖（利用缓存层）
COPY pyproject.toml .
RUN pip3 config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple && \
     pip install --break-system-packages --no-cache-dir \
    "python-pptx>=1.0.2" \
    "python-docx>=1.1.0" \
    "Pillow>=10.0.0" \
    "spire.presentation>=9.0.0" \
    "edge-tts>=7.2.8" \
    "moviepy>=2.2.1" \
    "loguru>=0.7.0" \
    "flask>=3.0.0" \
    "pdfplumber>=0.10.0" \
    "pdf2image>=1.16.0" \
    "httpx>=0.25.0" \
    "psutil>=5.9.0"

# 7. 复制项目代码
COPY vidppt/ vidppt/
COPY web/ web/

# 8. 创建上传/输出目录
RUN mkdir -p /app/web/uploads /app/web/outputs

# 9. 暴露端口
EXPOSE 5000

# 10. 启动 Web 服务
CMD ["python3", "web/app.py", "5000"]
