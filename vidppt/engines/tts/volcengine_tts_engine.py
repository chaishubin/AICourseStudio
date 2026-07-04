"""火山引擎豆包语音 HTTP 非流式 TTS 引擎。"""

import asyncio
import base64
import os
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

from ...core.interfaces import TTSEngine


class VolcengineTTSEngine(TTSEngine):
    DEFAULT_API_URL = "https://openspeech.bytedance.com/api/v1/tts"

    def __init__(
        self,
        appid: Optional[str] = None,
        access_token: Optional[str] = None,
        api_url: str = DEFAULT_API_URL,
        cluster: str = "volcano_tts",
        sample_rate: int = 24000,
        audio_format: str = "mp3",
        timeout: float = 60.0,
        max_retries: int = 3,
        uid: str = "ai-course-studio",
        **kwargs,
    ):
        self.appid = appid or os.getenv("VOLCENGINE_TTS_APPID")
        self.access_token = access_token or os.getenv(
            "VOLCENGINE_TTS_ACCESS_TOKEN"
        )
        if not self.appid or not self.access_token:
            raise ValueError(
                "火山 TTS 凭证未设置，请配置 VOLCENGINE_TTS_APPID 和 "
                "VOLCENGINE_TTS_ACCESS_TOKEN"
            )
        self.api_url = api_url
        self.cluster = cluster
        self.sample_rate = sample_rate
        self.audio_format = audio_format
        self.timeout = timeout
        self.max_retries = max_retries
        self.uid = uid
        self.options = kwargs

    @staticmethod
    def _parse_rate(rate: str) -> float:
        value = str(rate).strip()
        try:
            if value.endswith("%"):
                return max(0.2, min(3.0, 1.0 + float(value[:-1]) / 100))
            return max(0.2, min(3.0, float(value)))
        except ValueError:
            return 1.0

    def _build_payload(
        self,
        text: str,
        voice: str,
        rate: str,
        emotion: Optional[str] = None,
        **kwargs,
    ) -> dict:
        audio = {
            "voice_type": voice,
            "encoding": kwargs.get("audio_format", self.audio_format),
            "rate": kwargs.get("sample_rate", self.sample_rate),
            "speed_ratio": self._parse_rate(rate),
        }
        if emotion:
            audio["emotion"] = emotion
        return {
            "app": {
                "appid": self.appid,
                "token": self.access_token,
                "cluster": kwargs.get("cluster", self.cluster),
            },
            "user": {"uid": self.uid},
            "audio": audio,
            "request": {
                "reqid": uuid.uuid4().hex,
                "text": text.strip() or "此页无文字内容。",
                "text_type": "plain",
                "operation": "query",
            },
        }

    async def convert_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
        **kwargs,
    ) -> None:
        try:
            import httpx
        except ImportError as exc:
            raise ImportError("火山 TTS 调用需要 httpx，请安装 api 依赖") from exc

        headers = {
            "Authorization": f"Bearer;{self.access_token}",
            "Content-Type": "application/json",
        }
        chunks = self._split_text(text)
        audio_parts = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for chunk in chunks:
                payload = self._build_payload(chunk, voice, rate, **kwargs)
                audio_parts.append(
                    await self._request_audio(client, headers, payload)
                )
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"".join(audio_parts))

    async def _request_audio(self, client, headers: dict, payload: dict) -> bytes:
        import httpx

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.post(
                    self.api_url, headers=headers, json=payload
                )
                response.raise_for_status()
                result = response.json()
                if result.get("code") not in (None, 0, 3000):
                    raise RuntimeError(
                        f"火山 TTS 返回错误 code={result.get('code')}: "
                        f"{result.get('message', result)}"
                    )
                audio_b64 = result.get("data")
                if isinstance(audio_b64, dict):
                    audio_b64 = audio_b64.get("audio") or audio_b64.get("data")
                if not audio_b64:
                    raise ValueError(f"火山 TTS 返回音频为空: {result}")
                return base64.b64decode(audio_b64)
            except (httpx.TimeoutException, httpx.NetworkError) as exc:
                last_error = exc
                if attempt == self.max_retries:
                    raise
                wait = 2 ** (attempt - 1)
                logger.warning(
                    f"火山 TTS 请求失败（{attempt}/{self.max_retries}），"
                    f"{wait}s 后重试: {exc}"
                )
                await asyncio.sleep(wait)
        raise last_error or RuntimeError("火山 TTS 请求失败")

    @staticmethod
    def _split_text(text: str, max_bytes: int = 900) -> list[str]:
        """按 UTF-8 字节切段，为官方 HTTP 接口保留请求开销余量。"""
        source = text.strip() or "此页无文字内容。"
        chunks, current = [], ""
        for char in source:
            candidate = current + char
            if current and len(candidate.encode("utf-8")) > max_bytes:
                chunks.append(current)
                current = char
            else:
                current = candidate
        if current:
            chunks.append(current)
        return chunks
