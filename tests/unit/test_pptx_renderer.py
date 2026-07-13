from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE, MSO_SHAPE_TYPE
from pptx.enum.text import PP_ALIGN

from vidppt.core.course import CourseSection
from vidppt.renderers.pptx_renderer import PPTXRenderer


def test_organic_card_numbers_are_centered_inside_markers():
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    renderer = PPTXRenderer()
    renderer.DESIGN_STYLE = "organic"

    renderer._render_content_cards(
        slide,
        CourseSection(id="cards", title="知识资产化", bullets=["统一治理"]),
        x=0.75,
        y=2.0,
        width=11.8,
        height=3.8,
        accent=renderer.TEAL,
        columns=3,
    )

    number_box = next(
        shape for shape in slide.shapes
        if getattr(shape, "has_text_frame", False) and shape.text == "01"
    )
    marker = next(
        shape for shape in slide.shapes
        if shape.shape_type == MSO_SHAPE_TYPE.AUTO_SHAPE
        and shape.auto_shape_type == MSO_SHAPE.OVAL
    )
    assert (number_box.left, number_box.top) == (marker.left, marker.top)
    assert (number_box.width, number_box.height) == (marker.width, marker.height)
    assert number_box.text_frame.paragraphs[0].alignment == PP_ALIGN.CENTER
    assert str(number_box.text_frame.paragraphs[0].runs[0].font.color.rgb) == "FFFFFF"


def test_text_normalizes_emoji_status_marks_and_uses_symbol_font():
    presentation = Presentation()
    slide = presentation.slides.add_slide(presentation.slide_layouts[6])
    renderer = PPTXRenderer()

    box = renderer._text(
        slide,
        "✅ 可执行 · ❌ 不可执行 · ☑ 已确认 · ☒ 已否决 · ⚠️ 注意 → 下一步",
        0,
        0,
        12,
        1,
        18,
        renderer.INK,
    )

    paragraph = box.text_frame.paragraphs[0]
    assert box.text == "✓ 可执行 · ✗ 不可执行 · ☑ 已确认 · ☒ 已否决 · ⚠ 注意 → 下一步"
    symbol_runs = [run for run in paragraph.runs if run.font.name == renderer.SYMBOL_FONT]
    assert "".join(run.text for run in symbol_runs) == "✓✗☑☒⚠→"
    assert {run.font.name for run in paragraph.runs} == {
        renderer.FONT,
        renderer.SYMBOL_FONT,
    }


def test_presentation_symbol_normalization_covers_common_generated_icons():
    renderer = PPTXRenderer()

    assert renderer._normalize_presentation_symbols(
        "✔️通过 ❎失败 🚫禁止 ⛔停止 ⭐重点 👉下一步 🔹条目 🔸次要 📌提示 🎯目标"
    ) == "✓通过 ✗失败 ⊘禁止 ⊘停止 ★重点 →下一步 ◆条目 ◇次要 ◆提示 ◎目标"

    assert renderer._normalize_presentation_symbols(
        "🔍查询 📊分析 🧠决策 🔑关键 💡提示 🔧实施 🚀进阶 🛡️安全 👥协作"
    ) == "◆查询 ◆分析 ◆决策 ◆关键 ◆提示 ◆实施 ◆进阶 ◆安全 ◆协作"
