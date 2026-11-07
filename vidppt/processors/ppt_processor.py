"""
PowerPoint 文档处理器
"""

import io
from dataclasses import replace
import hashlib
import json
import shutil
import subprocess
import tempfile
from importlib.metadata import version
from pathlib import Path

from loguru import logger
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE
from PIL import Image

from ..core.interfaces import DocumentProcessor
from ..core.models import DocumentContent, PageContent, ProcessConfig
from ..core.registry import register_processor
from .original_slides import reference_path, render_original_slides
from ..utils.document_cache import DocumentCache, file_digest
from ..utils.render_capacity import serialized_render


@register_processor
class PPTProcessor(DocumentProcessor):
    """PowerPoint 文档处理器"""

    @classmethod
    def supported_extensions(cls) -> list[str]:
        return [".ppt", ".pptx"]

    def extract_content(self, config: ProcessConfig) -> DocumentContent:
        if not config.input_path.is_file():
            return self._extract_content(config)
        cache = DocumentCache('ppt-content', {
            'version': 1, 'source': file_digest(config.input_path),
            'parser': version('python-pptx'), 'images': config.save_intermediate,
        })
        cached = cache.load()
        if cached is not None:
            payload, assets = cached
            try:
                pages = []
                for number, item in enumerate(payload['pages'], 1):
                    page = PageContent(page_number=number, text=item['text'])
                    page_dir = config.output_dir / str(number)
                    for asset in item['images']:
                        target = page_dir / Path(asset['name']).name
                        target.parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(assets[asset['index']], target)
                        page.images.append(target)
                    if config.save_intermediate and page.text.strip():
                        page_dir.mkdir(parents=True, exist_ok=True)
                        (page_dir / 'text.txt').write_text(page.text, encoding='utf-8')
                    pages.append(page)
                logger.info(f'复用文件解析缓存，共 {len(pages)} 页')
                return DocumentContent(pages=pages)
            except (OSError, KeyError, IndexError, TypeError, ValueError):
                pass
        # A changed source must not inherit stale text.txt from this output directory.
        content = self._extract_content(replace(config, skip_existing=False))
        assets, pages = [], []
        for page in content.pages:
            images = []
            for image in page.images:
                images.append({'index': len(assets), 'name': image.name})
                assets.append(image)
            pages.append({'text': page.text, 'images': images})
        cache.store({'pages': pages}, assets)
        return content

    def _extract_content(self, config: ProcessConfig) -> DocumentContent:
        """提取 PPT 内容"""
        prs = Presentation(str(config.input_path))
        pages = []

        logger.info(f"共 {len(prs.slides)} 页，开始提取...")

        text_skipped = 0
        for i, slide in enumerate(prs.slides, start=1):
            page = PageContent(page_number=i)
            page_dir = config.output_dir / str(i)
            text_path = page_dir / "text.txt"

            # 跳过已有文本的页面
            if config.save_intermediate and config.skip_existing and text_path.exists():
                page.text = text_path.read_text(encoding="utf-8")
                logger.debug(f"第 {i} 页 文字已存在，跳过提取  ({len(page.text)} 字符)")
                text_skipped += 1
            else:
                # 提取文本
                page.text = self._extract_text_from_slide(slide)

                # 保存文本（如果需要且不为空）
                if config.save_intermediate and page.text and page.text.strip():
                    page_dir.mkdir(parents=True, exist_ok=True)
                    text_path.write_text(page.text, encoding="utf-8")
                    logger.debug(f"第 {i} 页 文字 -> {text_path}  ({len(page.text)} 字符)")
                elif config.save_intermediate:
                    logger.debug(f"第 {i} 页 无文本内容，跳过文本文件保存")

                # 提取图片
                if config.save_intermediate:
                    page_dir.mkdir(parents=True, exist_ok=True)
                    page.images = self._extract_images_from_slide(slide, page_dir)
                    for img_path in page.images:
                        logger.debug(f"第 {i} 页 图片 -> {img_path}")
                    if not page.images:
                        logger.debug(f"第 {i} 页 无内嵌图片")

            pages.append(page)

        if text_skipped:
            logger.info(f"跳过 {text_skipped} 页已有文字提取")

        return DocumentContent(pages=pages)

    @serialized_render
    def render_pages(self, config: ProcessConfig) -> list[Path]:
        """优先使用已确认的原生页面；成功渲染后才提交缓存签名。"""
        engine = 'original' if reference_path(config.input_path).is_file() else config.render_engine
        renderers = {
            'original': lambda c: render_original_slides(c.input_path, c.output_dir),
            'libreoffice': self._render_with_libreoffice,
            'spire': self._render_with_spire,
        }
        if engine not in renderers:
            raise ValueError(f'不支持的 PPT 渲染引擎：{engine}')
        # 输入不可读时由具体引擎报告错误，不尝试读取缓存。
        if not config.input_path.is_file():
            return renderers[engine](config)
        signature = self._render_signature(config, engine)
        marker = config.output_dir / '.render_signature'
        page_count = self._get_slide_count(config)
        paths = [config.output_dir / str(i) / 'slide.png' for i in range(1, page_count + 1)]
        if (config.save_intermediate and config.skip_existing and marker.is_file()
                and marker.read_text() == signature
                and all(p.is_file() and p.stat().st_size for p in paths)):
            return paths
        cache = DocumentCache('ppt-render', signature)
        if config.save_intermediate and config.skip_existing:
            cached = cache.load()
            if cached is not None:
                payload, assets = cached
                if payload == {'page_count': page_count} and len(assets) == page_count:
                    try:
                        marker.unlink(missing_ok=True)
                        self._clear_slides(config)
                        for source, target in zip(assets, paths):
                            target.parent.mkdir(parents=True, exist_ok=True)
                            shutil.copyfile(source, target)
                        marker.write_text(signature)
                        (config.output_dir / '.render_engine').write_text(engine)
                        logger.info(f'复用原始页面截图缓存，共 {page_count} 页')
                        return paths
                    except OSError:
                        pass
        # 旧缓存没有完整签名时也失效，失败后不能误用部分新截图。
        marker.unlink(missing_ok=True)
        self._clear_slides(config)
        paths = renderers[engine](config)
        if len(paths) != page_count or not all(p.is_file() for p in paths):
            raise ValueError(f'PPT 渲染页数不一致：预期 {page_count} 页，实际 {len(paths)} 页')
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(signature)
        (config.output_dir / '.render_engine').write_text(engine)
        if config.save_intermediate and config.skip_existing:
            cache.store({'page_count': page_count}, paths)
        return paths

    @staticmethod
    def _render_signature(config: ProcessConfig, engine: str) -> str:
        def digest(path):
            with path.open('rb') as stream:
                return hashlib.file_digest(stream, 'sha256').hexdigest()

        values = {'version': 2, 'engine': engine, 'source': digest(config.input_path)}
        if engine == 'original':
            archive = reference_path(config.input_path)
            values['reference'] = digest(archive) if archive.is_file() else 'missing'
        else:
            values['python_pptx'] = version('python-pptx')
            if engine == 'spire':
                values['spire'] = version('spire.presentation')
            else:
                executable = shutil.which('libreoffice') or shutil.which('soffice')
                if executable and Path(executable).is_file():
                    binary = Path(executable)
                    values['binary'] = (str(binary.resolve()), binary.stat().st_size, binary.stat().st_mtime_ns)
            # 字体安装、替换和 fontconfig 调整之后必须重新渲染。
            fc_list = shutil.which('fc-list')
            if fc_list:
                listing = subprocess.check_output(
                    [fc_list, '--format', '%{file}\n'], timeout=15,
                ).decode('utf-8').splitlines()
                values['fonts'] = sorted(
                    (str(p), p.stat().st_size, p.stat().st_mtime_ns)
                    for p in {Path(name) for name in listing} if p.is_file()
                )
            values['fontconfig'] = [
                (str(p), digest(p)) for root in [Path('/etc/fonts'), Path.home() / '.config/fontconfig']
                if root.is_dir() for p in sorted(root.rglob('*.conf')) if p.is_file()
            ]
        return json.dumps(values, sort_keys=True)

    def _existing_slide_count(self, config: ProcessConfig) -> int:
        """统计已存在的 slide.png 数量"""
        count = 0
        while True:
            if not (config.output_dir / str(count + 1) / "slide.png").exists():
                break
            count += 1
        return count

    def _clear_slides(self, config: ProcessConfig) -> None:
        """清除旧的幻灯片截图"""
        for page_dir in config.output_dir.glob('*'):
            if not page_dir.is_dir() or not page_dir.name.isdigit():
                continue
            slide_path = page_dir / "slide.png"
            if slide_path.exists():
                slide_path.unlink()
            # 如果目录为空则删除
            try:
                page_dir.rmdir()
            except OSError:
                pass

    def _render_with_spire(self, config: ProcessConfig) -> list[Path]:
        """使用 Spire 渲染 PPT 页面为图像"""
        from spire.presentation import Presentation as SpirePresentation

        logger.info("开始渲染幻灯片截图（spire）...")

        # 如果当前引擎与上次渲染不同，清除旧截图
        marker = config.output_dir / ".render_engine"
        if marker.exists() and marker.read_text().strip() != "spire":
            logger.info("检测到上次使用其他引擎渲染，清除旧截图")
            self._clear_slides(config)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("spire")

        # 预检查哪些页需要渲染
        if config.save_intermediate and config.skip_existing:
            page_count = self._get_slide_count(config)
            skip_flags = []
            for i in range(1, page_count + 1):
                slide_path = config.output_dir / str(i) / "slide.png"
                skip_flags.append(slide_path.exists())

            if all(skip_flags):
                logger.info("所有幻灯片截图已存在，跳过渲染")
                return [config.output_dir / str(i) / "slide.png" for i in range(1, page_count + 1)]
        else:
            skip_flags = []

        # 需要渲染至少一页，加载 spire
        prs = SpirePresentation()
        prs.LoadFromFile(str(config.input_path))

        # 确保输出目录存在
        config.output_dir.mkdir(parents=True, exist_ok=True)

        # 如果没有预检查结果（skip_existing 未启用），重新计算
        if len(skip_flags) != prs.Slides.Count:
            skip_flags = [False] * prs.Slides.Count
            if config.save_intermediate and config.skip_existing:
                for i in range(prs.Slides.Count):
                    slide_path = config.output_dir / str(i + 1) / "slide.png"
                    skip_flags[i] = slide_path.exists()

        slide_images = []
        rendered = 0
        for i in range(prs.Slides.Count):
            page_num = i + 1

            if skip_flags[i]:
                out_path = config.output_dir / str(page_num) / "slide.png"
                slide_images.append(out_path)
                logger.debug(f"第 {page_num} 页 截图已存在，跳过渲染")
                continue

            slide = prs.Slides[i]
            img_stream = slide.SaveAsImage()
            img_bytes = bytes(img_stream.ToArray())
            img = Image.open(io.BytesIO(img_bytes))

            if config.save_intermediate:
                page_dir = config.output_dir / str(page_num)
                page_dir.mkdir(parents=True, exist_ok=True)
                out_path = page_dir / "slide.png"
                img.save(out_path, "PNG")
                logger.debug(f"第 {page_num} 页 截图 -> {out_path}")
                slide_images.append(out_path)
                rendered += 1
            else:
                # 不保存中间文件时，保存到临时路径
                config.output_dir.mkdir(parents=True, exist_ok=True)
                temp_path = config.output_dir / f"_temp_slide_{page_num}.png"
                img.save(temp_path, "PNG")
                slide_images.append(temp_path)
                rendered += 1

            img_stream.Dispose()

        prs.Dispose()

        skipped = sum(skip_flags)
        if skipped:
            logger.info(f"跳过 {skipped} 页已有截图，渲染 {rendered} 页")
        else:
            logger.info(f"渲染 {rendered} 页截图")

        return slide_images

    def _render_with_libreoffice(self, config: ProcessConfig) -> list[Path]:
        """使用 LibreOffice 渲染 PPT 页面为图像

        两步流程：LibreOffice 转 PDF → pdftoppm 逐页转 PNG
        """
        logger.info("开始渲染幻灯片截图（libreoffice）...")

        # 如果当前引擎与上次渲染不同，清除旧截图
        marker = config.output_dir / ".render_engine"
        if marker.exists() and marker.read_text().strip() != "libreoffice":
            logger.info("检测到上次使用其他引擎渲染，清除旧截图")
            self._clear_slides(config)
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text("libreoffice")

        # 预检查 skip_existing
        if config.save_intermediate and config.skip_existing:
            page_count = self._get_slide_count(config)
            skip_flags = []
            for i in range(1, page_count + 1):
                slide_path = config.output_dir / str(i) / "slide.png"
                skip_flags.append(slide_path.exists())

            if all(skip_flags):
                logger.info("所有幻灯片截图已存在，跳过渲染")
                return [config.output_dir / str(i) / "slide.png" for i in range(1, page_count + 1)]

            need_render = not all(skip_flags)
        else:
            need_render = True

        if need_render:
            libreoffice = shutil.which("libreoffice") or shutil.which("soffice")
            if not libreoffice:
                raise FileNotFoundError("未找到 LibreOffice，请安装并将 libreoffice 或 soffice 加入 PATH")
            with tempfile.TemporaryDirectory() as tmp_dir:
                # 先将输入文件复制到临时目录（安全文件名），避免 LO 无法加载
                # 含特殊字符（引号等）的原始文件名或某些 PPTX 格式会导致 LO 加载失败
                safe_input = Path(tmp_dir) / f"input{config.input_path.suffix.lower()}"
                shutil.copy2(config.input_path, safe_input)

                # Step 1: LibreOffice PPT → PDF
                cmd_pdf = []
                if shutil.which("xvfb-run"):
                    cmd_pdf.append("xvfb-run")
                cmd_pdf.extend([
                    libreoffice,
                    f"-env:UserInstallation={(Path(tmp_dir) / 'profile').as_uri()}",
                    "--headless",
                    "--convert-to",
                    "pdf",
                    "--outdir",
                    tmp_dir,
                    str(safe_input),
                ])
                try:
                    subprocess.run(cmd_pdf, check=True, capture_output=True)
                    pdf_path = Path(tmp_dir) / "input.pdf"
                    if not pdf_path.exists():
                        raise subprocess.CalledProcessError(1, cmd_pdf)
                except subprocess.CalledProcessError as exc:
                    raise RuntimeError(
                        'LibreOffice 无法转换原 PPT；为避免损失图表等内容，不自动重新保存原稿。'
                        '请使用 PowerPoint 导出的 PNG 页面 ZIP。'
                    ) from exc

                pdf_path = Path(tmp_dir) / "input.pdf"
                if not pdf_path.exists():
                    raise FileNotFoundError(
                        f"LibreOffice 未生成 PDF: {pdf_path}"
                    )

                # Step 2: pdftoppm PDF → PNG（逐页）
                cmd_ppm = [
                    "pdftoppm",
                    "-png",
                    "-r",
                    "150",
                    str(pdf_path),
                    str(Path(tmp_dir) / "slide"),
                ]
                subprocess.run(cmd_ppm, check=True, capture_output=True)

                # pdftoppm 输出命名：slide-01.png, slide-02.png, ...（零填充）
                config.output_dir.mkdir(parents=True, exist_ok=True)
                slide_images = []
                page_num = 1
                while True:
                    # pdftoppm 用零填充页码，如 slide-01.png, slide-001.png
                    # 两种格式都检查
                    ppm_output = Path(tmp_dir) / f"slide-{page_num:02d}.png"
                    if not ppm_output.exists():
                        # 也尝试三位零填充
                        ppm_output = Path(tmp_dir) / f"slide-{page_num:03d}.png"
                    if not ppm_output.exists():
                        # 最后尝试无零填充
                        ppm_output = Path(tmp_dir) / f"slide-{page_num}.png"
                    if not ppm_output.exists():
                        break
                    page_dir = config.output_dir / str(page_num)
                    page_dir.mkdir(parents=True, exist_ok=True)
                    dest = page_dir / "slide.png"
                    shutil.copy2(ppm_output, dest)
                    slide_images.append(dest)
                    logger.debug(f"第 {page_num} 页 截图 -> {dest}")
                    page_num += 1
        else:
            # 部分存在，只需收集已存在的
            page_count = self._get_slide_count(config)
            slide_images = []
            for i in range(1, page_count + 1):
                slide_path = config.output_dir / str(i) / "slide.png"
                slide_images.append(slide_path)

        logger.info(f"渲染 {len(slide_images)} 页截图（libreoffice）")
        return slide_images

    def _get_slide_count(self, config: ProcessConfig) -> int:
        """获取 PPT 幻灯片数量（不加载 spire）"""
        prs = Presentation(str(config.input_path))
        count = len(prs.slides)
        return count

    @staticmethod
    def _extract_text_from_slide(slide) -> str:
        """提取幻灯片正文和演讲者备注，供后续 LLM 与 TTS 使用。"""
        lines = []
        for shape in slide.shapes:
            if not shape.has_text_frame:
                continue
            for para in shape.text_frame.paragraphs:
                text = para.text.strip()
                if not text:
                    continue
                level = para.level if para.level else 0
                indent = "  " * level
                lines.append(f"{indent}{text}")

        slide_text = "\n".join(lines)
        notes_text = PPTProcessor._extract_notes_from_slide(slide)
        if not notes_text:
            return slide_text

        parts = []
        if slide_text:
            parts.append(f"[幻灯片正文]\n{slide_text}")
        parts.append(f"[演讲者备注]\n{notes_text}")
        return "\n\n".join(parts)

    @staticmethod
    def _extract_notes_from_slide(slide) -> str:
        """提取演讲者备注；无备注或备注结构不可用时返回空字符串。"""
        if getattr(slide, "has_notes_slide", False) is not True:
            return ""
        try:
            text = slide.notes_slide.notes_text_frame.text
        except (AttributeError, ValueError):
            return ""
        return text.strip() if isinstance(text, str) else ""

    @staticmethod
    def _extract_images_from_slide(slide, out_dir: Path) -> list[Path]:
        """提取幻灯片中所有内嵌图片，返回保存路径列表"""
        saved = []
        img_index = 1

        def extract_from_shape(shape):
            nonlocal img_index
            try:
                shape_type = shape.shape_type
            except NotImplementedError:
                return
            if shape_type == MSO_SHAPE_TYPE.PICTURE:
                image = shape.image
                ext = image.ext
                img_path = out_dir / f"image_{img_index}.{ext}"
                # 如果目录不存在，先创建
                img_path.parent.mkdir(parents=True, exist_ok=True)
                img_path.write_bytes(image.blob)
                saved.append(img_path)
                img_index += 1
            elif shape_type == MSO_SHAPE_TYPE.GROUP:
                for child in shape.shapes:
                    extract_from_shape(child)

        for shape in slide.shapes:
            extract_from_shape(shape)

        return saved
