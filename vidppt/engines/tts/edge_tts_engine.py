"""
Edge TTS 引擎实现
"""
import os
import json
import hashlib
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
        *,
        capture_timestamps: bool = False,
    ) -> None:
        """异步转换单个文本为音频"""
        content = text.strip() if text.strip() else "此页无文字内容。"
        timing_path = output_path.with_suffix(".timing.json")
        timing_path.unlink(missing_ok=True)
        if not capture_timestamps:
            communicate = edge_tts.Communicate(content, voice, rate=rate)
            await communicate.save(str(output_path))
            return

        communicate = edge_tts.Communicate(
            content, voice, rate=rate, boundary="WordBoundary"
        )
        boundaries = []
        digest = hashlib.sha256()
        try:
            with output_path.open("wb") as audio:
                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio.write(chunk["data"])
                        digest.update(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        boundaries.append({
                            "text": chunk["text"],
                            "start": chunk["offset"] / 10_000_000,
                            "end": (chunk["offset"] + chunk["duration"]) / 10_000_000,
                        })
            if not output_path.stat().st_size:
                raise ValueError("TTS 返回空音频")
            timing_path.write_text(json.dumps({
                "audio_sha256": digest.hexdigest(),
                "boundaries": boundaries,
            }, ensure_ascii=False), encoding="utf-8")
        except Exception:
            output_path.unlink(missing_ok=True)
            timing_path.unlink(missing_ok=True)
            raise
