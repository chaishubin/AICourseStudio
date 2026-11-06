"""将 Word/PDF/EPUB 教案读取为保留标题层级的 SourceDocument。"""

from __future__ import annotations

from dataclasses import asdict
from importlib.metadata import version, PackageNotFoundError
from pathlib import Path
from html.parser import HTMLParser
import posixpath
import xml.etree.ElementTree as ET
from zipfile import BadZipFile, ZipFile

from loguru import logger

from .models import SourceDocument, SourceSection
from ..utils.document_cache import DocumentCache, file_digest


def read_source_document(path: Path) -> SourceDocument:
    path = Path(path)
    suffix = path.suffix.lower()
    readers = {".docx": (_read_docx, "python-docx"),
               ".pdf": (_read_pdf, "pdfplumber"), ".epub": (_read_epub, None)}
    if suffix not in readers:
        raise ValueError(f"教案输入仅支持 .docx、.pdf 和 .epub，收到: {suffix or '无扩展名'}")
    reader, dependency = readers[suffix]
    try:
        parser_version = version(dependency) if dependency else 'stdlib'
    except PackageNotFoundError:
        return reader(path)  # Keep the reader's actionable dependency error.
    cache = DocumentCache('source', {
        'version': 1, 'source': file_digest(path), 'format': suffix,
        'parser': parser_version,
    })
    cached = cache.load()
    if cached is not None:
        payload, _ = cached
        try:
            document = SourceDocument(
                title=path.stem if payload['filename_title'] else payload['title'],
                source_path=path,
                sections=[SourceSection(**section) for section in payload['sections']],
                metadata=payload['metadata'],
                title_from_filename=payload['filename_title'],
            )
            logger.info('复用教案文件解析缓存')
            return document
        except (KeyError, TypeError, ValueError):
            pass
    document = reader(path)
    cache.store({
        'title': document.title,
        'filename_title': document.title_from_filename,
        'sections': [asdict(section) for section in document.sections],
        'metadata': document.metadata,
    })
    return document


def _read_docx(path: Path) -> SourceDocument:
    try:
        from docx import Document
    except ImportError as exc:
        raise ImportError("读取 Word 需要 python-docx，请安装项目的 lesson-plan 依赖") from exc

    document = Document(str(path))
    title = path.stem
    filename_title = True
    sections: list[SourceSection] = []
    current = SourceSection(title="课程导入", level=1)

    for paragraph in document.paragraphs:
        text = paragraph.text.strip()
        if not text:
            continue
        style_name = (paragraph.style.name or "").lower()
        if style_name == "title":
            title = text
            filename_title = False
            continue
        level = _heading_level(style_name)
        if level is not None:
            if current.paragraphs or current.title != "课程导入":
                sections.append(current)
            current = SourceSection(title=text, level=level)
        else:
            current.paragraphs.append(text)

    if current.paragraphs or not sections:
        sections.append(current)

    return SourceDocument(
        title=title,
        source_path=path,
        sections=sections,
        metadata={"format": "docx"},
        title_from_filename=filename_title,
    )


def _heading_level(style_name: str) -> int | None:
    for prefix in ("heading ", "标题 "):
        if style_name.startswith(prefix):
            try:
                return max(1, int(style_name[len(prefix):]))
            except ValueError:
                return 1
    return None


def _read_pdf(path: Path) -> SourceDocument:
    try:
        import pdfplumber
    except ImportError as exc:
        raise ImportError("读取 PDF 需要 pdfplumber，请安装项目的 lesson-plan 依赖") from exc

    sections = []
    with pdfplumber.open(path) as pdf:
        for page_number, page in enumerate(pdf.pages, 1):
            text = (page.extract_text() or "").strip()
            if text:
                lines = [line.strip() for line in text.splitlines() if line.strip()]
                sections.append(
                    SourceSection(
                        title=f"第 {page_number} 页",
                        level=1,
                        paragraphs=lines,
                    )
                )

    if not sections:
        raise ValueError("PDF 未提取到文本；扫描版 PDF 需要先配置 OCR")

    return SourceDocument(
        title=path.stem,
        source_path=path,
        sections=sections,
        metadata={"format": "pdf", "page_count": len(sections)},
        title_from_filename=True,
    )


class _EPUBHTMLParser(HTMLParser):
    """提取 EPUB 内容文档中的标题与段落，忽略样式和脚本。"""

    _block_tags = {"p", "li", "blockquote", "pre", "div", "section", "article"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: list[tuple[str, int, str]] = []
        self._capture: tuple[str, int] | None = None
        self._parts: list[str] = []
        self._ignored_depth = 0

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "svg"}:
            self._ignored_depth += 1
            return
        if self._ignored_depth or self._capture is not None:
            return
        if len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
            self._capture = ("heading", int(tag[1]))
            self._parts = []
        elif tag in self._block_tags:
            self._capture = ("paragraph", 0)
            self._parts = []

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style", "svg"} and self._ignored_depth:
            self._ignored_depth -= 1
            return
        if self._ignored_depth or self._capture is None:
            return
        kind, level = self._capture
        expected = f"h{level}" if kind == "heading" else tag
        if kind == "heading" and tag != expected:
            return
        if kind == "paragraph" and tag not in self._block_tags:
            return
        text = " ".join("".join(self._parts).split())
        if text:
            self.items.append((kind, level, text))
        self._capture = None
        self._parts = []

    def handle_data(self, data: str) -> None:
        if self._capture is not None and not self._ignored_depth:
            self._parts.append(data)


def _read_epub(path: Path) -> SourceDocument:
    try:
        with ZipFile(path) as archive:
            container = ET.fromstring(archive.read("META-INF/container.xml"))
            rootfile = next(
                element for element in container.iter() if element.tag.endswith("rootfile")
            ).attrib["full-path"]
            package = ET.fromstring(archive.read(rootfile))
            title = next(
                (
                    (element.text or "").strip()
                    for element in package.iter()
                    if element.tag.endswith("title") and (element.text or "").strip()
                ),
                None,
            )
            manifest = {
                element.attrib.get("id"): element.attrib.get("href")
                for element in package.iter()
                if element.tag.endswith("item")
            }
            spine = [
                element.attrib.get("idref")
                for element in package.iter()
                if element.tag.endswith("itemref")
            ]
            base_dir = posixpath.dirname(rootfile)
            documents = [manifest.get(item_id) for item_id in spine]
            sections: list[SourceSection] = []
            current: SourceSection | None = None

            for href in documents:
                if not href:
                    continue
                member = posixpath.normpath(posixpath.join(base_dir, href.split("#", 1)[0]))
                parser = _EPUBHTMLParser()
                parser.feed(archive.read(member).decode("utf-8", errors="replace"))
                for kind, level, text in parser.items:
                    if kind == "heading":
                        if current and current.paragraphs:
                            sections.append(current)
                        current = SourceSection(title=text, level=level)
                    else:
                        if current is None:
                            current = SourceSection(title=f"章节 {len(sections) + 1}", level=1)
                        current.paragraphs.append(text)
                if current and current.paragraphs:
                    sections.append(current)
                    current = None
    except (BadZipFile, KeyError, StopIteration, ET.ParseError) as exc:
        raise ValueError("EPUB 文件结构无效或内容已损坏") from exc

    if not sections:
        raise ValueError("EPUB 未提取到可用正文")

    return SourceDocument(
        title=title or path.stem,
        source_path=path,
        sections=sections,
        metadata={"format": "epub", "section_count": len(sections)},
        title_from_filename=title is None,
    )
