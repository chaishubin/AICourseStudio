"""原生页面必须完整、保持原 PNG 字节，缓存不能掩盖原稿变更。"""

import io
from zipfile import ZipFile

import pytest
from PIL import Image
from pptx import Presentation

from vidppt.core.models import ProcessConfig
from vidppt.processors.original_slides import read_original_slides, reference_path
from vidppt.processors.ppt_processor import PPTProcessor


def make_source(tmp_path):
    source = tmp_path / 'course.pptx'
    prs = Presentation()
    for _ in range(2):
        prs.slides.add_slide(prs.slide_layouts[6])
    prs.save(source)
    return source


def png(color='white', size=(400, 300)):
    stream = io.BytesIO()
    Image.new('RGB', size, color).save(stream, 'PNG')
    return stream.getvalue()


def bundle(source, entries):
    with ZipFile(reference_path(source), 'w') as archive:
        for name, data in entries:
            archive.writestr(name, data)


def test_original_pages_bypass_layout_and_preserve_png_bytes(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    first, second = png('red'), png('blue')
    bundle(source, [('export/幻灯片2.png', second), ('export/Slide1.png', first)])
    processor = PPTProcessor()
    monkeypatch.setattr(processor, '_render_with_spire', lambda _: pytest.fail('unexpected Spire'))
    monkeypatch.setattr(processor, '_render_with_libreoffice', lambda _: pytest.fail('unexpected LO'))
    config = ProcessConfig(source, tmp_path / 'out', render_engine='libreoffice')
    paths = processor.render_pages(config)
    assert [p.read_bytes() for p in paths] == [first, second]
    assert (config.output_dir / '.render_engine').read_text() == 'original'
    # 替换 ZIP 后不能复用旧页面。
    bundle(source, [('1.png', second), ('2.png', first)])
    assert [p.read_bytes() for p in processor.render_pages(config)] == [second, first]


@pytest.mark.parametrize('entries, message', [
    ([('1.png', png())], '全部 2 页'),
    ([('1.png', png()), ('Slide1.png', png())], '编号重复'),
    ([('1.png', png(size=(400, 225))), ('2.png', png())], '宽高比'),
    ([('1.png', b'broken'), ('2.png', png())], None),
    ([('1.png', png()), ('2.png', png()), ('script.py', b'bad')], '只能包含 PNG'),
])
def test_rejects_unusable_reference_before_rendering(tmp_path, entries, message):
    source = make_source(tmp_path)
    bundle(source, entries)
    with pytest.raises(Exception, match=message):
        read_original_slides(source, reference_path(source))
    assert not (tmp_path / 'out/1/slide.png').exists()


def test_original_engine_fails_without_reference(tmp_path):
    source = make_source(tmp_path)
    with pytest.raises(ValueError, match='不会降级'):
        PPTProcessor().render_pages(ProcessConfig(source, tmp_path / 'out', render_engine='original'))


def test_cache_source_change_and_failed_render_do_not_reuse_old_images(tmp_path, monkeypatch):
    source = make_source(tmp_path)
    processor = PPTProcessor()
    monkeypatch.setattr(processor, '_render_signature', lambda c, e: c.input_path.read_bytes().hex())
    config = ProcessConfig(source, tmp_path / 'out', render_engine='libreoffice')
    calls = []

    def render(c):
        calls.append(True)
        paths = []
        for i in [1, 2]:
            path = c.output_dir / str(i) / 'slide.png'
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(png())
            paths.append(path)
        return paths

    monkeypatch.setattr(processor, '_render_with_libreoffice', render)
    processor.render_pages(config)
    processor.render_pages(config)
    assert len(calls) == 1
    # 文件内容变化，哪怕页数相同，也必须重新渲染。
    prs = Presentation(source)
    prs.core_properties.title = 'changed'
    prs.save(source)
    processor.render_pages(config)
    assert len(calls) == 2
    # 页数不全属于失败，不提交签名。
    config.skip_existing = False
    monkeypatch.setattr(processor, '_render_with_libreoffice', lambda c: [])
    with pytest.raises(ValueError, match='页数不一致'):
        processor.render_pages(config)
    assert not (config.output_dir / '.render_signature').exists()


def test_web_upload_pairs_and_validates_reference(tmp_path, monkeypatch):
    import web.app as web_app

    source = make_source(tmp_path)
    bundle(source, [('1.png', png('red')), ('2.png', png('blue'))])
    uploads = tmp_path / 'uploads'
    uploads.mkdir()
    monkeypatch.setattr(web_app, 'UPLOAD_FOLDER', uploads)
    client = web_app.app.test_client()
    response = client.post('/api/upload', data={
        'file': (io.BytesIO(source.read_bytes()), '课程.pptx'),
        'original_slides': (io.BytesIO(reference_path(source).read_bytes()), 'pages.zip'),
    })
    assert response.status_code == 200
    result = response.get_json()
    assert result['original_slides'] is True
    from pathlib import Path
    assert read_original_slides(Path(result['file_path']), reference_path(Path(result['file_path']))) == [png('red'), png('blue')]
    count_before = len(list(uploads.iterdir()))
    response = client.post('/api/upload', data={
        'file': (io.BytesIO(source.read_bytes()), '课程.pptx'),
        'original_slides': (io.BytesIO(b'bad zip'), 'pages.zip'),
    })
    assert response.status_code == 400
    assert len(list(uploads.iterdir())) == count_before
