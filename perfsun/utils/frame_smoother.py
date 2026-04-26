"""
PerfSun 帧率平滑器

本模块提供多种帧率数据平滑算法，用于减少瞬时帧率波动，
使数据曲线更加平滑，便于分析和展示。

对标 PerfDog 的帧率平滑功能，提供三种平滑策略：
1. 滑动窗口平均（Moving Average）：基础平滑，适合大多数场景
2. 指数平滑（Exponential）：快速响应变化，适合实时监控
3. 卡尔曼滤波（Kalman）：自适应平滑，适合噪声较大的场景
"""

from collections import deque
from typing import List, Optional
import statistics
import math


class FrameRateSmoother:
    """
    帧率平滑器（滑动窗口平均算法）

    使用滑动窗口平均算法平滑帧率数据。
    窗口大小决定了平滑程度：窗口越大曲线越平滑，但响应越慢。

    对标 PerfDog 的帧率平滑功能。

    Attributes:
        window_size: 滑动窗口大小
        frame_times: 帧时间队列
        fps_values: FPS 值队列
    """

    def __init__(self, window_size: int = 5):
        """
        初始化帧率平滑器

        Args:
            window_size: 滑动窗口大小，默认 5 帧
                        可选值建议：实时监控用 3-5，分析用 10-30
        """
        self.window_size = window_size
        self.frame_times: deque = deque(maxlen=window_size)
        self.fps_values: deque = deque(maxlen=window_size)

    def add_frame_time(self, frame_time_ms: float) -> float:
        """
        添加一帧的帧时间，返回平滑后的 FPS

        Args:
            frame_time_ms: 帧时间（毫秒）

        Returns:
            平滑后的 FPS 值
        """
        self.frame_times.append(frame_time_ms)

        avg_frame_time = sum(self.frame_times) / len(self.frame_times)

        if avg_frame_time > 0:
            fps = 1000.0 / avg_frame_time
        else:
            fps = 0.0

        self.fps_values.append(fps)
        return fps

    def add_fps(self, fps: float) -> float:
        """
        添加原始 FPS 值，返回平滑后的 FPS

        Args:
            fps: 原始 FPS 值

        Returns:
            平滑后的 FPS 值
        """
        self.fps_values.append(fps)

        if len(self.fps_values) >= 2:
            return sum(self.fps_values) / len(self.fps_values)
        return fps

    def get_smoothed_fps(self) -> float:
        """
        获取当前平滑后的 FPS 值

        Returns:
            平滑后的 FPS 值，无数据则返回 0
        """
        if not self.fps_values:
            return 0.0
        return sum(self.fps_values) / len(self.fps_values)

    def get_average_frame_time(self) -> float:
        """
        获取当前平均帧时间

        Returns:
            平均帧时间（毫秒），无数据则返回 0
        """
        if not self.frame_times:
            return 0.0
        return sum(self.frame_times) / len(self.frame_times)

    def reset(self) -> None:
        """
        重置所有缓冲数据

        清除窗口内的帧时间和 FPS 数据。
        """
        self.frame_times.clear()
        self.fps_values.clear()

    def get_stats(self) -> dict:
        """
        获取帧率统计信息

        Returns:
            包含详细统计信息的字典：
            - smoothed_fps: 平滑后的 FPS
            - avg_frame_time: 平均帧时间
            - min_fps: 窗口内最小 FPS
            - max_fps: 窗口内最大 FPS
            - fps_std: FPS 标准差（反映帧率稳定性）
        """
        if not self.fps_values:
            return {
                "smoothed_fps": 0.0,
                "avg_frame_time": 0.0,
                "min_fps": 0.0,
                "max_fps": 0.0,
                "fps_std": 0.0,
            }

        fps_list = list(self.fps_values)
        return {
            "smoothed_fps": sum(fps_list) / len(fps_list),
            "avg_frame_time": sum(self.frame_times) / len(self.frame_times) if self.frame_times else 0.0,
            "min_fps": min(fps_list),
            "max_fps": max(fps_list),
            "fps_std": statistics.stdev(fps_list) if len(fps_list) > 1 else 0.0,
        }

    def get_fps_variance(self) -> float:
        """
        获取 FPS 方差

        方差越大表示帧率波动越大，流畅度越差。

        Returns:
            FPS 方差值
        """
        if len(self.fps_values) < 2:
            return 0.0
        fps_list = list(self.fps_values)
        mean = sum(fps_list) / len(fps_list)
        return sum((f - mean) ** 2 for f in fps_list) / len(fps_list)


