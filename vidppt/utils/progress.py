"""
处理进度跟踪系统
"""

import sys
import time
from datetime import datetime, timedelta
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from loguru import logger


class ProcessStage(Enum):
    """处理阶段"""

    INIT = "初始化"
    EXTRACT = "提取内容"
    TTS = "文字转语音"
    VIDEO = "合成视频"
    CLEANUP = "清理"
    COMPLETE = "完成"


@dataclass
class StageProgress:
    """单个阶段的进度"""

    stage: ProcessStage
    current: int = 0
    total: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    status: str = "pending"  # pending, running, completed, failed

    @property
    def elapsed_seconds(self) -> float:
        """已用时间（秒）"""
        if not self.start_time:
            return 0
        end = self.end_time or datetime.now()
        return (end - self.start_time).total_seconds()

    @property
    def estimated_remaining_seconds(self) -> float:
        """估计剩余时间（秒）"""
        if self.current == 0:
            return 0
        elapsed = self.elapsed_seconds
        avg_time_per_item = elapsed / self.current
        remaining_items = self.total - self.current
        return avg_time_per_item * remaining_items

    @property
    def estimated_total_seconds(self) -> float:
        """估计总时间（秒）"""
        return self.elapsed_seconds + self.estimated_remaining_seconds

    @property
    def progress_percentage(self) -> float:
        """进度百分比 (0-100)"""
        if self.total == 0:
            return 0
        return min(100, (self.current / self.total) * 100)

    def start(self):
        """开始阶段"""
        self.start_time = datetime.now()
        self.status = "running"
        logger.info(f"开始 {self.stage.value}...")

    def update(self, current: int, total: Optional[int] = None):
        """更新进度"""
        if not self.start_time:
            self.start()
        self.current = current
        if total:
            self.total = total

    def complete(self):
        """完成阶段"""
        self.end_time = datetime.now()
        self.status = "completed"
        # 确保进度条换行后再输出完成信息
        sys.stdout.write("\n")
        sys.stdout.flush()
        logger.info(f"{self.stage.value}完成 (耗时: {self.elapsed_seconds:.1f}秒)")

    def fail(self, error: str = ""):
        """标记为失败"""
        self.end_time = datetime.now()
        self.status = "failed"
        logger.error(f"{self.stage.value}失败: {error}")


