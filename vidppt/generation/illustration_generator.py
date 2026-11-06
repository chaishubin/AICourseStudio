"""使用通义万相为课程生成少量、可缓存的内容匹配插图。"""

import os
import time
from pathlib import Path

from loguru import logger

from ..core.course import Course


class DashScopeIllustrationGenerator:
    DEFAULT_MODEL = "wan2.7-image"
    CREATE_URL = (
        "https://dashscope.aliyuncs.com/api/v1/services/"
        "aigc/text2image/image-synthesis"
    )
    TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
        poll_interval: float = 2.0,
        base_url: str | None = None,
    ):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model or os.getenv("DASHSCOPE_IMAGE_MODEL") or self.DEFAULT_MODEL
        base = (base_url or os.getenv("DASHSCOPE_IMAGE_BASE_URL") or "https://dashscope.aliyuncs.com").rstrip("/")
        self.CREATE_URL = f"{base}/api/v1/services/aigc/text2image/image-synthesis"
        self.TASK_URL = f"{base}/api/v1/tasks/{{task_id}}"
        self.generation_url = f"{base}/api/v1/services/aigc/multimodal-generation/generation"
        self.timeout = timeout
        self.poll_interval = poll_interval

    def generate_for_course(
        self, course: Course, output_dir: Path, max_images: int = 3
    ) -> list[Path]:
        if not self.api_key:
            logger.warning("未设置 DASHSCOPE_API_KEY，跳过课程插图生成")
            return []

        candidates = self._select_sections(course, max_images)
        illustration_dir = Path(output_dir) / "illustrations"
        illustration_dir.mkdir(parents=True, exist_ok=True)
        generated = []
        for index, section in candidates:
            output = illustration_dir / f"slide-{index}.png"
            try:
                self._generate(self._prompt(course.title, section), output)
                section.metadata["illustration_path"] = str(output)
                generated.append(output)
            except Exception as exc:
                logger.warning(f"第 {index} 页插图生成失败，继续生成纯版式 PPT: {exc}")
        return generated

    @staticmethod
    def _select_sections(course: Course, max_images: int):
        if not course.sections or max_images <= 0:
            return []
        selected = [(1, course.sections[0])]
        preferred = [
            (index, section)
            for index, section in enumerate(course.sections[1:], 2)
            if section.layout == "section" or section.image_prompt
        ]
        remaining = [
            (index, section)
            for index, section in enumerate(course.sections[1:], 2)
            if (index, section) not in preferred and section.layout != "summary"
        ]
        for item in preferred + remaining:
            if len(selected) >= max_images:
                break
            selected.append(item)
        return selected

    @staticmethod
    def _prompt(course_title: str, section) -> str:
        subject = section.image_prompt or "；".join(
            [section.title, *section.bullets[:3]]
        )
        return (
            "生成一张纯无字横版教学插图，只画场景、人物、物体、流程意象或抽象图形。"
            "画面中绝对禁止出现任何文字、标题、标签、字母、拼音、数字、符号、Logo、水印、印章或边框，"
            "也不要生成海报、封面、信息图、看板、屏幕文字、书页文字、路牌文字或图表文字。"
            f"课程主题：{course_title}。本页语义：{subject}。"
            "现代编辑插画风，构图清晰，主体位于画面右侧或中央，"
            "适合放入16:9课程幻灯片，专业、克制、具有真实细节。"
            "最终图片必须保持无任何可读或不可读字符，所有说明文字由 PPT 文本框另行排版。"
        )

    def _generate(self, prompt: str, output_path: Path) -> None:
        if self.model.startswith(("wan2.7-image", "wan2.6-t2i")):
            self._generate_multimodal(prompt, output_path)
        else:
            self._generate_legacy(prompt, output_path)

    def _generate_multimodal(self, prompt: str, output_path: Path) -> None:
        """Wan 2.6/2.7 use messages and return image content, not legacy task results."""
        import httpx

        payload = {
            "model": self.model,
            "input": {"messages": [{"role": "user", "content": [{"text": prompt}]}]},
            "parameters": {"size": "1728*972", "n": 1, "watermark": False},
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(
                self.generation_url,
                headers={"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"},
                json=payload,
            )
            response.raise_for_status()
            result = response.json()
            image_url = next((
                item["image"]
                for choice in result.get("output", {}).get("choices", [])
                for item in choice.get("message", {}).get("content", [])
                if item.get("image")
            ), None)
            if not image_url:
                raise RuntimeError(f"万相未返回图片: {result.get('code', '')} {result.get('message', '')}")
            image_response = client.get(image_url)
            image_response.raise_for_status()
            if not image_response.content:
                raise RuntimeError("万相返回了空图片")
            output_path.write_bytes(image_response.content)

    def _generate_legacy(self, prompt: str, output_path: Path) -> None:
        import httpx

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-DashScope-Async": "enable",
        }
        payload = {
            "model": self.model,
            "input": {"prompt": prompt},
            "parameters": {
                "style": "<auto>",
                "size": "1280*720",
                "n": 1,
            },
        }
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(self.CREATE_URL, headers=headers, json=payload)
            response.raise_for_status()
            result = response.json()
            task_id = result.get("output", {}).get("task_id")
            if not task_id:
                raise RuntimeError(f"万相未返回任务 ID: {result}")

            deadline = time.monotonic() + self.timeout
            while time.monotonic() < deadline:
                task_response = client.get(
                    self.TASK_URL.format(task_id=task_id),
                    headers={"Authorization": f"Bearer {self.api_key}"},
                )
                task_response.raise_for_status()
                task = task_response.json()
                status = task.get("output", {}).get("task_status")
                if status == "SUCCEEDED":
                    results = task["output"].get("results") or []
                    image_url = next(
                        (item.get("url") for item in results if item.get("url")),
                        None,
                    )
                    if not image_url:
                        raise RuntimeError(f"万相任务成功但没有图片: {task}")
                    image_response = client.get(image_url)
                    image_response.raise_for_status()
                    output_path.write_bytes(image_response.content)
                    return
                if status in {"FAILED", "CANCELED", "UNKNOWN"}:
                    raise RuntimeError(
                        task.get("output", {}).get("message")
                        or f"万相任务状态: {status}"
                    )
                time.sleep(self.poll_interval)
        raise TimeoutError("等待万相生成插图超时")
