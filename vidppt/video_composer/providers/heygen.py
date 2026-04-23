"""
HeyGen API Provider 实现 (示例)

HeyGen: https://www.heygen.com/

配置参数：
- api_key: API 密钥（必需）
- avatar_id: 数字人 ID
- voice_id: 语音 ID
"""

import json
import requests
from pathlib import Path
from typing import Any, Dict
import time

from .base import BaseFaceVideoProvider, FaceVideoResult
from .registry import register_provider


@register_provider("heygen")
class HeyGenProvider(BaseFaceVideoProvider):
    """HeyGen Cloud API 人脸视频生成"""

    name = "heygen"
    description = "HeyGen Cloud API - AI 视频生成平台"

    API_BASE = "https://api.heygen.com/v2"

    def get_required_params(self) -> list:
        return ["api_key"]

    def get_optional_params(self) -> list:
        return [
            "avatar_id",      # 数字人 ID
            "voice_id",       # 语音 ID
            "background",     # 背景设置
            "resolution",     # 分辨率
            "timeout",        # 超时时间
        ]

    def generate(
        self,
        face_image: Path,
        text: str,
        output_path: Path,
        **kwargs
    ) -> FaceVideoResult:
        """
        通过 HeyGen API 生成视频

        Args:
            face_image: 人脸图像（用于创建自定义 Avatar）
            text: 要说的文本
            output_path: 输出路径
        """
        api_key = self.config["api_key"]
        avatar_id = self.config.get("avatar_id")
        voice_id = self.config.get("voice_id")

        headers = {
            "X-Api-Key": api_key,
            "Content-Type": "application/json",
        }

        # 1. 创建视频任务
        payload = self._build_payload(text, avatar_id, voice_id)
        video_id = self._create_video(headers, payload)

        # 2. 等待生成完成
        video_url = self._poll_status(headers, video_id)

        # 3. 下载视频
        self._download_video(video_url, output_path)

        return FaceVideoResult(
            video_path=output_path,
            metadata={"video_id": video_id, "url": video_url}
        )

    def _build_payload(
        self,
        text: str,
        avatar_id: str = None,
        voice_id: str = None
    ) -> dict:
        """构建 API 请求体"""
        return {
            "video_inputs": [{
                "character": {
                    "type": "avatar",
                    "avatar_id": avatar_id,
                },
                "voice": {
                    "type": "text",
                    "input_text": text,
                    "voice_id": voice_id,
                },
            }],
            "dimension": {
                "width": 1920,
                "height": 1080,
            }
        }

    def _create_video(self, headers: dict, payload: dict) -> str:
        """创建视频任务并返回视频 ID"""
        resp = requests.post(
            f"{self.API_BASE}/videos",
            headers=headers,
            json=payload
        )
        resp.raise_for_status()
        return resp.json()["data"]["video_id"]

    def _poll_status(self, headers: dict, video_id: str) -> str:
        """轮询视频状态，完成后返回下载链接"""
        timeout = self.config.get("timeout", 300)
        start = time.time()

        while time.time() - start < timeout:
            resp = requests.get(
                f"{self.API_BASE}/videos/{video_id}",
                headers=headers
            )
            resp.raise_for_status()
            data = resp.json()["data"]

            status = data.get("status")
            if status == "completed":
                return data["video_url"]
            elif status == "failed":
                raise RuntimeError(f"HeyGen 生成失败: {data.get('error')}")

            time.sleep(5)

        raise TimeoutError(f"HeyGen 生成超时 ({timeout}s)")

    def _download_video(self, url: str, output_path: Path) -> None:
        """下载视频文件"""
        print(f"[HeyGen] 下载视频: {url}")
        resp = requests.get(url, stream=True)
        resp.raise_for_status()

        with open(output_path, "wb") as f:
            for chunk in resp.iter_content(chunk_size=8192):
                f.write(chunk)
