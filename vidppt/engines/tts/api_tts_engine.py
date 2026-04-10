"""
API TTS 引擎实现
支持通过 API 调用进行文字转语音
包括 MiniMax、阿里云、腾讯云等云服务商的 TTS API
"""

from pathlib import Path
from typing import Optional, Dict, Any
import base64

from ...core.interfaces import TTSEngine


class APITTSEngine(TTSEngine):
    """
    基于 API 的语音合成引擎基类
    可以对接各种云服务商的 TTS API，如：
    - MiniMax
    - 阿里云
    - 腾讯云
    - 百度云
    等
    """

    def __init__(self, api_key: str, api_url: str, **kwargs):
        """
        初始化 API TTS 引擎

        参数:
            api_key: API 密钥
            api_url: API 端点 URL
            **kwargs: 其他配置选项
        """
        self.api_key = api_key
        self.api_url = api_url
        self.options = kwargs

    async def convert_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
    ) -> None:
        """异步转换单个文本为音频"""
        raise NotImplementedError(
            "API TTS Engine 需要根据具体的 API 服务商实现。\n"
            "参考 MiniMaxTTSEngine 或其他具体实现类。"
        )


class MiniMaxTTSEngine(APITTSEngine):
    """
    MiniMax TTS 引擎实现

    支持的语音 ID：
    - male-qn-qingse (男声-清晰)
    - female-qn-nana (女声-娜娜)
    等

    使用方法：
        engine = MiniMaxTTSEngine(
            api_key="sk-cp-xxx",
            api_url="https://api.minimaxi.com/v1/t2a_v2",
            model="speech-2.8-hd",
        )

        await engine.convert_async(
            text="今天天气很好",
            output_path=Path("output.mp3"),
            voice="male-qn-qingse",
            rate="+0%"
        )
    """

    # 默认配置
    DEFAULT_MODEL = "speech-2.8-hd"
    DEFAULT_SAMPLE_RATE = 32000
    DEFAULT_BITRATE = 128000
    DEFAULT_FORMAT = "mp3"
    DEFAULT_CHANNEL = 1

    # 情感类型
    EMOTIONS = ["happy", "sad", "angry", "neutral", "peaceful"]

    def __init__(
        self,
        api_key: str,
        api_url: str = "https://api.minimaxi.com/v1/t2a_v2",
        model: str = DEFAULT_MODEL,
        sample_rate: int = DEFAULT_SAMPLE_RATE,
        bitrate: int = DEFAULT_BITRATE,
        audio_format: str = DEFAULT_FORMAT,
        channel: int = DEFAULT_CHANNEL,
        emotion: str = "neutral",
        **kwargs,
    ):
        """
        初始化 MiniMax TTS 引擎

        参数:
            api_key: MiniMax API 密钥
            api_url: API 端点 URL
            model: 模型名称 (默认: speech-2.8-hd)
            sample_rate: 采样率 (默认: 32000)
            bitrate: 比特率 (默认: 128000)
            audio_format: 音频格式 (默认: mp3)
            channel: 声道数 (默认: 1)
            emotion: 情感类型 (默认: neutral)
            **kwargs: 其他选项
        """
        super().__init__(api_key, api_url, **kwargs)
        self.model = model
        self.sample_rate = sample_rate
        self.bitrate = bitrate
        self.audio_format = audio_format
        self.channel = channel
        self.emotion = emotion if emotion in self.EMOTIONS else "neutral"

    @staticmethod
    def _parse_rate(rate: str) -> float:
        """
        解析语速字符串

        支持的格式:
        - "+20%" -> 1.2
        - "-10%" -> 0.9
        - "+0%" -> 1.0
        - "1.0" -> 1.0

        参数:
            rate: 语速字符串

        返回:
            浮点数语速值 (0.5 - 2.0)
        """
        rate = str(rate).strip()

        try:
            if rate.startswith("+"):
                # "+20%" 格式
                percentage = (
                    float(rate[1:-1]) if rate.endswith("%") else float(rate[1:])
                )
                return max(0.5, min(2.0, 1.0 + percentage / 100))
            elif rate.startswith("-"):
                # "-10%" 格式
                percentage = (
                    float(rate[1:-1]) if rate.endswith("%") else float(rate[1:])
                )
                return max(0.5, min(2.0, 1.0 - percentage / 100))
            else:
                # 直接是数字
                return max(0.5, min(2.0, float(rate)))
        except (ValueError, IndexError):
            return 1.0

    def _build_request_payload(
        self,
        text: str,
        voice: str,
        rate: str,
        emotion: Optional[str] = None,
        pronunciation_dict: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        构建 MiniMax API 请求负载

        参数:
            text: 待转语音的文本
            voice: 语音 ID
            rate: 语速
            emotion: 情感类型
            pronunciation_dict: 发音字典

        返回:
            请求负载字典
        """
        rate_value = self._parse_rate(rate)
        emotion = emotion or self.emotion

        payload = {
            "model": self.model,
            "text": text.strip() if text.strip() else "此页无文字内容。",
            "stream": False,
            "voice_setting": {
                "voice_id": voice,
                "speed": rate_value,
                "vol": 1,
                "pitch": 0,
                "emotion": emotion,
            },
            "audio_setting": {
                "sample_rate": self.sample_rate,
                "bitrate": self.bitrate,
                "format": self.audio_format,
                "channel": self.channel,
            },
        }

        # 添加发音字典（如果提供）
        if pronunciation_dict:
            payload["pronunciation_dict"] = pronunciation_dict

        return payload

    async def convert_async(
        self,
        text: str,
        output_path: Path,
        voice: str,
        rate: str,
        emotion: Optional[str] = None,
        pronunciation_dict: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        异步转换单个文本为音频

        参数:
            text: 待转语音的文本
            output_path: 输出文件路径
            voice: 语音 ID
            rate: 语速
            emotion: 情感类型（可选）
            pronunciation_dict: 发音字典（可选）

        抛出异常:
            httpx.HTTPStatusError: API 调用失败
            IOError: 文件保存失败
        """
        try:
            import httpx
        except ImportError:
            raise ImportError("httpx 未安装。请运行: pip install httpx")

        # 构建请求负载
        payload = self._build_request_payload(
            text, voice, rate, emotion, pronunciation_dict
        )

        # 构建请求头
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        # 发送 API 请求
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.api_url,
                headers=headers,
                json=payload,
                timeout=30.0,
            )
            response.raise_for_status()

            # 解析响应
            result = response.json()

            # 提取音频数据
            # MiniMax API 返回格式: {"data": {"audio": "hex_string"}, ...}
            audio_hex = result.get("data", {}).get("audio")
            if not audio_hex:
                raise ValueError("API 返回的音频数据为空")

            # 从十六进制转换为二进制
            audio_data = bytes.fromhex(audio_hex)

            # 保存到文件
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(audio_data)

    async def batch_convert_with_emotions(
        self,
        texts: list[tuple[int, str, Path, str]],
        voice: str,
        rate: str,
        emotions: Optional[list[str]] = None,
        batch_size: int = 5,
    ) -> None:
        """
        批量转换文本为音频，支持不同的情感

        参数:
            texts: [(页码, 文本, 输出路径, 情感), ...]
            voice: 语音 ID
            rate: 语速
            emotions: 情感列表
            batch_size: 批处理大小
        """
        import asyncio

        tasks = []
        for page_num, text, path, emotion in texts:
            task = self.convert_async(
                text=text,
                output_path=path,
                voice=voice,
                rate=rate,
                emotion=emotion,
            )
            tasks.append(task)

        # 分批处理避免并发过多
        for i in range(0, len(tasks), batch_size):
            batch_tasks = tasks[i : i + batch_size]
            await asyncio.gather(*batch_tasks)