class ProgressTracker:
    """处理进度跟踪器"""

    def __init__(self, total_pages: int, enable_progress: bool = True):
        """
        初始化进度跟踪器

        Args:
            total_pages: 总页数
            enable_progress: 是否启用进度显示
        """
        self.total_pages = total_pages
        self.enable_progress = enable_progress
        self.stages = {}
        self.overall_start_time = datetime.now()
        self._last_progress_update = 0  # 上次进度更新的页数

        # 初始化各个阶段
        for stage in ProcessStage:
            self.stages[stage] = StageProgress(stage=stage, total=total_pages)

        logger.info(f"开始处理 {total_pages} 页文档")

    def start_stage(self, stage: ProcessStage) -> StageProgress:
        """开始一个处理阶段"""
        progress = self.stages[stage]
        progress.start()
        return progress

    def get_stage_progress(self, stage: ProcessStage) -> StageProgress:
        """获取阶段进度"""
        return self.stages[stage]

    def update_stage(
        self, stage: ProcessStage, current: int, total: Optional[int] = None
    ):
        """更新阶段进度"""
        progress = self.stages[stage]
        if progress.status == "pending":
            progress.start()
        progress.update(current, total)
        self._log_progress(progress)

    def update_stage_incremental(
        self, stage: ProcessStage, current: int, total: Optional[int] = None,
        force_display: bool = False
    ):
        """
        增量更新阶段进度，避免频繁输出

        参数:
            stage: 处理阶段
            current: 当前值
            total: 总值（可选）
            force_display: 强制显示进度（用于关键时刻）
        """
        progress = self.stages[stage]
        if progress.status == "pending":
            progress.start()

        # 检查是否有实际进展
        if current == self._last_progress_update and not force_display:
            return

        self._last_progress_update = current
        progress.update(current, total)

        # 根据总数决定显示频率
        display_step = max(1, (progress.total or 10) // 10)  # 每10%显示一次

        if force_display or current == 1 or current == progress.total or current % display_step == 0:
            self._log_progress(progress)

    def complete_stage(self, stage: ProcessStage):
        """完成一个阶段"""
        progress = self.stages[stage]
        progress.complete()

    def fail_stage(self, stage: ProcessStage, error: str = ""):
        """标记阶段为失败"""
        progress = self.stages[stage]
        progress.fail(error)

    def _log_progress(self, progress: StageProgress):
        """记录进度（如果启用）"""
        if not self.enable_progress:
            return

        if progress.total > 0:
            percentage = progress.progress_percentage
            bar_length = 40
            filled = int(bar_length * progress.current / progress.total)
            bar = "█" * filled + "░" * (bar_length - filled)

            # 计算剩余时间
            remaining = progress.estimated_remaining_seconds
            eta_str = (
                f"ETA: {int(remaining // 60):02d}:{int(remaining % 60):02d}"
                if remaining > 0
                else "完成"
            )

            # 直接输出进度条到终端（覆盖上一行）
            msg = (
                f"\r{progress.stage.value} [{bar}] "
                f"{progress.current}/{progress.total} "
                f"({percentage:.0f}%) - {eta_str}"
            )
            sys.stdout.write(msg)
            sys.stdout.flush()

            # 如果完成，换行
            if progress.current >= progress.total:
                sys.stdout.write("\n")
                sys.stdout.flush()

    def get_overall_progress(self) -> dict:
        """获取整体进度信息"""
        overall_elapsed = (datetime.now() - self.overall_start_time).total_seconds()

        # 计算所有阶段的总进度
        completed_stages = sum(
            1 for p in self.stages.values() if p.status == "completed"
        )
        running_stages = sum(1 for p in self.stages.values() if p.status == "running")
        failed_stages = sum(1 for p in self.stages.values() if p.status == "failed")

        # 计算平均进度（只计算已启动的阶段，不包括还未启动的）
        started_stages = [p for p in self.stages.values() if p.status != "pending"]
        avg_progress = (
            sum(p.progress_percentage for p in started_stages) / len(started_stages)
            if started_stages
            else 0
        )

        return {
            "total_pages": self.total_pages,
            "overall_progress_percentage": avg_progress,
            "elapsed_seconds": overall_elapsed,
            "completed_stages": completed_stages,
            "running_stages": running_stages,
            "failed_stages": failed_stages,
            "stages": {
                stage.name: {
                    "current": progress.current,
                    "total": progress.total,
                    "status": progress.status,
                    "progress_percentage": progress.progress_percentage,
                    "elapsed_seconds": progress.elapsed_seconds,
                    "estimated_remaining_seconds": progress.estimated_remaining_seconds,
                }
                for stage, progress in self.stages.items()
            },
        }

    def print_summary(self):
        """打印总结信息"""
        overall = self.get_overall_progress()
        logger.info("=" * 60)
        logger.info("处理总结")
        logger.info("=" * 60)

        for stage_name, info in overall["stages"].items():
            if info["total"] > 0:
                logger.info(
                    f"{stage_name:12} | "
                    f"{info['current']:3}/{info['total']:3} | "
                    f"{info['progress_percentage']:5.1f}% | "
                    f"状态: {info['status']}"
                )

        total_time = overall["elapsed_seconds"]
        logger.info("=" * 60)
        logger.info(
            f"总耗时: {int(total_time // 60):02d}:{int(total_time % 60):02d} "
            f"({total_time:.1f} 秒)"
        )
        logger.info("=" * 60)
