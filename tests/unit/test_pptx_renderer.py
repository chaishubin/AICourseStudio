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
