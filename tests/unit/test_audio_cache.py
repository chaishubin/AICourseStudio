"""
音频缓存系统的单元测试
"""

import hashlib
import json
import tempfile
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

import pytest

from vidppt.utils.audio_cache import AudioCacheManager


class TestAudioCacheKeyGeneration:
    """测试缓存键生成"""

    def test_generate_cache_key_basic(self):
        """测试基本缓存键生成"""
        cache = AudioCacheManager(enable_cache=False)
        key1 = cache._generate_cache_key(
            text="Hello World",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        key2 = cache._generate_cache_key(
            text="Hello World",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        assert key1 == key2
        assert len(key1) == 64  # SHA256 哈希值长度

    def test_generate_cache_key_different_texts(self):
        """测试不同文本生成不同缓存键"""
        cache = AudioCacheManager(enable_cache=False)
        key1 = cache._generate_cache_key(
            text="Hello",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        key2 = cache._generate_cache_key(
            text="World",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        assert key1 != key2

    def test_generate_cache_key_different_voices(self):
        """测试不同声音生成不同缓存键"""
        cache = AudioCacheManager(enable_cache=False)
        key1 = cache._generate_cache_key(
            text="Hello",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        key2 = cache._generate_cache_key(
            text="Hello",
            tts_engine="edge-tts",
            voice="en-US-GuyNeural",
            rate="+0%",
        )
        assert key1 != key2

    def test_generate_cache_key_with_extra_params(self):
        """测试包含额外参数的缓存键生成"""
        cache = AudioCacheManager(enable_cache=False)
        key1 = cache._generate_cache_key(
            text="Hello",
            tts_engine="minimax",
            voice="Female",
            rate="+0%",
            emotion="happy",
            model="speech-2.8-hd",
        )
        key2 = cache._generate_cache_key(
            text="Hello",
            tts_engine="minimax",
            voice="Female",
            rate="+0%",
            emotion="happy",
            model="speech-2.8-hd",
        )
        assert key1 == key2

    def test_cache_key_strips_whitespace(self):
        """测试缓存键生成时去除空格"""
        cache = AudioCacheManager(enable_cache=False)
        key1 = cache._generate_cache_key(
            text="  Hello World  ",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        key2 = cache._generate_cache_key(
            text="Hello World",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        assert key1 == key2


class TestAudioCachePutGet:
    """测试缓存的读写"""

    @pytest.fixture
    def temp_cache_dir(self):
        """创建临时缓存目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """创建缓存管理器实例"""
        return AudioCacheManager(
            cache_dir=temp_cache_dir,
            enable_cache=True,
            expiry_days=30,
        )

    @pytest.fixture
    def temp_audio_file(self):
        """创建临时音频文件"""
        with tempfile.NamedTemporaryFile(suffix=".mp3", delete=False) as f:
            f.write(b"fake mp3 data")
            return Path(f.name)

    def test_put_and_get_cache(self, cache_manager, temp_audio_file):
        """测试缓存保存和获取"""
        # 保存到缓存
        cache_manager.put(
            audio_path=temp_audio_file,
            text="Test audio",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )

        # 从缓存获取
        cached_path = cache_manager.get(
            text="Test audio",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )

        assert cached_path is not None
        assert cached_path.exists()
        assert cached_path.suffix == ".mp3"

    def test_cache_miss_returns_none(self, cache_manager):
        """测试缓存未命中返回 None"""
        result = cache_manager.get(
            text="Non-existent",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        assert result is None

    def test_cache_disabled_returns_none(self, temp_cache_dir, temp_audio_file):
        """测试禁用缓存时返回 None"""
        cache = AudioCacheManager(cache_dir=temp_cache_dir, enable_cache=False)
        cache.put(
            audio_path=temp_audio_file,
            text="Test",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        result = cache.get(
            text="Test",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        assert result is None

    def test_metadata_saved_correctly(self, cache_manager, temp_audio_file):
        """测试元数据正确保存"""
        cache_manager.put(
            audio_path=temp_audio_file,
            text="Test audio",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )

        metadata = cache_manager._load_metadata()
        assert len(metadata) > 0

        # 找到对应的键
        key = cache_manager._generate_cache_key(
            text="Test audio",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        assert key in metadata
        assert metadata[key]["tts_engine"] == "edge-tts"
        assert metadata[key]["voice"] == "en-US-AriaNeural"


class TestAudioCacheExpiry:
    """测试缓存过期机制"""

    @pytest.fixture
    def temp_cache_dir(self):
        """创建临时缓存目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """创建缓存管理器实例"""
        return AudioCacheManager(
            cache_dir=temp_cache_dir,
            enable_cache=True,
            expiry_days=1,
        )

    def test_cache_expiry_check(self, cache_manager):
        """测试缓存过期检查"""
        now = datetime.now().isoformat()
        past = (datetime.now() - timedelta(days=2)).isoformat()
        future = (datetime.now() + timedelta(days=2)).isoformat()

        assert not cache_manager._is_cache_expired(future)
        assert cache_manager._is_cache_expired(past)

    def test_expired_cache_not_returned(self, cache_manager, temp_cache_dir):
        """测试过期缓存不被返回"""
        # 创建一个过期的缓存条目
        key = cache_manager._generate_cache_key(
            text="Old audio",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        cache_file = cache_manager._get_cache_file_path(key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"fake mp3 data")

        # 添加过期的元数据
        metadata = {
            key: {
                "timestamp": (datetime.now() - timedelta(days=2)).isoformat(),
                "text_length": 9,
                "tts_engine": "edge-tts",
                "voice": "en-US-AriaNeural",
                "rate": "+0%",
            }
        }
        cache_manager._save_metadata(metadata)

        # 尝试获取应该返回 None
        result = cache_manager.get(
            text="Old audio",
            tts_engine="edge-tts",
            voice="en-US-AriaNeural",
            rate="+0%",
        )
        assert result is None


class TestAudioCacheClear:
    """测试缓存清理"""

    @pytest.fixture
    def temp_cache_dir(self):
        """创建临时缓存目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """创建缓存管理器实例"""
        return AudioCacheManager(
            cache_dir=temp_cache_dir,
            enable_cache=True,
            expiry_days=30,
        )

    def test_clear_all_cache(self, cache_manager, temp_cache_dir):
        """测试清理所有缓存"""
        # 创建多个缓存文件
        for i in range(3):
            key = hashlib.sha256(f"test{i}".encode()).hexdigest()
            cache_file = cache_manager._get_cache_file_path(key)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(b"fake mp3 data")

        # 添加元数据
        metadata = {}
        for i in range(3):
            key = hashlib.sha256(f"test{i}".encode()).hexdigest()
            metadata[key] = {
                "timestamp": datetime.now().isoformat(),
                "text_length": 5,
                "tts_engine": "edge-tts",
                "voice": "en-US-AriaNeural",
                "rate": "+0%",
            }
        cache_manager._save_metadata(metadata)

        # 清理所有缓存
        count = cache_manager.clear(older_than_days=None)
        assert count == 3

        # 确认文件已删除
        assert len(list(cache_manager.cache_dir.glob("*.mp3"))) == 0

    def test_clear_old_cache_only(self, cache_manager):
        """测试只清理旧缓存"""
        # 创建新旧缓存
        old_key = hashlib.sha256(b"old").hexdigest()
        new_key = hashlib.sha256(b"new").hexdigest()

        for key in [old_key, new_key]:
            cache_file = cache_manager._get_cache_file_path(key)
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_bytes(b"fake mp3 data")

        # 添加元数据
        metadata = {
            old_key: {
                "timestamp": (datetime.now() - timedelta(days=10)).isoformat(),
                "text_length": 3,
                "tts_engine": "edge-tts",
                "voice": "en-US-AriaNeural",
                "rate": "+0%",
            },
            new_key: {
                "timestamp": datetime.now().isoformat(),
                "text_length": 3,
                "tts_engine": "edge-tts",
                "voice": "en-US-AriaNeural",
                "rate": "+0%",
            },
        }
        cache_manager._save_metadata(metadata)

        # 清理超过5天的缓存
        count = cache_manager.clear(older_than_days=5)
        assert count == 1

        # 新缓存应该还存在
        new_cache = cache_manager._get_cache_file_path(new_key)
        assert new_cache.exists()


class TestAudioCacheStats:
    """测试缓存统计"""

    @pytest.fixture
    def temp_cache_dir(self):
        """创建临时缓存目录"""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield Path(tmpdir)

    @pytest.fixture
    def cache_manager(self, temp_cache_dir):
        """创建缓存管理器实例"""
        return AudioCacheManager(
            cache_dir=temp_cache_dir,
            enable_cache=True,
            expiry_days=30,
        )

    def test_cache_stats_disabled_cache(self, temp_cache_dir):
        """测试禁用缓存时的统计"""
        cache = AudioCacheManager(cache_dir=temp_cache_dir, enable_cache=False)
        stats = cache.get_cache_stats()
        assert stats["enabled"] is False

    def test_cache_stats_with_files(self, cache_manager):
        """测试有缓存文件时的统计"""
        # 创建缓存文件
        key = hashlib.sha256(b"test").hexdigest()
        cache_file = cache_manager._get_cache_file_path(key)
        cache_file.parent.mkdir(parents=True, exist_ok=True)
        cache_file.write_bytes(b"x" * 1024 * 100)  # 100 KB

        # 添加元数据
        metadata = {
            key: {
                "timestamp": datetime.now().isoformat(),
                "text_length": 4,
                "tts_engine": "edge-tts",
                "voice": "en-US-AriaNeural",
                "rate": "+0%",
            }
        }
        cache_manager._save_metadata(metadata)

        stats = cache_manager.get_cache_stats()
        assert stats["enabled"] is True
        assert stats["cache_count"] == 1
        assert stats["total_size_mb"] > 0
        assert stats["metadata_entries"] == 1
