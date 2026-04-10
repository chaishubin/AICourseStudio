"""
音频缓存系统 - 避免重复的 TTS 转换
"""

import hashlib
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime, timedelta

from loguru import logger


class AudioCacheManager:
    """管理音频文件缓存的类"""

    DEFAULT_CACHE_DIR = Path.home() / ".cache" / "vidppt" / "audio"
    DEFAULT_CACHE_EXPIRY_DAYS = 30

    def __init__(
        self,
        cache_dir: Optional[Path] = None,
        enable_cache: bool = True,
        expiry_days: int = DEFAULT_CACHE_EXPIRY_DAYS,
    ):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录路径，默认为 ~/.cache/vidppt/audio
            enable_cache: 是否启用缓存
            expiry_days: 缓存过期天数
        """
        self.cache_dir = cache_dir or self.DEFAULT_CACHE_DIR
        self.enable_cache = enable_cache
        self.expiry_days = expiry_days
        self.metadata_file = self.cache_dir / "cache_metadata.json"

        # 创建缓存目录
        if self.enable_cache:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            logger.debug(f"使用音频缓存目录: {self.cache_dir}")

    def _generate_cache_key(
        self,
        text: str,
        tts_engine: str,
        voice: str,
        rate: float,
        **kwargs,
    ) -> str:
        """
        基于文本和 TTS 参数生成缓存键

        Args:
            text: 待转换的文本
            tts_engine: TTS 引擎名称 (e.g., 'edge-tts', 'minimax')
            voice: 语音名称
            rate: 语速
            **kwargs: 其他 TTS 参数 (e.g., emotion, model)

        Returns:
            缓存键 (SHA256 哈希值)
        """
        # 构建缓存键的基础字符串
        cache_key_data = {
            "text": text.strip(),
            "tts_engine": tts_engine,
            "voice": voice,
            "rate": rate,
            **kwargs,
        }

        # 转换为 JSON 字符串以保证一致性
        cache_key_str = json.dumps(cache_key_data, sort_keys=True, ensure_ascii=False)

        # 生成 SHA256 哈希值
        cache_key = hashlib.sha256(cache_key_str.encode("utf-8")).hexdigest()
        return cache_key

    def _get_cache_file_path(self, cache_key: str) -> Path:
        """
        获取缓存文件路径

        Args:
            cache_key: 缓存键

        Returns:
            缓存文件路径
        """
        return self.cache_dir / f"{cache_key}.mp3"

    def _load_metadata(self) -> Dict[str, Any]:
        """加载缓存元数据"""
        if not self.metadata_file.exists():
            return {}

        try:
            with open(self.metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"无法读取缓存元数据: {e}")
            return {}

    def _save_metadata(self, metadata: Dict[str, Any]) -> None:
        """保存缓存元数据"""
        try:
            self.metadata_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.metadata_file, "w", encoding="utf-8") as f:
                json.dump(metadata, f, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.warning(f"无法保存缓存元数据: {e}")

    def _is_cache_expired(self, cache_timestamp: str) -> bool:
        """
        检查缓存是否已过期

        Args:
            cache_timestamp: 缓存的时间戳字符串

        Returns:
            True 如果已过期，False 否则
        """
        try:
            cache_time = datetime.fromisoformat(cache_timestamp)
            expiry_time = cache_time + timedelta(days=self.expiry_days)
            is_expired = datetime.now() > expiry_time
            return is_expired
        except (ValueError, TypeError):
            return True

    def get(
        self,
        text: str,
        tts_engine: str,
        voice: str,
        rate: float,
        **kwargs,
    ) -> Optional[Path]:
        """
        从缓存获取音频文件

        Args:
            text: 待转换的文本
            tts_engine: TTS 引擎名称
            voice: 语音名称
            rate: 语速
            **kwargs: 其他 TTS 参数

        Returns:
            缓存文件路径，如果不存在或已过期则返回 None
        """
        if not self.enable_cache:
            return None

        cache_key = self._generate_cache_key(text, tts_engine, voice, rate, **kwargs)
        cache_file = self._get_cache_file_path(cache_key)

        # 检查文件是否存在
        if not cache_file.exists():
            logger.debug(f"缓存未命中: {cache_key}")
            return None

        # 检查元数据和过期时间
        metadata = self._load_metadata()
        if cache_key in metadata:
            if self._is_cache_expired(metadata[cache_key]["timestamp"]):
                logger.debug(f"缓存已过期: {cache_key}")
                cache_file.unlink()
                return None

            logger.debug(f"缓存命中: {cache_key}")
            return cache_file

        return None

    def put(
        self,
        audio_path: Path,
        text: str,
        tts_engine: str,
        voice: str,
        rate: float,
        **kwargs,
    ) -> None:
        """
        将音频文件保存到缓存

        Args:
            audio_path: 音频文件路径
            text: 待转换的文本
            tts_engine: TTS 引擎名称
            voice: 语音名称
            rate: 语速
            **kwargs: 其他 TTS 参数
        """
        if not self.enable_cache or not audio_path.exists():
            return

        cache_key = self._generate_cache_key(text, tts_engine, voice, rate, **kwargs)
        cache_file = self._get_cache_file_path(cache_key)

        try:
            # 复制文件到缓存目录
            import shutil

            shutil.copy2(audio_path, cache_file)

            # 更新元数据
            metadata = self._load_metadata()
            metadata[cache_key] = {
                "timestamp": datetime.now().isoformat(),
                "text_length": len(text),
                "tts_engine": tts_engine,
                "voice": voice,
                "rate": rate,
            }
            self._save_metadata(metadata)

            logger.debug(f"缓存已保存: {cache_key} -> {cache_file}")
        except Exception as e:
            logger.warning(f"无法保存缓存: {e}")

    def clear(self, older_than_days: Optional[int] = None) -> int:
        """
        清理缓存

        Args:
            older_than_days: 清理指定天数之前的缓存。如果为 None，清理所有缓存

        Returns:
            清理的文件数
        """
        if not self.enable_cache or not self.cache_dir.exists():
            return 0

        count = 0
        metadata = self._load_metadata()
        cutoff_time = (
            datetime.now() - timedelta(days=older_than_days)
            if older_than_days
            else datetime.now() + timedelta(days=999999)  # 删除所有
        )

        for cache_key, info in list(metadata.items()):
            cache_file = self._get_cache_file_path(cache_key)
            try:
                cache_timestamp = datetime.fromisoformat(info["timestamp"])
                if cache_timestamp < cutoff_time:
                    if cache_file.exists():
                        cache_file.unlink()
                        count += 1
                    del metadata[cache_key]
            except Exception as e:
                logger.warning(f"无法清理缓存 {cache_key}: {e}")

        if count > 0:
            self._save_metadata(metadata)
            logger.info(f"清理了 {count} 个缓存文件")

        return count

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        if not self.enable_cache or not self.cache_dir.exists():
            return {"enabled": False}

        metadata = self._load_metadata()
        total_size = 0
        cache_count = 0

        for cache_file in self.cache_dir.glob("*.mp3"):
            cache_count += 1
            total_size += cache_file.stat().st_size

        return {
            "enabled": True,
            "cache_dir": str(self.cache_dir),
            "cache_count": cache_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "metadata_entries": len(metadata),
            "expiry_days": self.expiry_days,
        }
