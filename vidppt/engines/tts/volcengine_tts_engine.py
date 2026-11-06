"""火山引擎豆包语音 HTTP 非流式 TTS 引擎。"""

import asyncio
import base64
import json
import math
import os
import re
import uuid
from pathlib import Path
from typing import Optional

from loguru import logger

from ...core.interfaces import TTSEngine
from ...utils.speech_text import safe_speech_boundary


class VolcengineTTSEngine(TTSEngine):
    DEFAULT_API_URL = "https://openspeech.bytedance.com/api/v1/tts"
    V3_API_URL = "https://openspeech.bytedance.com/api/v3/tts/unidirectional"

    def __init__(
        self,
        appid: Optional[str] = None,
        access_token: Optional[str] = None,
        api_url: Optional[str] = None,
        cluster: str = "volcano_tts",
        sample_rate: int = 24000,
        audio_format: str = "mp3",
        timeout: float = 60.0,
        max_retries: int = 3,
        uid: str = "ai-course-studio",
        volume_ratio: float = 1.0,
        pitch_ratio: float = 1.0,
        emotion: Optional[str] = None,
        emotion_scale: float = 4.0,
        language: Optional[str] = None,
        silence_duration: Optional[int] = None,
        api_key: Optional[str] = None,
        api_version: Optional[str] = None,
        resource_id: Optional[str] = None,
        **kwargs,
    ):
        self.appid = appid or os.getenv("VOLCENGINE_TTS_APPID")
        self.access_token = access_token or os.getenv(
            "VOLCENGINE_TTS_ACCESS_TOKEN"
        )
        self.api_key = api_key or os.getenv("VOLCENGINE_TTS_API_KEY")
        if not self.api_key and not (self.appid and self.access_token):
            raise ValueError(
                "火山 TTS 凭证未设置，请配置 VOLCENGINE_TTS_API_KEY，或 VOLCENGINE_TTS_APPID 和 "
                "VOLCENGINE_TTS_ACCESS_TOKEN"
            )
        self.api_url = api_url or os.getenv("VOLCENGINE_TTS_API_URL")
        self.api_version = api_version or os.getenv("VOLCENGINE_TTS_API_VERSION") or "auto"
        if self.api_version not in {"auto", "v1", "v3"}:
            raise ValueError("VOLCENGINE_TTS_API_VERSION 只能是 auto、v1 或 v3")
        self.resource_id = resource_id or os.getenv("VOLCENGINE_TTS_RESOURCE_ID")
        self.cluster = cluster
        self.sample_rate = sample_rate
        self.audio_format = audio_format
        self.timeout = timeout
        self.max_retries = max_retries
        self.uid = uid
        self.volume_ratio = self._clamp(volume_ratio, 0.1, 3.0, 1.0)
        self.pitch_ratio = self._clamp(pitch_ratio, 0.1, 3.0, 1.0)
        self.emotion = emotion
        self.emotion_scale = self._clamp(emotion_scale, 1.0, 5.0, 4.0)
        self.explicit_language = kwargs.get("explicit_language", language)
        self.silence_duration = silence_duration
        self.options = kwargs

    @staticmethod
    def _clamp(value, minimum: float, maximum: float, default: float) -> float:
        try:
            return max(minimum, min(maximum, float(value)))
        except (TypeError, ValueError):
            return default

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
        selected_emotion = emotion or kwargs.get("emotion") or self.emotion
        language = kwargs.get(
            "explicit_language", kwargs.get("language", self.explicit_language)
        )
        if language is None:
            english_phrase = re.fullmatch(
                r"[A-Za-z]+(?: +[A-Za-z]+)+[.!?]?", text.strip()
            )
            language = "en" if english_phrase else "zh-cn"
        audio = {
            "voice_type": voice,
            "encoding": kwargs.get("audio_format", self.audio_format),
            "rate": kwargs.get("sample_rate", self.sample_rate),
            "speed_ratio": self._parse_rate(rate),
            "volume_ratio": self._clamp(
                kwargs.get("volume_ratio", self.volume_ratio), 0.1, 3.0, 1.0
            ),
            "pitch_ratio": self._clamp(
                kwargs.get("pitch_ratio", self.pitch_ratio), 0.1, 3.0, 1.0
            ),
            "explicit_language": "zh-cn" if language == "cn" else language,
        }
        if selected_emotion:
            audio["emotion"] = selected_emotion
            audio["emotion_scale"] = self._clamp(
                kwargs.get("emotion_scale", self.emotion_scale), 1.0, 5.0, 4.0
            )
        request = {
            "reqid": uuid.uuid4().hex,
            "text": text.strip() or "此页无文字内容。",
            "text_type": "plain",
            "operation": "query",
            "with_frontend": "1",
            "frontend_type": "unitTson",
        }
        silence_duration = kwargs.get("silence_duration", self.silence_duration)
        if silence_duration is not None:
            request["silence_duration"] = str(
                int(self._clamp(silence_duration, 0, 3000, 0))
            )
        return {
            "app": {
                "appid": self.appid,
                "token": self.access_token,
                "cluster": kwargs.get("cluster", self.cluster),
            },
            "user": {"uid": self.uid},
            "audio": audio,
            "request": request,
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

        version = self._version_for_voice(voice)
        if version == "v1" and not (self.appid and self.access_token):
            raise ValueError("旧版火山音色需要 AppID 和 Access Token；新版 API Key 请搭配 V3 音色")
        headers = {"Authorization": f"Bearer;{self.access_token}", "Content-Type": "application/json"}
        chunks = self._split_text(text)
        audio_parts = []
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            for chunk in chunks:
                if version == "v3":
                    audio_parts.append(await self._request_v3_audio(client, chunk, voice, rate, **kwargs))
                else:
                    payload = self._build_payload(chunk, voice, rate, **kwargs)
                    audio_parts.append(await self._request_audio(client, headers, payload))
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"".join(audio_parts))

    async def _request_audio(self, client, headers: dict, payload: dict) -> bytes:
        import httpx

        last_error = None
        for attempt in range(1, self.max_retries + 1):
            try:
                response = await client.post(
                    self.api_url or self.DEFAULT_API_URL, headers=headers, json=payload
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

    def _version_for_voice(self, voice: str) -> str:
        return self.cache_identity(voice, {
            "api_version": self.api_version, "api_url": self.api_url,
            "api_key": self.api_key, "resource_id": self.resource_id,
        })["api_version"]

    @classmethod
    def cache_identity(cls, voice: str, options: dict | None = None) -> dict:
        """Resolve protocol settings without credentials in cache keys."""
        options = options or {}
        version = options.get("api_version") or os.getenv("VOLCENGINE_TTS_API_VERSION") or "auto"
        url = options.get("api_url") or os.getenv("VOLCENGINE_TTS_API_URL")
        resource = options.get("resource_id") or os.getenv("VOLCENGINE_TTS_RESOURCE_ID")
        if version == "auto":
            if url:
                version = "v3" if "/v3/" in url else "v1"
            else:
                use_v3 = "_uranus_" in voice or resource or options.get("api_key") or os.getenv("VOLCENGINE_TTS_API_KEY")
                version = "v3" if use_v3 else "v1"
        if version not in {"v1", "v3"}:
            raise ValueError("VOLCENGINE_TTS_API_VERSION 只能是 auto、v1 或 v3")
        return {
            "text_split_revision": 2,
            "api_version": version,
            "api_url": url or (cls.V3_API_URL if version == "v3" else cls.DEFAULT_API_URL),
            "resource_id": (resource or ("seed-tts-2.0" if "_uranus_" in voice else "seed-tts-1.0")) if version == "v3" else "",
        }

    def _build_v3_payload(self, text: str, voice: str, rate: str, **kwargs) -> dict:
        audio = {
            "format": kwargs.get("audio_format", self.audio_format),
            "sample_rate": kwargs.get("sample_rate", self.sample_rate),
            "speech_rate": round((self._clamp(self._parse_rate(rate), 0.5, 2, 1) - 1) * 100),
            "loudness_rate": round((self._clamp(kwargs.get("volume_ratio", self.volume_ratio), 0.5, 2, 1) - 1) * 100),
        }
        emotion = kwargs.get("emotion") or self.emotion
        if emotion:
            audio["emotion"] = emotion
            audio["emotion_scale"] = self._clamp(kwargs.get("emotion_scale", self.emotion_scale), 1, 5, 4)
        additions = {}
        pitch = self._clamp(kwargs.get("pitch_ratio", self.pitch_ratio), 0.5, 2, 1)
        if pitch != 1:
            additions["post_process"] = {"pitch": round(12 * math.log2(pitch))}
        language = kwargs.get("explicit_language", kwargs.get("language", self.explicit_language))
        if language:
            additions["explicit_language"] = "zh-cn" if language == "cn" else language
        pause = kwargs.get("silence_duration", self.silence_duration)
        if pause is not None:
            additions["silence_duration"] = int(self._clamp(pause, 0, 3000, 0))
        return {
            "user": {"uid": self.uid},
            "req_params": {"text": text, "speaker": voice, "audio_params": audio,
                           "additions": json.dumps(additions)},
        }

    async def _request_v3_audio(self, client, text: str, voice: str, rate: str, **kwargs) -> bytes:
        import httpx

        headers = {
            "Content-Type": "application/json",
            "X-Api-Resource-Id": self.resource_id or ("seed-tts-2.0" if "_uranus_" in voice else "seed-tts-1.0"),
        }
        if self.api_key:
            headers["X-Api-Key"] = self.api_key
        else:
            headers.update({"X-Api-App-Id": self.appid, "X-Api-Access-Key": self.access_token})
        payload = self._build_v3_payload(text, voice, rate, **kwargs)
        for attempt in range(1, self.max_retries + 1):
            headers["X-Api-Request-Id"] = uuid.uuid4().hex
            try:
                response = await client.post(self.api_url or self.V3_API_URL, headers=headers, json=payload)
                response.raise_for_status()
                parts, completed = [], False
                for line in response.iter_lines():
                    line = line.strip()
                    if not line or line.startswith((":", "event:", "id:")):
                        continue
                    if line.startswith("data:"):
                        line = line[5:].strip()
                    event = json.loads(line)
                    code = event.get("code")
                    if code not in {0, 20000000}:
                        raise RuntimeError(f"火山 V3 TTS 错误 code={code}: {event.get('message', '')}")
                    if event.get("data"):
                        parts.append(base64.b64decode(event["data"], validate=True))
                    if code == 20000000:
                        completed = True
                        break
                audio = b"".join(parts)
                if not completed or not audio:
                    raise ValueError("火山 V3 TTS 音频为空或响应未完成，请重试")
                return audio
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == self.max_retries:
                    raise
                await asyncio.sleep(2 ** (attempt - 1))
        raise RuntimeError("火山 V3 TTS 请求失败")

    @staticmethod
    def _split_text(text: str, max_bytes: int = 900) -> list[str]:
        """按 UTF-8 字节切段，为官方 HTTP 接口保留请求开销余量。"""
        if max_bytes < 4:
            raise ValueError("TTS 分段字节上限不能小于 4")
        source = text.strip() or "此页无文字内容。"
        chunks = []
        start = 0
        while start < len(source):
            end, size = start, 0
            while end < len(source):
                char_size = len(source[end].encode("utf-8"))
                if size + char_size > max_bytes:
                    break
                size += char_size
                end += 1
            end = safe_speech_boundary(source, end, start)
            if len(source[start:end].encode("utf-8")) > max_bytes:
                raise ValueError("单个英文或数字词组超过 TTS 分段字节上限，请缩短后重试")
            chunks.append(source[start:end])
            start = end
        return chunks
