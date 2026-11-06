"""Grounded page generation, native chart/formula extraction and vision payloads."""
import json
from unittest.mock import Mock, patch

import pytest
from PIL import Image
from pptx import Presentation
from pptx.chart.data import CategoryChartData
from pptx.enum.chart import XL_CHART_TYPE
from pptx.util import Inches
from pptx.oxml import parse_xml

from vidppt.core.models import PageContent
from vidppt.generation.page_analysis import analyze_page, validate_analysis, generate_presentation_narration
from vidppt.processors.slide_objects import presentation_objects
from vidppt.utils.focus_guidance import plan_page_focus
from vidppt.utils.focus_style import focus_appearance


def analysis_object(**overrides):
    return dict(target_id='', kind='formula', label='欧姆定律公式',
                description='电压等于电流乘电阻', evidence='U=IR',
                bbox=[.1, .2, .5, .1], readable=True, **overrides)


def make_page(tmp_path, number=1, text=''):
    image = tmp_path / f'slide{number}.png'
    Image.new('RGB', (1280, 720), 'white').save(image)
    return PageContent(page_number=number, text=text, slide_image=image)


def fake_engine(objects=None):
    engine = Mock(model='vision-test', api_url='https://example.invalid', options={})
    engine.analyze_slide.return_value = json.dumps({
        'summary': '欧姆定律', 'objects': objects if objects is not None else [analysis_object()],
        'uncertainties': ['页面没有注明适用温度条件'],
    }, ensure_ascii=False)
    engine.summarize.return_value = json.dumps({
        'script': '看这个欧姆定律公式，电压等于电流乘电阻。',
        'focus_cues': [{'text': '看这个欧姆定律公式，电压等于电流乘电阻。',
                        'anchor_id': 'p1-v1', 'action': 'switch'}],
    }, ensure_ascii=False)
    return engine


def test_native_chart_table_and_office_math_are_read_without_modifying_source(tmp_path):
    prs = Presentation()
    slide = prs.slides.add_slide(prs.slide_layouts[6])
    data = CategoryChartData()
    data.categories = ['第一期', '第二期']
    data.add_series('产量', [10, 20])
    slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1), Inches(4), Inches(2), data)
    table = slide.shapes.add_table(2, 2, Inches(1), Inches(3), Inches(4), Inches(1)).table
    table.cell(0, 0).text, table.cell(1, 0).text = '电流', '2 A'
    shape = slide.shapes.add_textbox(Inches(1), Inches(4), Inches(3), Inches(.5))
    shape.text_frame.paragraphs[0]._p.append(parse_xml(
        '<m:oMath xmlns:m="http://schemas.openxmlformats.org/officeDocument/2006/math"><m:r><m:t>U=IR</m:t></m:r></m:oMath>'))
    group = slide.shapes.add_group_shape()
    child = group.shapes.add_textbox(Inches(1), Inches(1), Inches(2), Inches(1))
    child.text = '分组文字'
    group.left, group.top, group.width, group.height = Inches(5), Inches(2), Inches(4), Inches(2)
    path = tmp_path / 'objects.pptx'
    prs.save(path)
    original = path.read_bytes()
    objects = presentation_objects(path)[0]
    assert path.read_bytes() == original
    chart = next(o for o in objects if o['kind'] == 'chart')
    assert chart['native_data']['series'] == [{'name': '产量', 'values': [10.0, 20.0]}]
    assert chart['native_data']['categories'] == ['第一期', '第二期']
    assert next(o for o in objects if o['kind'] == 'table')['native_data']['rows'][1][0] == '2 A'
    assert 'U=IR' in next(o for o in objects if o['kind'] == 'formula')['text']
    grouped = next(o for o in objects if o['text'] == '分组文字')
    assert grouped['x'] == pytest.approx(0.5)
    assert grouped['width'] == pytest.approx(0.4)
    assert len({o['id'] for o in objects}) == len(objects)


@pytest.mark.parametrize('bbox', [[0, 0, float('nan'), .2], [0, 0, -.2, .2], [.9, 0, .3, .2], [True, 0, .2, .2], ['bad', 0, .2, .2]])
def test_invalid_visual_geometry_is_never_focusable(bbox):
    item = analysis_object()
    item['bbox'] = bbox
    analysis, targets = validate_analysis({'summary': '公式', 'objects': [item]}, [], 1)
    assert not targets and not analysis['objects']


def test_native_geometry_and_data_are_authoritative():
    native = [{'id': 'p1-a1', 'text': '图表', 'kind': 'chart', 'x': .2, 'y': .3,
               'width': .4, 'height': .3, 'native_data': {'values': [10, 20]}}]
    item = analysis_object()
    item.update(target_id='p1-a1', bbox=[0, 0, 1, 1], label='产量变化')
    analysis, targets = validate_analysis({'summary': '产量', 'objects': [item]}, native, 1)
    assert targets[0]['x'] == .2 and targets[0]['native_data'] == {'values': [10, 20]}
    assert targets[0]['text'] == '产量变化'
    assert native[0]['text'] == '图表'
    item['target_id'] = 'invented'
    assert validate_analysis({'summary': '', 'objects': [item]}, [], 1)[1] == []


