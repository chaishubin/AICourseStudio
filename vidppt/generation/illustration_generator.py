"""使用通义万相为课程生成少量、可缓存的内容匹配插图。"""

import os
import time
from pathlib import Path

from loguru import logger

from ..core.course import Course


class DashScopeIllustrationGenerator:
    CREATE_URL = (
        "https://dashscope.aliyuncs.com/api/v1/services/"
        "aigc/text2image/image-synthesis"
    )
    TASK_URL = "https://dashscope.aliyuncs.com/api/v1/tasks/{task_id}"

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "wanx2.1-t2i-turbo",
        timeout: float = 120.0,
        poll_interval: float = 2.0,
    ):
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY")
        self.model = model
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
            f"为中文课程《{course_title}》制作一张与本页主题匹配的横版教学插图。"
            f"本页内容：{subject}。"
            "现代编辑插画风，构图清晰，主体位于画面右侧或中央，"
            "适合放入16:9课程幻灯片，专业、克制、具有真实细节。"
            "不要出现文字、字母、数字、标志、水印或边框。"
        )

    def _generate(self, prompt: str, output_path: Path) -> None:
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