class ExponentialSmoother:
    """
    指数平滑器（Exponential Weighted Moving Average）

    使用指数加权移动平均算法平滑数据。
    相比滑动窗口平均，指数平滑对最近数据赋予更高权重，
    响应速度更快，适合实时监控场景。

    公式：S_t = α * x_t + (1 - α) * S_{t-1}

    Attributes:
        alpha: 平滑系数 (0-1)，值越大对最近数据响应越快
        _last_value: 上一个平滑值
    """

    def __init__(self, alpha: float = 0.3):
        """
        初始化指数平滑器

        Args:
            alpha: 平滑系数，默认 0.3
                   - 接近 1：快速响应变化（对噪声敏感）
                   - 接近 0：高度平滑（响应迟钝）
        """
        self.alpha = max(0.0, min(1.0, alpha))
        self._last_value: Optional[float] = None

    def add(self, value: float) -> float:
        """
        添加新值并返回平滑后的值

        Args:
            value: 新的测量值

        Returns:
            平滑后的值
        """
        if self._last_value is None:
            self._last_value = value
        else:
            self._last_value = self.alpha * value + (1 - self.alpha) * self._last_value

        return self._last_value

    def get_value(self) -> float:
        """
        获取当前平滑值

        Returns:
            平滑后的值，无数据则返回 0
        """
        return self._last_value if self._last_value is not None else 0.0

    def reset(self) -> None:
        """
        重置平滑器

        清除历史值，恢复到初始状态。
        """
        self._last_value = None


class KalmanSmoother:
    """
    卡尔曼平滑器（Kalman Filter）

    使用卡尔曼滤波算法平滑数据。
    卡尔曼滤波是一种最优估计算法，能够自适应调整平滑程度，
    在噪声较大的场景下表现优异。

    适用于：传感器数据滤波、帧率抖动特别大的场景。

    Attributes:
        _q: 过程噪声协方差（系统不确定性）
        _r: 测量噪声协方差（测量不确定性）
        _x: 状态估计值
        _p: 估计误差协方差
        _k: 卡尔曼增益
    """

    def __init__(self, q: float = 0.1, r: float = 1.0):
        """
        初始化卡尔曼平滑器

        Args:
            q: 过程噪声协方差，默认 0.1
               q 越大，滤波器响应越快
            r: 测量噪声协方差，默认 1.0
               r 越大，平滑程度越高
        """
        self._q = q
        self._r = r
        self._x: Optional[float] = None
        self._p: float = 1.0
        self._k: float = 0.0

    def add(self, measurement: float) -> float:
        """
        添加测量值，返回平滑后的估计值

        执行一次完整的卡尔曼滤波更新：
        1. 预测：更新先验估计
        2. 更新：结合测量值修正估计

        Args:
            measurement: 测量值

        Returns:
            平滑后的估计值
        """
        if self._x is None:
            self._x = measurement
            return self._x

        # 预测步骤
        self._p += self._q

        # 更新步骤：计算卡尔曼增益
        self._k = self._p / (self._p + self._r)

        # 更新步骤：修正估计
        self._x = self._x + self._k * (measurement - self._x)

        # 更新步骤：更新误差协方差
        self._p = (1 - self._k) * self._p

        return self._x

    def get_value(self) -> float:
        """
        获取当前平滑后的估计值

        Returns:
            平滑后的估计值，无数据则返回 0
        """
        return self._x if self._x is not None else 0.0

    def reset(self) -> None:
        """
        重置滤波器

        清除所有状态，恢复到初始值。
        """
        self._x = None
        self._p = 1.0
        self._k = 0.0


def create_smoother(smoother_type: str = "moving_average", **kwargs) -> object:
    """
    创建指定类型的平滑器（工厂方法）

    根据参数创建对应类型的平滑器实例。

    Args:
        smoother_type: 平滑器类型
            - "moving_average": 滑动平均平滑器（默认）
            - "exponential": 指数平滑器
            - "kalman": 卡尔曼平滑器
        **kwargs: 平滑器参数
            - window_size: (移动平均) 窗口大小
            - alpha: (指数) 平滑系数
            - q, r: (卡尔曼) 噪声协方差

    Returns:
        平滑器实例

    Raises:
        ValueError: 未知的平滑器类型
    """
    if smoother_type == "moving_average":
        return FrameRateSmoother(window_size=kwargs.get("window_size", 5))
    elif smoother_type == "exponential":
        return ExponentialSmoother(alpha=kwargs.get("alpha", 0.3))
    elif smoother_type == "kalman":
        return KalmanSmoother(q=kwargs.get("q", 0.1), r=kwargs.get("r", 1.0))
    else:
        raise ValueError(f"未知的平滑器类型: {smoother_type}")