def test_unreadable_regions_and_unsupported_claims_stay_out_of_focus():
    item = analysis_object()
    item['readable'] = False
    result, targets = validate_analysis({'summary': '', 'objects': [item], 'uncertainties': ['公式模糊']}, [], 1)
    assert targets == []
    assert result['uncertainties'] == ['公式模糊']


def test_analysis_cache_reuses_only_matching_image_source_and_model(tmp_path):
    page = make_page(tmp_path)
    engine = fake_engine()
    analyze_page(engine, page, [], tmp_path)
    analyze_page(engine, page, [], tmp_path)
    assert engine.analyze_slide.call_count == 1
    page.text = '新增备注'
    analyze_page(engine, page, [], tmp_path)
    assert engine.analyze_slide.call_count == 2
    engine.model = 'changed-model'
    analyze_page(engine, page, [], tmp_path)
    assert engine.analyze_slide.call_count == 3
    saved = json.loads((tmp_path / '1/page_analysis.json').read_text())
    assert saved['analysis']['objects'][0]['evidence'] == 'U=IR'


def test_image_only_page_generates_narration_and_survives_focus_roundtrip(tmp_path):
    page = make_page(tmp_path)
    engine = fake_engine()
    targets = []
    generate_presentation_narration(engine, [page], targets, tmp_path)
    assert page.text and page.metadata['original_text'] == ''
    assert page.metadata['page_analysis']['objects'][0]['target_id'] == 'p1-v1'
    sent = json.loads(engine.summarize.call_args.args[0])
    assert sent['analysis']['uncertainties']
    cues, _ = plan_page_focus(page.text, targets[0], page.metadata['focus_cues'])
    assert cues[0]['target_id'] == 'p1-v1'
    again, _ = plan_page_focus(page.text, targets[0], json.loads(json.dumps(cues)))
    assert again[0]['target_id'] == 'p1-v1'


def test_whole_document_context_keeps_every_page_narration(tmp_path):
    pages = [make_page(tmp_path, 1), make_page(tmp_path, 2)]
    engine = fake_engine()
    generate_presentation_narration(engine, pages, [], tmp_path, mode='whole-document')
    assert all(page.text for page in pages)
    assert len(json.loads(engine.summarize.call_args.args[0])['course_context']) == 2
    assert pages[1].metadata['focus_cues'][0]['action'] == 'clear'  # page-1 ID cannot leak


def test_malformed_script_cannot_be_read_as_json_by_tts(tmp_path):
    engine = fake_engine()
    engine.summarize.return_value = '{"script": null, "focus_cues": []}'
    with pytest.raises(ValueError, match='口播稿'):
        generate_presentation_narration(engine, [make_page(tmp_path)], [], tmp_path)


@pytest.mark.parametrize('provider,env,expected', [('qwen', 'QWEN_VISION_MODEL', 'qwen3-vl-plus'), ('openai', 'OPENAI_VISION_MODEL', 'configured-model')])
def test_vision_api_sends_local_image_and_separate_model(tmp_path, monkeypatch, provider, env, expected):
    from vidppt.engines.llm.qwen_llm_engine import QwenLLMEngine
    from vidppt.engines.llm.openai_llm_engine import OpenAILLMEngine
    cls = QwenLLMEngine if provider == 'qwen' else OpenAILLMEngine
    monkeypatch.delenv(env, raising=False)
    engine = cls(api_key='test-only', model='configured-model')
    page = make_page(tmp_path)
    with patch.object(engine, '_call_api', return_value='{}') as call:
        engine.analyze_slide('公式', page.slide_image)
    messages = call.call_args.args[0]
    assert call.call_args.kwargs['model'] == expected
    assert messages[1]['content'][1]['image_url']['url'].startswith('data:image/png;base64,')
    monkeypatch.setenv(env, 'custom-vision')
    with patch.object(engine, '_call_api', return_value='{}') as call:
        engine.analyze_slide('公式', page.slide_image)
    assert call.call_args.kwargs['model'] == 'custom-vision'


@pytest.mark.parametrize('options', [{'focus_highlight_width': 0}, {'focus_highlight_width': 7}, {'focus_highlight_width': 2.5}, {'focus_highlight_width': True}, {'focus_highlight_color': 'red'}])
def test_invalid_focus_appearance_rejected(options):
    with pytest.raises(ValueError):
        focus_appearance(options)


