"""Regression coverage for target-based lesson cuts and short final lessons."""

import pytest

from web.app import _recommend_lesson_segments


def pages(durations, sections=None):
    return [
        {'page_number': index + 1, 'duration': duration,
         'title': f'页面{index + 1}',
         'section_title': sections[index] if sections else ''}
        for index, duration in enumerate(durations)
    ]


def ranges(segments):
    return [(item['start_page'], item['end_page']) for item in segments]


def test_screenshot_course_stays_together():
    content = pages([69] * 20 + [1367 / 21] * 21 + [67])
    result = _recommend_lesson_segments(content, 40, 'section')
    assert ranges(result) == [(1, 42)]
    assert result[0]['estimated_seconds'] == 2814


def test_section_priority_prefers_boundary_near_target():
    # Old implementation cut at 23 minutes; the next boundary is at 46.
    content = pages([23 * 60, 23 * 60, 34 * 60], ['A', 'B', 'C'])
    result = _recommend_lesson_segments(content, 40, 'section')
    assert ranges(result) == [(1, 2), (3, 3)]


def test_section_boundary_preferred_over_closer_page_cut():
    content = pages([20 * 60, 15 * 60, 5 * 60, 20 * 60, 20 * 60],
                    ['A', 'A', 'B', 'B', 'B'])
    result = _recommend_lesson_segments(content, 40, 'section')
    assert ranges(result) == [(1, 2), (3, 5)]


def test_long_section_falls_back_to_page_boundary():
    result = _recommend_lesson_segments(pages([10 * 60] * 8, ['A'] * 8), 40, 'section')
    assert ranges(result) == [(1, 4), (5, 8)]


@pytest.mark.parametrize('priority', ['section', 'duration'])
def test_short_tail_is_merged(priority):
    result = _recommend_lesson_segments(pages([10 * 60] * 4 + [67]), 40, priority)
    assert ranges(result) == [(1, 5)]


def test_duration_priority_rebalances_tail_when_merge_too_long():
    result = _recommend_lesson_segments(pages([30 * 60, 30 * 60, 60]), 40, 'duration')
    assert ranges(result) == [(1, 1), (2, 3)]


@pytest.mark.parametrize('priority', ['section', 'duration'])
def test_cuts_cover_all_pages_and_preserve_total_duration(priority):
    content = pages([190, 420, 75, 1000, 550, 90, 1800, 20])
    result = _recommend_lesson_segments(list(reversed(content)), 10, priority)
    covered = [number for segment in result
               for number in range(segment['start_page'], segment['end_page'] + 1)]
    assert covered == list(range(1, 9))
    assert sum(segment['estimated_seconds'] for segment in result) == sum(p['duration'] for p in content)
    assert [s['id'] for s in result] == list(range(1, len(result) + 1))


def test_generated_title_is_short_and_source_title_unchanged():
    content = pages([60])
    original = '欢迎来到项目三：可编程序控制器软件和位逻辑指令应用。在本项目中我们将学习指令。'
    content[0]['title'] = original
    result = _recommend_lesson_segments(content, 40, 'section')
    assert len(result[0]['title']) <= 28
    assert result[0]['title'] == original.split('。')[0]
    assert content[0]['title'] == original


@pytest.mark.parametrize('priority', ['section', 'duration'])
def test_empty_and_single_long_page(priority):
    assert _recommend_lesson_segments([], 40, priority) == []
    assert ranges(_recommend_lesson_segments(pages([7200]), 40, priority)) == [(1, 1)]


def test_generated_title_without_punctuation_is_truncated():
    content = pages([60])
    content[0]['title'] = '长标题' * 30
    result = _recommend_lesson_segments(content, 40, 'section')
    assert result[0]['title'] == content[0]['title'][:27] + '…'
