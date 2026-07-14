from zipfile import ZipFile

import pytest

from vidppt.ingestion.reader import read_source_document


def _write_epub(path):
    container = """<?xml version="1.0"?>
    <container xmlns="urn:oasis:names:tc:opendocument:xmlns:container">
      <rootfiles><rootfile full-path="OEBPS/content.opf"/></rootfiles>
    </container>"""
    package = """<?xml version="1.0" encoding="utf-8"?>
    <package xmlns="http://www.idpf.org/2007/opf" version="3.0">
      <metadata xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>测试电子书</dc:title></metadata>
      <manifest>
        <item id="chapter-1" href="chapter1.xhtml" media-type="application/xhtml+xml"/>
        <item id="chapter-2" href="chapter2.xhtml" media-type="application/xhtml+xml"/>
      </manifest>
      <spine><itemref idref="chapter-2"/><itemref idref="chapter-1"/></spine>
    </package>"""
    chapter_1 = """<html><body><h1>第一章</h1><p>第一章正文。</p></body></html>"""
    chapter_2 = """<html><body><h2>第二章</h2><p>第二章正文。</p><script>忽略脚本</script></body></html>"""
    with ZipFile(path, "w") as archive:
        archive.writestr("mimetype", "application/epub+zip")
        archive.writestr("META-INF/container.xml", container)
        archive.writestr("OEBPS/content.opf", package)
        archive.writestr("OEBPS/chapter1.xhtml", chapter_1)
        archive.writestr("OEBPS/chapter2.xhtml", chapter_2)


def test_read_epub_uses_spine_order_and_extracts_headings(temp_dir):
    source = temp_dir / "course.epub"
    _write_epub(source)

    document = read_source_document(source)

    assert document.title == "测试电子书"
    assert document.metadata == {"format": "epub", "section_count": 2}
    assert [section.title for section in document.sections] == ["第二章", "第一章"]
    assert document.sections[0].level == 2
    assert document.sections[0].paragraphs == ["第二章正文。"]
    assert "忽略脚本" not in document.full_text


def test_read_epub_rejects_invalid_archive(temp_dir):
    source = temp_dir / "broken.epub"
    source.write_bytes(b"not-an-epub")

    with pytest.raises(ValueError, match="结构无效"):
        read_source_document(source)
