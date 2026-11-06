"""Shared validated focus appearance (width is measured on a 1080p slide)."""
import re


def focus_appearance(data: dict) -> dict:
    color = str(data.get('focus_highlight_color', '#FFAE1F')).strip()
    if not re.fullmatch(r'#[0-9a-fA-F]{6}', color):
        raise ValueError('焦点线条颜色必须是 #RRGGBB 格式')
    raw = data.get('focus_highlight_width', 2)
    try:
        width = int(raw)
    except (TypeError, ValueError, OverflowError):
        raise ValueError('焦点线条粗细必须是 1 到 6 的整数') from None
    if isinstance(raw, bool) or str(raw) not in {str(n) for n in range(1, 7)}:
        raise ValueError('焦点线条粗细必须是 1 到 6 的整数')
    return {'focus_highlight_color': color.upper(), 'focus_highlight_width': width}
