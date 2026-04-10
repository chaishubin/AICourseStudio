"""
处理进度跟踪系统的单元测试
"""

import time
from datetime import datetime, timedelta

import pytest

from vidppt.utils.progress import ProgressTracker, ProcessStage, StageProgress


class TestStageProgress:
    """测试单个阶段的进度"""

    def test_stage_progress_initial_state(self):
        """测试初始状态"""
        progress = StageProgress(stage=ProcessStage.TTS, total=10)
        assert progress.current == 0
        assert progress.total == 10
        assert progress.status == "pending"
        assert progress.progress_percentage == 0

    def test_stage_progress_update(self):
        """测试进度更新"""
        progress = StageProgress(stage=ProcessStage.TTS, total=10)
        progress.start()
        progress.update(5)
        assert progress.current == 5
        assert progress.progress_percentage == 50

    def test_stage_progress_complete(self):
        """测试完成阶段"""
        progress = StageProgress(stage=ProcessStage.TTS, total=10)
        progress.start()
        time.sleep(0.1)  # 等待一段时间
        progress.complete()
        assert progress.status == "completed"
        assert progress.end_time is not None
        assert progress.elapsed_seconds >= 0.1

    def test_stage_progress_fail(self):
        """测试失败阶段"""
        progress = StageProgress(stage=ProcessStage.TTS, total=10)
        progress.start()
        progress.fail("测试错误")
        assert progress.status == "failed"
        assert progress.end_time is not None

    def test_elapsed_time_calculation(self):
        """测试耗时计算"""
        progress = StageProgress(stage=ProcessStage.TTS, total=10)
        progress.start()
        time.sleep(0.2)
        assert progress.elapsed_seconds >= 0.2

    def test_estimated_remaining_time(self):
        """测试估计剩余时间"""
        progress = StageProgress(stage=ProcessStage.TTS, total=100)
        progress.start()
        time.sleep(0.1)
        progress.update(10)
        # 如果处理 10 项用了 0.1 秒，剩余 90 项应该需要约 0.9 秒
        estimated = progress.estimated_remaining_seconds
        assert estimated >= 0.8  # 允许一些误差

    def test_progress_percentage_boundary(self):
        """测试进度百分比边界"""
        progress = StageProgress(stage=ProcessStage.TTS, total=0)
        assert progress.progress_percentage == 0

        progress = StageProgress(stage=ProcessStage.TTS, total=10)
        progress.update(15)  # 超过总数
        assert progress.progress_percentage == 100


