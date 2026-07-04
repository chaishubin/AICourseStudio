"""将 Course 渲染为包含可编辑文本和逐页备注的 PPTX。"""

from pathlib import Path

from ..core.course import Course, CourseSection


class PPTXRenderer:
    def render(self, course: Course, output_path: Path) -> Path:
        from pptx import Presentation

        presentation = Presentation()
        presentation.core_properties.title = course.title
        presentation.core_properties.subject = course.description

        for page in course.sections:
            self._add_slide(presentation, page)

        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        presentation.save(output_path)
        return output_path

    def _add_slide(self, presentation, page: CourseSection) -> None:
        is_cover = page.layout == "cover"
        layout_index = 0 if is_cover else 1
        slide = presentation.slides.add_slide(presentation.slide_layouts[layout_index])
        slide.shapes.title.text = page.title

        if not is_cover and len(slide.placeholders) > 1:
            frame = slide.placeholders[1].text_frame
            frame.clear()
            for index, bullet in enumerate(page.bullets):
                paragraph = frame.paragraphs[0] if index == 0 else frame.add_paragraph()
                paragraph.text = bullet
                paragraph.level = 0

        notes = page.script
        if page.notes:
            notes = f"{notes}\n\n讲师备注：\n{page.notes}".strip()
        if notes:
            notes_frame = getattr(slide.notes_slide, "notes_text_frame", None)
            if notes_frame is not None:
                notes_frame.text = notes
