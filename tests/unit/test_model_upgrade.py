"""Offline contract checks for the upgraded model requests and responses."""

import base64
import json

import httpx
import pytest

from vidppt.engines.llm.deepseek_llm_engine import DeepSeekLLMEngine
from vidppt.engines.llm.qwen_llm_engine import QwenLLMEngine
from vidppt.engines.tts.volcengine_tts_engine import VolcengineTTSEngine
from vidppt.generation.illustration_generator import DashScopeIllustrationGenerator
from vidppt.review.course_reviewer import CourseReviewer


@pytest.fixture(autouse=True)
def isolate_model_settings(monkeypatch):
    for name in (
        "QWEN_MODEL", "QWEN_API_URL", "DASHSCOPE_IMAGE_MODEL", "DASHSCOPE_IMAGE_BASE_URL",
        "VOLCENGINE_TTS_API_KEY", "VOLCENGINE_TTS_API_URL", "VOLCENGINE_TTS_API_VERSION",
        "VOLCENGINE_TTS_RESOURCE_ID", "COURSE_REVIEW_INPUT_USD_PER_MILLION",
        "COURSE_REVIEW_OUTPUT_USD_PER_MILLION",
    ):
        monkeypatch.delenv(name, raising=False)


def mock_sync_client(monkeypatch, handler):
    client_type = httpx.Client
    monkeypatch.setattr(httpx, "Client", lambda **kw: client_type(transport=httpx.MockTransport(handler), **kw))


def test_qwen_new_default_config_precedence_and_explicit_thinking(monkeypatch):
    assert QwenLLMEngine(api_key="test").model == "qwen3.7-plus"
    monkeypatch.setenv("QWEN_MODEL", "qwen-plus")
    monkeypatch.setenv("QWEN_API_URL", "https://example.test/v1")
    assert QwenLLMEngine(api_key="test").model == "qwen-plus"
    engine = QwenLLMEngine(api_key="test", model="qwen3.7-plus")

    def handler(request):
        payload = json.loads(request.content)
        assert str(request.url) == "https://example.test/v1/chat/completions"
        assert payload["model"] == "qwen3.7-plus"
        assert payload["enable_thinking"] is False
        return httpx.Response(200, json={"choices": [{"message": {"content": "讲稿"}, "finish_reason": "stop"}]})

    mock_sync_client(monkeypatch, handler)
    assert engine.summarize("原文") == "讲稿"


def test_qwen_rejects_truncated_script(monkeypatch):
    mock_sync_client(monkeypatch, lambda _: httpx.Response(200, json={
        "choices": [{"finish_reason": "length", "message": {"content": "不完整讲稿"}}],
    }))
    with pytest.raises(ValueError, match="截断"):
        QwenLLMEngine(api_key="test").summarize("原文")


@pytest.mark.parametrize("model", ["wan2.7-image", "wan2.7-image-pro", "wan2.6-t2i"])
def test_modern_illustration_uses_sync_messages(monkeypatch, tmp_path, model):
    def handler(request):
        if request.method == "POST":
            assert str(request.url) == "https://images.test/api/v1/services/aigc/multimodal-generation/generation"
            assert "X-DashScope-Async" not in request.headers
            payload = json.loads(request.content)
            assert payload["model"] == model
            assert payload["input"]["messages"][0]["content"] == [{"text": "横版无字插图"}]
            assert payload["parameters"]["n"] == 1
            width, height = map(int, payload["parameters"]["size"].split("*"))
            assert width * 9 == height * 16
            assert 1280 ** 2 <= width * height <= 1440 ** 2
            return httpx.Response(200, json={"output": {"choices": [{"message": {
                "content": [{"image": "https://images.test/result.png"}],
            }}]}})
        return httpx.Response(200, content=b"image-result")

    mock_sync_client(monkeypatch, handler)
    output = tmp_path / "image.png"
    DashScopeIllustrationGenerator(api_key="test", model=model, base_url="https://images.test")._generate("横版无字插图", output)
    assert output.read_bytes() == b"image-result"


def test_legacy_illustration_can_still_be_selected(monkeypatch, tmp_path):
    monkeypatch.setenv("DASHSCOPE_IMAGE_MODEL", "wanx2.1-t2i-turbo")

    def handler(request):
        if request.method == "POST":
            assert request.url.path.endswith("text2image/image-synthesis")
            assert request.headers["X-DashScope-Async"] == "enable"
            assert json.loads(request.content)["input"] == {"prompt": "旧版插图"}
            return httpx.Response(200, json={"output": {"task_id": "test-task"}})
        if request.url.path.endswith("test-task"):
            return httpx.Response(200, json={"output": {"task_status": "SUCCEEDED", "results": [{"url": "https://images.test/result.png"}]}})
        return httpx.Response(200, content=b"legacy-result")

    mock_sync_client(monkeypatch, handler)
    output = tmp_path / "image.png"
    DashScopeIllustrationGenerator(api_key="test")._generate("旧版插图", output)
    assert output.read_bytes() == b"legacy-result"