class TestProgressTracker:
    """测试进度跟踪器"""

    def test_tracker_initialization(self):
        """测试初始化"""
        tracker = ProgressTracker(total_pages=20, enable_progress=True)
        assert tracker.total_pages == 20
        assert tracker.enable_progress is True
        assert len(tracker.stages) == len(ProcessStage)

    def test_start_stage(self):
        """测试开始阶段"""
        tracker = ProgressTracker(total_pages=10)
        progress = tracker.start_stage(ProcessStage.EXTRACT)
        assert progress.status == "running"
        assert progress.start_time is not None

    def test_update_stage(self):
        """测试更新阶段进度"""
        tracker = ProgressTracker(total_pages=10)
        tracker.start_stage(ProcessStage.EXTRACT)
        tracker.update_stage(ProcessStage.EXTRACT, 5, 10)
        progress = tracker.get_stage_progress(ProcessStage.EXTRACT)
        assert progress.current == 5
        assert progress.total == 10

    def test_complete_stage(self):
        """测试完成阶段"""
        tracker = ProgressTracker(total_pages=10)
        tracker.start_stage(ProcessStage.EXTRACT)
        tracker.complete_stage(ProcessStage.EXTRACT)
        progress = tracker.get_stage_progress(ProcessStage.EXTRACT)
        assert progress.status == "completed"

    def test_fail_stage(self):
        """测试阶段失败"""
        tracker = ProgressTracker(total_pages=10)
        tracker.start_stage(ProcessStage.EXTRACT)
        tracker.fail_stage(ProcessStage.EXTRACT, "测试错误")
        progress = tracker.get_stage_progress(ProcessStage.EXTRACT)
        assert progress.status == "failed"

    def test_get_overall_progress(self):
        """测试获取整体进度"""
        tracker = ProgressTracker(total_pages=10)

        # 完成第一个阶段
        tracker.start_stage(ProcessStage.EXTRACT)
        tracker.update_stage(ProcessStage.EXTRACT, 10, 10)
        tracker.complete_stage(ProcessStage.EXTRACT)

        # 运行第二个阶段
        tracker.start_stage(ProcessStage.TTS)
        tracker.update_stage(ProcessStage.TTS, 5, 10)

        overall = tracker.get_overall_progress()
        assert overall["total_pages"] == 10
        assert overall["completed_stages"] == 1
        assert overall["running_stages"] == 1

    def test_multiple_stages_workflow(self):
        """测试多阶段工作流"""
        tracker = ProgressTracker(total_pages=5)

        # EXTRACT 阶段
        tracker.start_stage(ProcessStage.EXTRACT)
        for i in range(1, 6):
            tracker.update_stage(ProcessStage.EXTRACT, i, 5)
        tracker.complete_stage(ProcessStage.EXTRACT)

        # TTS 阶段
        tracker.start_stage(ProcessStage.TTS)
        for i in range(1, 6):
            tracker.update_stage(ProcessStage.TTS, i, 5)
        tracker.complete_stage(ProcessStage.TTS)

        # VIDEO 阶段
        tracker.start_stage(ProcessStage.VIDEO)
        for i in range(1, 6):
            tracker.update_stage(ProcessStage.VIDEO, i, 5)
        tracker.complete_stage(ProcessStage.VIDEO)

        overall = tracker.get_overall_progress()
        assert overall["completed_stages"] == 3

    def test_progress_with_disabled_progress_bar(self):
        """测试禁用进度条时的行为"""
        tracker = ProgressTracker(total_pages=10, enable_progress=False)
        tracker.start_stage(ProcessStage.EXTRACT)
        # 这不应该抛出异常
        tracker.update_stage(ProcessStage.EXTRACT, 5, 10)

    def test_stage_auto_start(self):
        """测试更新阶段时的自动启动"""
        tracker = ProgressTracker(total_pages=10)
        # 不手动 start_stage，直接 update 应该自动启动
        tracker.update_stage(ProcessStage.EXTRACT, 1, 10)
        progress = tracker.get_stage_progress(ProcessStage.EXTRACT)
        assert progress.status == "running"

    def test_overall_progress_percentage(self):
        """测试整体进度百分比"""
        tracker = ProgressTracker(total_pages=10)

        # 每个阶段完成 50%
        for stage in ProcessStage:
            tracker.start_stage(stage)
            tracker.update_stage(stage, 5, 10)

        overall = tracker.get_overall_progress()
        # 所有阶段都是 50%，所以整体应该是 50%
        assert overall["overall_progress_percentage"] == 50

    def test_elapsed_time_tracking(self):
        """测试耗时跟踪"""
        tracker = ProgressTracker(total_pages=10)
        tracker.start_stage(ProcessStage.EXTRACT)
        time.sleep(0.2)
        tracker.complete_stage(ProcessStage.EXTRACT)

        progress = tracker.get_stage_progress(ProcessStage.EXTRACT)
        assert progress.elapsed_seconds >= 0.2

        overall = tracker.get_overall_progress()
        assert overall["elapsed_seconds"] >= 0.2


class TestProgressTrackerIntegration:
    """集成测试"""

    def test_realistic_workflow(self):
        """测试真实工作流"""
        tracker = ProgressTracker(
            total_pages=100, enable_progress=False
        )  # 禁用进度条防止大量日志

        # 模拟 EXTRACT 阶段
        tracker.start_stage(ProcessStage.EXTRACT)
        for i in range(1, 101):
            tracker.update_stage(ProcessStage.EXTRACT, i, 100)
            if i % 25 == 0:
                time.sleep(0.01)  # 模拟处理时间
        tracker.complete_stage(ProcessStage.EXTRACT)

        # 模拟 TTS 阶段（部分缓存命中）
        tracker.start_stage(ProcessStage.TTS)
        for i in range(1, 101):
            tracker.update_stage(ProcessStage.TTS, i, 100)
            if i % 20 == 0:
                time.sleep(0.01)  # 模拟处理时间
        tracker.complete_stage(ProcessStage.TTS)

        # 模拟 VIDEO 阶段
        tracker.start_stage(ProcessStage.VIDEO)
        for i in range(1, 101):
            tracker.update_stage(ProcessStage.VIDEO, i, 100)
            if i % 25 == 0:
                time.sleep(0.01)  # 模拟处理时间
        tracker.complete_stage(ProcessStage.VIDEO)

        overall = tracker.get_overall_progress()
        assert overall["completed_stages"] == 3
        assert overall["overall_progress_percentage"] == 100  # 所有阶段都完成
        assert overall["elapsed_seconds"] > 0

        # 打印总结（应该不会抛出异常）
        tracker.print_summary()
