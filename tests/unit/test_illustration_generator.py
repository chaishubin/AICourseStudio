from vidppt.core.course import CourseSection
from vidppt.generation.illustration_generator import DashScopeIllustrationGenerator


def test_illustration_prompt_forbids_embedded_text():
    section = CourseSection(
        id="slide-1",
        title="AI 生成效果图",
        bullets=["169 构图", "教学场景"],
        image_prompt="课堂中的 AI 助教和教师协作",
    )

    prompt = DashScopeIllustrationGenerator._prompt("AI 课程", section)

    assert "纯无字横版教学插图" in prompt
    assert "绝对禁止出现任何文字" in prompt
    assert "标题" in prompt
    assert "字母" in prompt
    assert "数字" in prompt
    assert "屏幕文字" in prompt
    assert "所有说明文字由 PPT 文本框另行排版" in prompt
    assert "课堂中的 AI 助教和教师协作" in prompt
