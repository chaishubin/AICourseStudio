"""千问 LLM 与火山引擎 TTS Provider 测试。"""

import base64
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

import pytest

from vidppt.engines.llm.qwen_llm_engine import QwenLLMEngine
from vidppt.engines.tts.volcengine_tts_engine import VolcengineTTSEngine


def test_qwen_requires_api_key(monkeypatch):
    monkeypatch.delenv("DASHSCOPE_API_KEY", raising=False)
    with pytest.raises(ValueError, match="DASHSCOPE_API_KEY"):
        QwenLLMEngine()


def test_qwen_uses_openai_compatible_payload():
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "choices": [{"message": {"content": "生成结果"}}]
    }
    client = Mock()
    client.__enter__ = Mock(return_value=client)
    client.__exit__ = Mock(return_value=False)
    client.post.return_value = response

    with patch("httpx.Client", return_value=client):
        engine = QwenLLMEngine(api_key="test", model="qwen-plus")
        result = engine.summarize("教案内容", system_prompt="生成课程")

    assert result == "生成结果"
    request = client.post.call_args
    assert request.kwargs["headers"]["Authorization"] == "Bearer test"
    assert request.kwargs["json"]["model"] == "qwen-plus"
    assert request.kwargs["json"]["messages"][0]["content"] == "生成课程"


def test_volcengine_requires_credentials(monkeypatch):
    monkeypatch.delenv("VOLCENGINE_TTS_APPID", raising=False)
    monkeypatch.delenv("VOLCENGINE_TTS_ACCESS_TOKEN", raising=False)
    with pytest.raises(ValueError, match="VOLCENGINE_TTS_APPID"):
        VolcengineTTSEngine()


def test_volcengine_payload_and_rate():
    engine = VolcengineTTSEngine(appid="app", access_token="token")
    payload = engine._build_payload(
        "课程讲稿",
        "zh_female_cancan_mars_bigtts",
        "+20%",
        emotion="happy",
    )

    assert payload["app"]["appid"] == "app"
    assert payload["audio"]["speed_ratio"] == 1.2
    assert payload["audio"]["emotion"] == "happy"
    assert payload["request"]["operation"] == "query"
    assert len(engine._split_text("中" * 400)) == 2


@pytest.mark.asyncio
async def test_volcengine_writes_base64_audio(temp_dir):
    audio = b"fake-mp3"
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = {
        "code": 3000,
        "message": "Success",
        "data": base64.b64encode(audio).decode(),
    }
    client = AsyncMock()
    client.__aenter__.return_value = client
    client.__aexit__.return_value = False
    client.post.return_value = response

    output = temp_dir / "audio.mp3"
    with patch("httpx.AsyncClient", return_value=client):
        engine = VolcengineTTSEngine(appid="app", access_token="token")
        await engine.convert_async(
            "课程讲稿", output, "zh_female_cancan_mars_bigtts", "+0%"
        )

    assert output.read_bytes() == audio
    headers = client.post.call_args.kwargs["headers"]
    assert headers["Authorization"] == "Bearer;token"
