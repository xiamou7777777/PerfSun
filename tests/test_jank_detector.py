"""
Jank检测器单元测试

测试卡顿检测功能:
- Jank判定逻辑
- BigJank判定逻辑
- 统计数据计算
- FPS范围计算
"""

import pytest
from perfsun.utils.jank_detector import (
    JankDetector,
    JankLevel,
    JankStatistics,
    AdaptiveJankDetector,
)


class TestJankDetector:
    """
    JankDetector测试类
    """

    def setup_method(self):
        """
        每个测试方法执行前的setup
        """
        self.detector = JankDetector(
            jank_threshold_ms=84.0,
            big_jank_threshold_ms=125.0,
            frame_window_size=60,
        )

    def test_normal_frame(self):
        """
        测试正常帧(16.67ms)不应被判定为jank
        """
        result = self.detector.add_frame_time(16.67, timestamp=1.0)
        assert result == JankLevel.NORMAL

    def test_slightly_slow_frame(self):
        """
        测试略慢帧(50ms)不应被判定为jank
        """
        result = self.detector.add_frame_time(50.0, timestamp=1.0)
        assert result == JankLevel.NORMAL

    def test_jank_detection(self):
        """
        测试Jank判定:帧时间>84ms且>上一帧*2
        """
        self.detector.add_frame_time(16.67, timestamp=1.0)

        result = self.detector.add_frame_time(90.0, timestamp=1.01667)
        assert result == JankLevel.JANK

    def test_big_jank_detection(self):
        """
        测试BigJank判定:帧时间>125ms
        """
        result = self.detector.add_frame_time(130.0, timestamp=1.0)
        assert result == JankLevel.BIG_JANK

    def test_double_frame_time_jank(self):
        """
        测试双倍帧时间判定jank
        """
        self.detector.add_frame_time(50.0, timestamp=1.0)

        result = self.detector.add_frame_time(110.0, timestamp=1.05)
        assert result == JankLevel.JANK

    def test_statistics_empty(self):
        """
        测试空状态统计
        """
        stats = self.detector.get_statistics()

        assert stats.total_frames == 0
        assert stats.jank_count == 0
        assert stats.big_jank_count == 0
        assert stats.jank_rate == 0.0

    def test_statistics_with_frames(self):
        """
        测试有帧数据时的统计
        """
        self.detector.add_frame_time(16.67, timestamp=1.0)
        self.detector.add_frame_time(16.67, timestamp=1.01667)
        self.detector.add_frame_time(16.67, timestamp=1.03334)

        stats = self.detector.get_statistics()

        assert stats.total_frames == 3
        assert stats.jank_count == 0
        assert stats.big_jank_count == 0
        assert 0.0 <= stats.jank_rate <= 100.0

    def test_statistics_with_janks(self):
        """
        测试有卡顿时的统计
        """
        self.detector.add_frame_time(16.67, timestamp=1.0)
        self.detector.add_frame_time(16.67, timestamp=1.01667)
        self.detector.add_frame_time(90.0, timestamp=1.03334)

        stats = self.detector.get_statistics()

        assert stats.total_frames == 3
        assert stats.jank_count == 1
        assert stats.big_jank_count == 0
        assert stats.jank_rate > 0.0

    def test_fps_calculation(self):
        """
        测试FPS计算
        """
        self.detector.add_frame_time(16.67, timestamp=1.0)
        self.detector.add_frame_time(16.67, timestamp=1.01667)
        self.detector.add_frame_time(16.67, timestamp=1.03334)

        fps = self.detector.get_current_fps()

        assert 55.0 <= fps <= 65.0

    def test_fps_range(self):
        """
        测试FPS范围计算
        """
        self.detector.add_frame_time(20.0, timestamp=1.0)
        self.detector.add_frame_time(16.67, timestamp=1.02)
        self.detector.add_frame_time(25.0, timestamp=1.04)

        min_fps, max_fps = self.detector.get_fps_range()

        assert min_fps > 0
        assert max_fps > min_fps

    def test_reset(self):
        """
        测试重置功能
        """
        self.detector.add_frame_time(16.67, timestamp=1.0)
        self.detector.add_frame_time(130.0, timestamp=1.01667)

        self.detector.reset()

        stats = self.detector.get_statistics()
        assert stats.total_frames == 0
        assert stats.jank_count == 0

    def test_get_jank_level(self):
        """
        测试获取卡顿等级字符串
        """
        self.detector.add_frame_time(16.67, timestamp=1.0)

        assert self.detector.get_jank_level(16.67) == "normal"
        assert self.detector.get_jank_level(90.0) == "jank"
        assert self.detector.get_jank_level(130.0) == "big_jank"

    def test_is_frame_smooth(self):
        """
        测试帧流畅判断
        """
        assert self.detector.is_frame_smooth(16.67) is True
        assert self.detector.is_frame_smooth(80.0) is True
        assert self.detector.is_frame_smooth(90.0) is False
        assert self.detector.is_frame_smooth(130.0) is False

    def test_set_thresholds(self):
        """
        测试设置阈值
        """
        self.detector.set_thresholds(100.0, 150.0)

        assert self.detector.jank_threshold_ms == 100.0
        assert self.detector.big_jank_threshold_ms == 150.0

    def test_jank_events_list(self):
        """
        测试卡顿事件列表
        """
        self.detector.add_frame_time(16.67, timestamp=1.0)
        self.detector.add_frame_time(90.0, timestamp=1.01667)
        self.detector.add_frame_time(130.0, timestamp=1.03334)

        events = self.detector.get_jank_events()

        assert len(events) == 2
        assert events[0].jank_level == JankLevel.JANK
        assert events[1].jank_level == JankLevel.BIG_JANK

    def test_recent_jank_events(self):
        """
        测试获取最近卡顿事件
        """
        for i in range(20):
            self.detector.add_frame_time(16.67, timestamp=float(i))

        self.detector.add_frame_time(90.0, timestamp=20.0)
        self.detector.add_frame_time(130.0, timestamp=20.01667)

        recent = self.detector.get_recent_jank_events(count=5)

        assert len(recent) == 2


