"""Pytest 配置和共享 fixtures"""

import pytest
from pathlib import Path
import tempfile
import shutil


@pytest.fixture(autouse=True)
def authenticated_web_tests(monkeypatch, tmp_path):
    """隔离 Web 测试的登录与持久化状态，避免污染本地生产任务。"""
    try:
        import web.app as app_module
        from web.task_store import TaskStore
    except ImportError:
        return
    monkeypatch.setitem(app_module.app.config, "LOGIN_DISABLED", True)
    state_file = tmp_path / "outputs" / "state.json"
    monkeypatch.setattr(app_module, "STATE_FILE", state_file)
    monkeypatch.setattr(app_module, "DEFAULT_STATE_FILE", state_file)
    monkeypatch.setattr(
        app_module,
        "task_store",
        TaskStore(tmp_path / "outputs" / "tasks.db"),
    )


@pytest.fixture
def temp_dir():
    """创建临时目录"""
    tmp = tempfile.mkdtemp()
    yield Path(tmp)
    shutil.rmtree(tmp)


@pytest.fixture
def sample_text():
    """示例文本"""
    return "这是一段测试文本，用于TTS转换。"


@pytest.fixture
def sample_config(temp_dir):
    """示例配置"""
    from vidppt.core.models import ProcessConfig

    return ProcessConfig(
        input_path=temp_dir / "test.pptx",
        output_dir=temp_dir / "output",
        save_intermediate=True,
        enable_tts=True,
        enable_video=True,
    )


@pytest.fixture
def mock_page_content():
    """模拟页面内容"""
    from vidppt.core.models import PageContent
    from pathlib import Path

    return PageContent(
        page_number=1,
        text="这是第一页的内容",
        images=[Path("image1.png")],
        slide_image=Path("slide1.png"),
        audio=Path("audio1.mp3"),
        metadata={"title": "测试页面"},
    )


@pytest.fixture
def mock_document_content(mock_page_content):
    """模拟文档内容"""
    from vidppt.core.models import DocumentContent, PageContent
    from pathlib import Path

    pages = [
        mock_page_content,
        PageContent(
            page_number=2,
            text="这是第二页的内容",
            images=[],
            slide_image=Path("slide2.png"),
        ),
    ]

    return DocumentContent(
        pages=pages, metadata={"author": "测试", "title": "测试文档"}
    )
