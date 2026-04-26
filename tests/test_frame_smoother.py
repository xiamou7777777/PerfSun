"""
帧率平滑器单元测试

测试帧率平滑功能:
- 滑动平均平滑
- 指数平滑
- 卡尔曼平滑
"""

import pytest
from perfsun.utils.frame_smoother import (
    FrameRateSmoother,
    ExponentialSmoother,
    KalmanSmoother,
    create_smoother,
)


class TestFrameRateSmoother:
    """
    FrameRateSmoother测试类
    """

    def setup_method(self):
        """
        每个测试方法执行前的setup
        """
        self.smoother = FrameRateSmoother(window_size=5)

    def test_initial_state(self):
        """
        测试初始状态
        """
        assert self.smoother.get_smoothed_fps() == 0.0
        assert self.smoother.get_average_frame_time() == 0.0

    def test_add_frame_time(self):
        """
        测试添加帧时间
        """
        fps = self.smoother.add_frame_time(16.67)

        assert 55.0 < fps < 65.0
        assert self.smoother.get_average_frame_time() == pytest.approx(16.67, rel=0.1)

    def test_multiple_frame_times(self):
        """
        测试添加多帧
        """
        self.smoother.add_frame_time(16.67)
        self.smoother.add_frame_time(16.67)
        self.smoother.add_frame_time(16.67)

        smoothed_fps = self.smoother.get_smoothed_fps()

        assert 55.0 < smoothed_fps < 65.0

    def test_frame_time_smoothing(self):
        """
        测试帧时间平滑效果
        """
        self.smoother.add_frame_time(16.67)
        self.smoother.add_frame_time(16.67)
        self.smoother.add_frame_time(100.0)
        self.smoother.add_frame_time(16.67)
        self.smoother.add_frame_time(16.67)

        smoothed_fps = self.smoother.get_smoothed_fps()

        assert smoothed_fps < 50.0

    def test_reset(self):
        """
        测试重置
        """
        self.smoother.add_frame_time(16.67)
        self.smoother.add_frame_time(100.0)

        self.smoother.reset()

        assert self.smoother.get_smoothed_fps() == 0.0
        assert self.smoother.get_average_frame_time() == 0.0

    def test_get_stats(self):
        """
        测试获取统计信息
        """
        self.smoother.add_frame_time(16.67)
        self.smoother.add_frame_time(16.67)
        self.smoother.add_frame_time(20.0)

        stats = self.smoother.get_stats()

        assert "smoothed_fps" in stats
        assert "avg_frame_time" in stats
        assert "min_fps" in stats
        assert "max_fps" in stats
        assert "fps_std" in stats

    def test_window_overflow(self):
        """
        测试窗口溢出
        """
        for i in range(10):
            self.smoother.add_frame_time(16.67 + i)

        assert len(self.smoother.frame_times) == 5
        assert len(self.smoother.fps_values) == 5


class TestExponentialSmoother:
    """
    ExponentialSmoother测试类
    """

    def test_initial_state(self):
        """
        测试初始状态
        """
        smoother = ExponentialSmoother()
        assert smoother.get_value() == 0.0

    def test_first_value(self):
        """
        测试第一个值
        """
        smoother = ExponentialSmoother()
        result = smoother.add(100.0)

        assert result == 100.0

    def test_smoothing(self):
        """
        测试平滑效果
        """
        smoother = ExponentialSmoother(alpha=0.3)

        smoother.add(100.0)
        result = smoother.add(200.0)

        assert 100.0 < result < 200.0

    def test_alpha_zero(self):
        """
        测试alpha=0(完全平滑)
        """
        smoother = ExponentialSmoother(alpha=0.0)

        smoother.add(100.0)
        result = smoother.add(200.0)

        assert result == 100.0

    def test_alpha_one(self):
        """
        测试alpha=1(无平滑)
        """
        smoother = ExponentialSmoother(alpha=1.0)

        smoother.add(100.0)
        result = smoother.add(200.0)

        assert result == 200.0

    def test_reset(self):
        """
        测试重置
        """
        smoother = ExponentialSmoother()

        smoother.add(100.0)
        smoother.reset()

        assert smoother.get_value() == 0.0


class TestKalmanSmoother:
    """
    KalmanSmoother测试类
    """

    def test_initial_state(self):
        """
        测试初始状态
        """
        smoother = KalmanSmoother()
        assert smoother.get_value() == 0.0

    def test_first_measurement(self):
        """
        测试第一个测量值
        """
        smoother = KalmanSmoother()
        result = smoother.add(100.0)

        assert result == 100.0

    def test_noise_filtering(self):
        """
        测试噪声过滤
        """
        smoother = KalmanSmoother(q=0.01, r=1.0)

        smoother.add(100.0)
        result = smoother.add(101.0)

        assert abs(result - 100.0) < 1.0

    def test_sudden_change(self):
        """
        测试突变
        """
        smoother = KalmanSmoother(q=0.1, r=1.0)

        smoother.add(100.0)
        smoother.add(100.0)
        result = smoother.add(200.0)

        assert result > 100.0

    def test_reset(self):
        """
        测试重置
        """
        smoother = KalmanSmoother()

        smoother.add(100.0)
        smoother.reset()

        assert smoother.get_value() == 0.0


class TestCreateSmoother:
    """
    create_smoother工厂函数测试类
    """

    def test_create_moving_average(self):
        """
        测试创建滑动平均平滑器
        """
        smoother = create_smoother("moving_average", window_size=10)

        assert isinstance(smoother, FrameRateSmoother)
        assert smoother.window_size == 10

    def test_create_exponential(self):
        """
        测试创建指数平滑器
        """
        smoother = create_smoother("exponential", alpha=0.5)

        assert isinstance(smoother, ExponentialSmoother)

    def test_create_kalman(self):
        """
        测试创建卡尔曼平滑器
        """
        smoother = create_smoother("kalman", q=0.1, r=1.0)

        assert isinstance(smoother, KalmanSmoother)

    def test_invalid_type(self):
        """
        测试无效类型
        """
        with pytest.raises(ValueError):
            create_smoother("invalid_type")


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