def test_export_underline_is_thin_colored_and_stays_inside_object():
    from vidppt.utils.video_composer import VideoComposer
    layers = VideoComposer._focus_layers(
        [{'id': 'a', 'x': .1, 'y': .2, 'width': .4, 'height': .1}],
        [{'start': 0, 'end': 1, 'target_ids': ['a']}], 1,
        1920, 1080, 0, 0, 'underline', '#1248AB', 2)
    try:
        line, = layers
        assert line.size == (768, 2)
        x, y = line.pos(0)
        assert x == 192 and y + line.h == round(.2 * 1080) + round(.1 * 1080)
        assert tuple(line.get_frame(0)[0, 0]) == (18, 72, 171)
    finally:
        for layer in layers:
            layer.close()


def test_web_conversion_persists_visual_evidence_for_image_only_page(tmp_path, monkeypatch):
    from queue import Queue
    from types import SimpleNamespace
    import web.app as web_app
    from vidppt.core.models import DocumentContent
    from vidppt.core.registry import ProcessorRegistry
    page = make_page(tmp_path)
    engine = fake_engine()
    content = DocumentContent(pages=[page])
    task_id = 'visual-conversion'
    source = tmp_path / 'source.pptx'
    source.touch()
    monkeypatch.setattr(web_app, 'tasks', {task_id: {'status': 'pending', 'output_dir': str(tmp_path)}})
    monkeypatch.setattr(web_app, 'progress_queues', {task_id: Queue()})
    monkeypatch.setattr(web_app, 'save_state', lambda _: None)
    monkeypatch.setattr(web_app, 'Pipeline', lambda _: SimpleNamespace(llm_engine=engine))
    monkeypatch.setattr(web_app, 'extract_presentation_focus_targets', lambda _: [[]])
    monkeypatch.setattr(web_app, '_auto_review_preview', lambda _: None)
    processor = SimpleNamespace(extract_content=lambda _: content, render_pages=lambda _: [page.slide_image])
    monkeypatch.setattr(ProcessorRegistry, 'get_processor', lambda _: lambda: processor)
    web_app.run_conversion(task_id, str(source), tmp_path, llm_enabled=True)
    preview = json.loads((tmp_path / 'preview.json').read_text())
    saved, = preview['pages']
    assert saved['script'] == page.text
    assert saved['page_analysis']['objects'][0]['evidence'] == 'U=IR'
    assert saved['focus_targets'][0]['id'] == 'p1-v1'
    assert saved['focus_cues'][0]['target_id'] == 'p1-v1'
    assert web_app.tasks[task_id]['status'] == 'awaiting_confirmation'


def test_web_focus_appearance_survives_save_and_strategy_restore(tmp_path, monkeypatch):
    import web.app as web_app
    task_id = 'appearance-roundtrip'
    preview = {'pages': [{'page_number': 1, 'script': '说明', 'focus_targets': [], 'focus_cues': []}]}
    (tmp_path / 'preview.json').write_text(json.dumps(preview))
    monkeypatch.setattr(web_app, 'tasks', {task_id: {'status': 'awaiting_confirmation', 'output_dir': str(tmp_path)}})
    monkeypatch.setattr(web_app, 'save_state', lambda _: None)
    client = web_app.app.test_client()
    response = client.patch(f'/api/course-preview/{task_id}', json={
        'pages': [], 'media_settings': {'focus_highlight_style': 'underline',
                                       'focus_highlight_color': '#1267ab', 'focus_highlight_width': 1}})
    assert response.status_code == 200
    restored = web_app._preview_strategy(web_app.tasks[task_id])
    assert restored['focus_highlight_style'] == 'underline'
    assert restored['focus_highlight_color'] == '#1267AB'
    assert restored['focus_highlight_width'] == 1


def test_named_visual_edges_convert_to_width_and_height():
    item = analysis_object()
    item['bbox'] = {'left': .59, 'top': .18, 'right': .92, 'bottom': .82}
    _, targets = validate_analysis({'summary': '图表', 'objects': [item]}, [], 1)
    assert targets[0]['width'] == pytest.approx(.33)
    assert targets[0]['height'] == pytest.approx(.64)
    item['bbox'] = {'left': .9, 'top': .2, 'right': .1, 'bottom': .5}
    assert validate_analysis({'summary': '', 'objects': [item]}, [], 1)[1] == []


def test_partial_model_focus_is_repaired_without_dropping_narration(tmp_path):
    engine = fake_engine()
    engine.summarize.return_value = json.dumps({'script': '欧姆定律公式，电压等于电流乘电阻。',
        'focus_cues': [{'text': '欧姆定律公式', 'anchor_id': 'p1-v1'}]})
    page = make_page(tmp_path)
    generate_presentation_narration(engine, [page], [], tmp_path)
    assert page.text == '欧姆定律公式，电压等于电流乘电阻。'
    assert page.metadata['focus_mapping_repaired']
    assert page.metadata['focus_cues'][0]['anchor_id'] == 'p1-v1'
    assert ''.join(c['text'] for c in page.metadata['focus_cues']) == page.text