class TestAdaptiveJankDetector:
    """
    AdaptiveJankDetector测试类
    """

    def test_default_60hz_thresholds(self):
        """
        测试默认60Hz阈值
        """
        detector = AdaptiveJankDetector(refresh_rate=60.0)

        assert detector.jank_threshold_ms == pytest.approx(83.33, rel=0.1)
        assert detector.big_jank_threshold_ms == pytest.approx(125.0, rel=0.1)

    def test_120hz_thresholds(self):
        """
        测试120Hz阈值
        """
        detector = AdaptiveJankDetector(refresh_rate=120.0)

        assert detector.jank_threshold_ms == pytest.approx(41.67, rel=0.1)
        assert detector.big_jank_threshold_ms == pytest.approx(62.5, rel=0.1)

    def test_90hz_thresholds(self):
        """
        测试90Hz阈值
        """
        detector = AdaptiveJankDetector(refresh_rate=90.0)

        frame_time = 1000.0 / 90.0

        assert detector.jank_threshold_ms == pytest.approx(frame_time * 5, rel=0.1)
        assert detector.big_jank_threshold_ms == pytest.approx(frame_time * 7.5, rel=0.1)

    def test_set_refresh_rate(self):
        """
        测试设置刷新率
        """
        detector = AdaptiveJankDetector(refresh_rate=60.0)

        detector.set_refresh_rate(144.0)

        assert detector.refresh_rate == 144.0
        frame_time = 1000.0 / 144.0
        assert detector.jank_threshold_ms == pytest.approx(frame_time * 5, rel=0.1)


class TestJankStatistics:
    """
    JankStatistics测试类
    """

    def test_to_dict(self):
        """
        测试转换为字典
        """
        stats = JankStatistics(
            total_frames=100,
            jank_count=5,
            big_jank_count=1,
            jank_rate=5.0,
            big_jank_rate=1.0,
            avg_frame_time=18.5,
            max_frame_time=130.0,
            jank_duration=215.0,
        )

        result = stats.to_dict()

        assert result["total_frames"] == 100
        assert result["jank_count"] == 5
        assert result["big_jank_count"] == 1
        assert result["jank_rate"] == 5.0
        assert result["avg_frame_time"] == 18.5
        assert result["max_frame_time"] == 130.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
