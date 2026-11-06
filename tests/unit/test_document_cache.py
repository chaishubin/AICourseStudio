"""Cross-task source reuse must never reuse generated scripts or stale artifacts."""

import io
import json
import os
import shutil
from unittest.mock import Mock
from zipfile import ZipFile

import pytest
from docx import Document
from PIL import Image
from pptx import Presentation

from vidppt.core.models import ProcessConfig
from vidppt.course_pipeline import CoursePipeline
from vidppt.ingestion import reader
from vidppt.processors import ppt_processor
from vidppt.processors.original_slides import reference_path
from vidppt.processors.ppt_processor import PPTProcessor


def make_docx(path, title=None):
    document = Document()
    if title:
        document.add_paragraph(title, style='Title')
    document.add_heading('第一章', level=1)
    document.add_paragraph('课程原文。')
    document.save(path)
    return path


def make_pptx(path):
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    slide.shapes.add_textbox(0, 0, 1000000, 1000000).text = 'source'
    image = io.BytesIO()
    Image.new('RGB', (40, 30), 'red').save(image, 'PNG')
    slide.shapes.add_picture(io.BytesIO(image.getvalue()), 0, 0)
    presentation.save(path)
    with ZipFile(reference_path(path), 'w') as archive:
        archive.writestr('1.png', image.getvalue())
    return path


@pytest.mark.parametrize('internal_title', [None, 'first'])
def test_source_parsing_reused_across_paths_with_fresh_objects(tmp_path, monkeypatch, internal_title):
    first = make_docx(tmp_path / 'first.docx', internal_title)
    second = tmp_path / 'second.docx'
    shutil.copyfile(first, second)
    parse = Mock(wraps=reader._read_docx)
    monkeypatch.setattr(reader, '_read_docx', parse)
    original = reader.read_source_document(first)
    original.sections[0].paragraphs.append('edited')
    cached = reader.read_source_document(second)
    assert parse.call_count == 1
    assert cached.source_path == second
    assert cached.title == (internal_title or 'second')
    assert cached.sections[0].paragraphs == ['课程原文。']


def test_source_changes_invalidate_even_with_same_size_and_timestamp(tmp_path, monkeypatch):
    source = tmp_path / 'source.epub'
    source.write_bytes(b'first')
    from vidppt.ingestion.models import SourceDocument, SourceSection
    parse = Mock(side_effect=lambda path: SourceDocument(
        title='source', source_path=path,
        sections=[SourceSection(title=path.read_text())]))
    monkeypatch.setattr(reader, '_read_epub', parse)
    reader.read_source_document(source)
    stat = source.stat()
    source.write_bytes(b'other')
    os.utime(source, ns=(stat.st_atime_ns, stat.st_mtime_ns))
    assert reader.read_source_document(source).sections[0].title == 'other'
    assert parse.call_count == 2


def test_ppt_parsing_reuses_images_and_original_text_after_task_deleted(tmp_path, monkeypatch):
    source = make_pptx(tmp_path / 'first.pptx')
    processor = PPTProcessor()
    extract = Mock(wraps=processor._extract_content)
    monkeypatch.setattr(processor, '_extract_content', extract)
    first = processor.extract_content(ProcessConfig(source, tmp_path / 'task1'))
    image = first.pages[0].images[0].read_bytes()
    first.pages[0].text = 'generated script'
    shutil.rmtree(tmp_path / 'task1')
    second_source = tmp_path / 'second.pptx'
    shutil.copyfile(source, second_source)
    second = processor.extract_content(ProcessConfig(second_source, tmp_path / 'task2'))
    assert extract.call_count == 1
    assert second.pages[0].text == 'source'
    assert second.pages[0].images[0].read_bytes() == image
    assert second.pages[0].images[0].is_relative_to(tmp_path / 'task2')
    assert (tmp_path / 'task2/1/text.txt').read_text() == 'source'
    # A changed input must also ignore stale per-task text files.
    presentation = Presentation(second_source)
    presentation.slides[0].shapes[0].text = 'changed'
    presentation.save(second_source)
    changed = processor.extract_content(ProcessConfig(second_source, tmp_path / 'task2'))
    assert changed.pages[0].text == 'changed'
    assert extract.call_count == 2


