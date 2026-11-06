"""Read slide objects without changing or re-saving the source presentation."""
from pathlib import Path
from lxml import etree
from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE


def presentation_objects(path: Path) -> list[list[dict]]:
    prs = Presentation(str(path))
    pages = []
    for number, slide in enumerate(prs.slides, 1):
        objects = []

        def walk(shapes, prefix='', transform=(1, 1, 0, 0)):
            sx, sy, ox, oy = transform
            for index, shape in enumerate(shapes, 1):
                key = f'{prefix}{index}'
                if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
                    xf = shape._element.grpSpPr.xfrm
                    if xf is not None and xf.chExt is not None and xf.chOff is not None and xf.chExt.cx and xf.chExt.cy:
                        gx, gy = shape.width / xf.chExt.cx, shape.height / xf.chExt.cy
                        walk(shape.shapes, key + '-', (
                            sx * gx, sy * gy,
                            ox + sx * (shape.left - xf.chOff.x * gx),
                            oy + sy * (shape.top - xf.chOff.y * gy),
                        ))
                    continue
                raw_x = (ox + sx * shape.left) / prs.slide_width
                raw_y = (oy + sy * shape.top) / prs.slide_height
                x, y = max(0, raw_x), max(0, raw_y)
                width = min(1, raw_x + sx * shape.width / prs.slide_width) - x
                height = min(1, raw_y + sy * shape.height / prs.slide_height) - y
                if width <= 0 or height <= 0:
                    continue
                text = str(getattr(shape, 'text', '') or '').strip()
                # Office Math text is not exposed through TextFrame.text.
                math = shape._element.xpath('.//*[local-name()="oMath"]')
                formula = [''.join(node.itertext()) for node in math]
                kind, data = 'text', {}
                if getattr(shape, 'has_chart', False):
                    kind = 'chart'
                    chart = shape.chart
                    series = []
                    for item in chart.series:
                        series.append({'name': item.name, 'values': list(item.values)})
                    categories = []
                    for plot in chart.plots:
                        try:
                            categories = [c.label for c in plot.categories]
                        except (AttributeError, ValueError):
                            categories = []
                        if categories:
                            break
                    text = chart.chart_title.text_frame.text if chart.has_title and chart.chart_title.has_text_frame else shape.name
                    data = {'categories': categories, 'series': series}
                elif getattr(shape, 'has_table', False):
                    kind = 'table'
                    rows = [[cell.text for cell in row.cells] for row in shape.table.rows]
                    text = '\n'.join(' | '.join(row) for row in rows)
                    data = {'rows': rows}
                elif formula:
                    kind, data = 'formula', {'office_math_text': formula, 'office_math_xml': [etree.tostring(node, encoding='unicode') for node in math]}
                    text = '\n'.join(filter(None, [text, *formula]))
                elif shape.shape_type == MSO_SHAPE_TYPE.PICTURE:
                    kind, text = 'image', shape.name or '页面插图'
                elif not text:
                    continue
                anchor = f'p{number}-a{key}'
                objects.append({
                    'id': anchor, 'anchor_id': anchor, 'shape_id': f'shape-{key}',
                    'text': text, 'kind': kind, 'native_data': data, 'source': 'pptx',
                    'x': round(x, 6), 'y': round(y, 6),
                    'width': round(width, 6), 'height': round(height, 6),
                    'role': 'content' if kind != 'text' else ('title' if y < .24 else 'content'),
                })
        walk(slide.shapes)
        pages.append(objects)
    return pages
