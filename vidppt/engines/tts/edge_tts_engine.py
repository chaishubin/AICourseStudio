"""
Edge TTS 引擎实现
"""
import os
from pathlib import Path

import edge_tts

from ...core.interfaces import TTSEngine

# edge-tts 使用 WebSocket 直连，不能走 HTTP 代理
for _proxy_key in ("http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"):
    os.environ.pop(_proxy_key, None)


class EdgeTTSEngine(TTSEngine):
    """基于 Microsoft Edge TTS 的语音合成引擎"""

    async def convert_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
    ) -> None:
        """异步转换单个文本为音频"""
        content = text.strip() if text.strip() else "此页无文字内容。"
        communicate = edge_tts.Communicate(content, voice, rate=rate)
        await communicate.save(str(output_path))
