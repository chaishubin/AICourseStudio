import json
from types import SimpleNamespace

import pytest

from vidppt.generation.teaching_context import normalize_teaching_context, teaching_prompt
from vidppt.generation.course_builder import CourseBuilder
from vidppt.generation.page_revision import PageScriptReviser
from vidppt.review.course_reviewer import CourseReviewer


@pytest.mark.parametrize('value', [{'scenario': 'bad'}, {'audience': '长' * 201},
                                    {'delivery_mode': 'bad'}, [], {'scenario': []}])
def test_invalid_context_rejected(value):
    with pytest.raises(ValueError):
        normalize_teaching_context(value)


def test_recorded_and_live_have_distinct_interaction_requirements():
    assert '不依赖现场回答' in teaching_prompt()
    assert '不依赖现场回答' not in teaching_prompt({'delivery_mode': 'live'})


def test_generation_revision_review_share_scenario():
    context = {'scenario': 'practical', 'audience': '新入职设备操作员', 'teaching_goal': 'operation'}
    captured = []
    def summarize(prompt, **kwargs):
        captured.append(kwargs['system_prompt'])
        return '{"script":"操作讲解"}'
    engine = SimpleNamespace(summarize=summarize)
    builder = CourseBuilder(engine, teaching_context=context)
    builder._from_llm_json = lambda *args: None
    builder.build(SimpleNamespace(full_text='设备操作原文'))
    PageScriptReviser(engine=engine, teaching_context=context).revise({'page_number': 1}, '说明步骤', '原文')
    engine.summarize = lambda prompt, **kwargs: (captured.append(kwargs['system_prompt']) or json.dumps({
        'review_completed': True, 'reviewed_pages': [1], 'status': 'passed', 'findings': []}))
    CourseReviewer(engine=engine).review({'teaching_context': context, 'pages': [{'page_number': 1, 'script': '讲解'}]}, 'full')
    assert len(captured) == 3
    assert all('实训教师' in prompt and '新入职设备操作员' in prompt for prompt in captured)
    assert '可执行性' in captured[-1]