@pytest.mark.asyncio
@pytest.mark.parametrize("api_key", [None, "new-api-key"])
async def test_volcengine_v3_audio_and_auth(monkeypatch, tmp_path, api_key):
    def handler(request):
        assert str(request.url) == VolcengineTTSEngine.V3_API_URL
        assert request.headers["X-Api-Resource-Id"] == "seed-tts-2.0"
        if api_key:
            assert request.headers["X-Api-Key"] == api_key
            assert "X-Api-Access-Key" not in request.headers
        else:
            assert request.headers["X-Api-App-Id"] == "app"
            assert request.headers["X-Api-Access-Key"] == "token"
        payload = json.loads(request.content)["req_params"]
        assert payload["speaker"] == "zh_female_vv_uranus_bigtts"
        assert payload["audio_params"]["speech_rate"] == -8
        assert payload["audio_params"]["sample_rate"] == 24000
        return httpx.Response(200, text='\n'.join([
            json.dumps({"code": 0, "data": base64.b64encode(b"first-").decode()}),
            json.dumps({"code": 0, "data": base64.b64encode(b"second").decode()}),
            json.dumps({"code": 20000000}),
        ]))

    client_type = httpx.AsyncClient
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client_type(transport=httpx.MockTransport(handler), **kw))
    engine = VolcengineTTSEngine(appid="app", access_token="token", api_key=api_key)
    output = tmp_path / "audio.mp3"
    await engine.convert_async("测试讲稿", output, "zh_female_vv_uranus_bigtts", "-8%")
    assert output.read_bytes() == b"first-second"


@pytest.mark.asyncio
@pytest.mark.parametrize("events", [
    [{"code": 0, "data": "YXVkaW8="}],  # Missing completion marker.
    [{"code": 20000000}],  # Completed without audio.
    [{"code": 45000000, "message": "resource denied"}],
])
async def test_volcengine_v3_rejects_partial_or_failed_audio(monkeypatch, tmp_path, events):
    client_type = httpx.AsyncClient
    transport = httpx.MockTransport(lambda _: httpx.Response(200, text='\n'.join(map(json.dumps, events))))
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kw: client_type(transport=transport, **kw))
    engine = VolcengineTTSEngine(appid="app", access_token="token")
    output = tmp_path / "audio.mp3"
    with pytest.raises((ValueError, RuntimeError)):
        await engine.convert_async("测试讲稿", output, "zh_female_vv_uranus_bigtts", "+0%")
    assert not output.exists()


def test_volcengine_old_voice_and_cache_protocol_identity(monkeypatch):
    voice = "zh_female_cancan_mars_bigtts"
    legacy = VolcengineTTSEngine.cache_identity(voice)
    assert legacy["api_version"] == "v1"
    monkeypatch.setenv("VOLCENGINE_TTS_API_VERSION", "v3")
    current = VolcengineTTSEngine.cache_identity(voice)
    assert current != legacy
    assert current["api_version"] == "v3"
    assert current["resource_id"] == "seed-tts-1.0"
    assert "api_key" not in current


def test_deepseek_json_request_retains_usage_and_disables_thinking(monkeypatch):
    def handler(request):
        payload = json.loads(request.content)
        assert payload["thinking"] == {"type": "disabled"}
        assert payload["response_format"] == {"type": "json_object"}
        return httpx.Response(200, json={"choices": [{"message": {"content": "{}"}}],
                                         "usage": {"prompt_tokens": 120, "completion_tokens": 60}})

    mock_sync_client(monkeypatch, handler)
    engine = DeepSeekLLMEngine(api_key="test")
    assert engine.summarize("输出 JSON", response_format={"type": "json_object"}) == "{}"
    assert engine.last_usage == {"prompt_tokens": 120, "completion_tokens": 60}


def test_review_cost_requires_model_price_and_prefers_real_usage(monkeypatch):
    class Engine:
        last_usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}

    reviewer = CourseReviewer(provider="deepseek", engine=Engine())
    assert reviewer.estimate_cost_cny("a", "b") is None
    monkeypatch.setenv("COURSE_REVIEW_INPUT_USD_PER_MILLION", "1")
    monkeypatch.setenv("COURSE_REVIEW_OUTPUT_USD_PER_MILLION", "2")
    assert reviewer.estimate_cost_cny("a", "b") == 21.6


def test_openai_review_standard_price_uses_real_usage():
    class Engine:
        last_usage = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}

    reviewer = CourseReviewer(provider="openai", model="gpt-5.4-mini", engine=Engine())
    assert reviewer.estimate_cost_cny("a", "b") == 37.8


def test_empty_compose_price_settings_leave_cost_unknown(monkeypatch):
    monkeypatch.setenv("COURSE_REVIEW_INPUT_USD_PER_MILLION", "")
    monkeypatch.setenv("COURSE_REVIEW_OUTPUT_USD_PER_MILLION", "")
    assert CourseReviewer(provider="deepseek", engine=object()).estimate_cost_cny("a", "b") is None