def test_original_render_reused_and_corruption_rebuilt(tmp_path, monkeypatch):
    source = make_pptx(tmp_path / 'first.pptx')
    render = Mock(wraps=ppt_processor.render_original_slides)
    monkeypatch.setattr(ppt_processor, 'render_original_slides', render)
    processor = PPTProcessor()
    paths = processor.render_pages(ProcessConfig(source, tmp_path / 'task1'))
    original = paths[0].read_bytes()
    shutil.rmtree(tmp_path / 'task1')
    copy = tmp_path / 'renamed.pptx'
    shutil.copyfile(source, copy)
    shutil.copyfile(reference_path(source), reference_path(copy))
    second = processor.render_pages(ProcessConfig(copy, tmp_path / 'task2'))
    assert render.call_count == 1
    assert second[0].read_bytes() == original
    cache_root = tmp_path / 'document-cache/ppt-render'
    asset = next(cache_root.glob('*/0'))
    asset.write_bytes(b'broken')
    processor.render_pages(ProcessConfig(copy, tmp_path / 'task3'))
    assert render.call_count == 2
    assert asset.read_bytes() == original
    processor.render_pages(ProcessConfig(copy, tmp_path / 'task4'))
    assert render.call_count == 2


def test_render_environment_change_invalidates_shared_cache(tmp_path, monkeypatch):
    source = make_pptx(tmp_path / 'source.pptx')
    processor = PPTProcessor()
    render = Mock(wraps=ppt_processor.render_original_slides)
    monkeypatch.setattr(ppt_processor, 'render_original_slides', render)
    signature = processor._render_signature
    monkeypatch.setattr(processor, '_render_signature', lambda c, e: signature(c, e) + 'v1')
    processor.render_pages(ProcessConfig(source, tmp_path / 'task1'))
    monkeypatch.setattr(processor, '_render_signature', lambda c, e: signature(c, e) + 'v2')
    processor.render_pages(ProcessConfig(source, tmp_path / 'task2'))
    assert render.call_count == 2


def test_cached_parsing_still_generates_new_scripts_each_time(tmp_path, monkeypatch):
    source = make_docx(tmp_path / 'source.docx')
    parse = Mock(wraps=reader._read_docx)
    monkeypatch.setattr(reader, '_read_docx', parse)
    llm = Mock()
    llm.summarize.side_effect = [json.dumps({'slides': [
        {'title': '课程', 'script': script}]} , ensure_ascii=False)
        for script in ['第一版讲稿', '第二版讲稿']]
    pipeline = CoursePipeline(llm)
    pipeline.pptx_renderer.render = Mock(return_value=tmp_path / 'generated.pptx')
    first = pipeline.run(source, tmp_path / 'task1')
    second = pipeline.run(source, tmp_path / 'task2')
    assert parse.call_count == 1
    assert llm.summarize.call_count == 2
    assert first.course.sections[0].script == '第一版讲稿'
    assert second.course.sections[0].script == '第二版讲稿'


def test_unwritable_cache_does_not_fail_parsing(tmp_path, monkeypatch):
    source = make_docx(tmp_path / 'source.docx')
    blocked = tmp_path / 'not-a-directory'
    blocked.write_text('file')
    monkeypatch.setenv('VIDPPT_DOCUMENT_CACHE_DIR', str(blocked))
    assert reader.read_source_document(source).sections[0].paragraphs == ['课程原文。']


def test_corrupt_parse_manifest_is_rebuilt(tmp_path, monkeypatch):
    source = make_docx(tmp_path / 'source.docx')
    parse = Mock(wraps=reader._read_docx)
    monkeypatch.setattr(reader, '_read_docx', parse)
    reader.read_source_document(source)
    manifest = next((tmp_path / 'document-cache/source').glob('*/manifest.json'))
    manifest.write_text('{broken')
    assert reader.read_source_document(source).sections[0].paragraphs == ['课程原文。']
    reader.read_source_document(source)
    assert parse.call_count == 2


def test_incomplete_render_is_not_shared(tmp_path, monkeypatch):
    source = make_pptx(tmp_path / 'source.pptx')
    processor = PPTProcessor()
    render = Mock(side_effect=[[], ppt_processor.render_original_slides(
        source, tmp_path / 'valid')])
    monkeypatch.setattr(ppt_processor, 'render_original_slides', render)
    with pytest.raises(ValueError, match='页数不一致'):
        processor.render_pages(ProcessConfig(source, tmp_path / 'failed'))
    assert not list((tmp_path / 'document-cache').glob('ppt-render/*/manifest.json'))
    processor.render_pages(ProcessConfig(source, tmp_path / 'retry'))
    assert render.call_count == 2
