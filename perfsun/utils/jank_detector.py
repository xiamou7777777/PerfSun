"""
PerfSun 卡顿检测器

本模块实现 Jank（卡顿）和 BigJank（严重卡顿）的检测算法。
对标 PerfDog 的卡顿检测功能。

卡顿定义：
- Jank：当前帧时间 > 上一帧时间 × 2 且 > 84ms（60Hz 下约 5 帧）
- BigJank：当前帧时间 > 125ms（严重卡顿）

卡顿产生原因：
- 主线程阻塞（UI 线程执行耗时操作）
- GPU 渲染过载（绘制命令过多）
- 内存分配压力（频繁 GC）
- IO 阻塞（文件读写或网络请求）
- 线程调度延迟

提供两种检测器：
1. JankDetector：标准卡顿检测器，使用固定阈值
2. AdaptiveJankDetector：自适应卡顿检测器，根据设备刷新率调整阈值
"""

from collections import deque
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple
from enum import Enum
import time


class JankLevel(Enum):
    """
    卡顿等级枚举

    定义三种卡顿等级：
    - NORMAL: 正常帧，画面流畅
    - JANK: 卡顿帧，画面轻微停顿
    - BIG_JANK: 严重卡顿帧，画面明显停顿
    """
    NORMAL = "normal"       # 正常
    JANK = "jank"           # 卡顿
    BIG_JANK = "big_jank"   # 严重卡顿


@dataclass
class JankEvent:
    """
    卡顿事件数据类

    记录一次卡顿事件的详细信息，用于后续分析和统计。

    Attributes:
        timestamp: 事件发生的时间戳（秒）
        frame_time: 导致卡顿的帧时间（毫秒）
        jank_level: 卡顿等级
        prev_frame_time: 上一帧的帧时间（毫秒）
        expected_frame_time: 预期的帧时间（毫秒），与刷新率相关
    """
    timestamp: float
    frame_time: float
    jank_level: JankLevel
    prev_frame_time: float
    expected_frame_time: float = 16.67

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "frame_time": self.frame_time,
            "jank_level": self.jank_level.value,
            "prev_frame_time": self.prev_frame_time,
            "expected_frame_time": self.expected_frame_time,
        }


@dataclass
class JankStatistics:
    """
    卡顿统计数据类

    提供全面的卡顿统计信息，包括计数、比率和帧时间统计。

    Attributes:
        total_frames: 总帧数
        jank_count: Jank 帧数
        big_jank_count: BigJank 帧数
        jank_rate: Jank 率（百分比）
        big_jank_rate: BigJank 率（百分比）
        avg_frame_time: 平均帧时间（毫秒）
        max_frame_time: 最大帧时间（毫秒）
        jank_duration: 总卡顿时长（毫秒）
    """
    total_frames: int = 0
    jank_count: int = 0
    big_jank_count: int = 0
    jank_rate: float = 0.0
    big_jank_rate: float = 0.0
    avg_frame_time: float = 0.0
    max_frame_time: float = 0.0
    jank_duration: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "total_frames": self.total_frames,
            "jank_count": self.jank_count,
            "big_jank_count": self.big_jank_count,
            "jank_rate": round(self.jank_rate, 2),
            "big_jank_rate": round(self.big_jank_rate, 2),
            "avg_frame_time": round(self.avg_frame_time, 2),
            "max_frame_time": round(self.max_frame_time, 2),
            "jank_duration": round(self.jank_duration, 2),
        }


class JankDetector:
    """
    卡顿检测器

    通过分析帧时间数据，检测 Jank 和 BigJank 事件。
    使用滑动窗口记录历史帧时间，用于帧率统计。

    判定规则（对标 PerfDog）：
    - 60Hz 屏幕：正常帧时间约 16.67ms (1000/60)
    - Jank: 帧时间 > 84ms（约 5 帧）且 > 上一帧 × 2
    - BigJank: 帧时间 > 125ms（约 7.5 帧）

    Attributes:
        jank_threshold_ms: Jank 阈值（毫秒），默认 84ms
        big_jank_threshold_ms: BigJank 阈值（毫秒），默认 125ms
        frame_window_size: 帧时间窗口大小
        _frame_times: 帧时间历史记录
        _jank_events: 卡顿事件列表
        _prev_frame_time: 上一帧时间
    """

    def __init__(
        self,
        jank_threshold_ms: float = 84.0,
        big_jank_threshold_ms: float = 125.0,
        frame_window_size: int = 60,
    ):
        """
        初始化卡顿检测器

        Args:
            jank_threshold_ms: Jank 判定阈值（毫秒）
            big_jank_threshold_ms: BigJank 判定阈值（毫秒）
            frame_window_size: 帧时间窗口大小，用于 FPS 统计
        """
        self.jank_threshold_ms = jank_threshold_ms
        self.big_jank_threshold_ms = big_jank_threshold_ms
        self.frame_window_size = frame_window_size

        self._frame_times: deque = deque(maxlen=frame_window_size)
        self._jank_events: List[JankEvent] = []
        self._prev_frame_time: float = 16.67
        self._session_start_time: Optional[float] = None

    def add_frame_time(self, frame_time_ms: float, timestamp: float = 0.0) -> JankLevel:
        """
        添加一帧的帧时间并检测卡顿

        Args:
            frame_time_ms: 帧时间（毫秒）
            timestamp: 时间戳（秒），为 0 时使用当前时间

        Returns:
            JankLevel: 检测到的卡顿等级
        """
        if self._session_start_time is None:
            self._session_start_time = timestamp or time.time()

        actual_timestamp = timestamp or time.time()
        jank_level = self._detect_jank(frame_time_ms)

        self._frame_times.append(frame_time_ms)

        if jank_level != JankLevel.NORMAL:
            event = JankEvent(
                timestamp=actual_timestamp,
                frame_time=frame_time_ms,
                jank_level=jank_level,
                prev_frame_time=self._prev_frame_time,
            )
            self._jank_events.append(event)

        self._prev_frame_time = frame_time_ms
        return jank_level

    def _detect_jank(self, frame_time_ms: float) -> JankLevel:
        """
        检测卡顿等级

        判定逻辑（对标 PerfDog）：
        1. 帧时间 > BigJank 阈值 → BigJank
        2. 帧时间 > Jank 阈值 且 帧时间 > 上一帧 × 2 → Jank
        3. 否则 → Normal

        Args:
            frame_time_ms: 帧时间（毫秒）

        Returns:
            JankLevel: 卡顿等级
        """
        if frame_time_ms > self.big_jank_threshold_ms:
            return JankLevel.BIG_JANK

        if frame_time_ms > self.jank_threshold_ms and frame_time_ms > self._prev_frame_time * 2:
            return JankLevel.JANK

        return JankLevel.NORMAL

    def get_jank_level(self, frame_time_ms: float) -> str:
        """
        获取指定帧时间对应的卡顿等级字符串

        Args:
            frame_time_ms: 帧时间（毫秒）

        Returns:
            卡顿等级字符串: "normal", "jank", "big_jank"
        """
        level = self._detect_jank(frame_time_ms)
        return level.value

    def get_statistics(self) -> JankStatistics:
        """
        获取当前卡顿统计信息

        Returns:
            包含完整统计数据的 JankStatistics 对象
        """
        if not self._frame_times:
            return JankStatistics()

        frame_times_list = list(self._frame_times)
        total_frames = len(frame_times_list)
        jank_count = sum(1 for e in self._jank_events if e.jank_level == JankLevel.JANK)
        big_jank_count = sum(1 for e in self._jank_events if e.jank_level == JankLevel.BIG_JANK)

        total_frame_time = sum(frame_times_list)
        jank_duration = sum(e.frame_time for e in self._jank_events)

        return JankStatistics(
            total_frames=total_frames,
            jank_count=jank_count,
            big_jank_count=big_jank_count,
            jank_rate=(jank_count / total_frames * 100) if total_frames > 0 else 0.0,
            big_jank_rate=(big_jank_count / total_frames * 100) if total_frames > 0 else 0.0,
            avg_frame_time=total_frame_time / total_frames if total_frames > 0 else 0.0,
            max_frame_time=max(frame_times_list) if frame_times_list else 0.0,
            jank_duration=jank_duration,
        )

    def get_current_fps(self) -> float:
        """
        基于最近帧时间计算当前 FPS

        Returns:
            当前 FPS 值
        """
        if not self._frame_times:
            return 0.0

        recent_frame_times = list(self._frame_times)[-5:]
        avg_frame_time = sum(recent_frame_times) / len(recent_frame_times)

        if avg_frame_time > 0:
            return min(120.0, 1000.0 / avg_frame_time)
        return 0.0

    def get_fps_range(self) -> Tuple[float, float]:
        """
        获取窗口内 FPS 的最小值和最大值

        Returns:
            (min_fps, max_fps) 元组
        """
        if not self._frame_times:
            return (0.0, 0.0)

        frame_times_list = list(self._frame_times)

        if len(frame_times_list) == 1:
            fps = 1000.0 / frame_times_list[0] if frame_times_list[0] > 0 else 0.0
            return (fps, fps)

        min_frame_time = min(frame_times_list)
        max_frame_time = max(frame_times_list)

        max_fps = 1000.0 / min_frame_time if min_frame_time > 0 else 0.0
        min_fps = 1000.0 / max_frame_time if max_frame_time > 0 else 0.0

        return (min_fps, max_fps)

    def get_jank_events(self) -> List[JankEvent]:
        """
        获取所有卡顿事件列表

        Returns:
            完整的 JankEvent 列表
        """
        return self._jank_events.copy()

    def get_recent_jank_events(self, count: int = 10) -> List[JankEvent]:
        """
        获取最近的 N 个卡顿事件

        Args:
            count: 返回的事件数量

        Returns:
            最近的 JankEvent 列表
        """
        return self._jank_events[-count:]

    def reset(self) -> None:
        """
        重置检测器状态

        清除所有历史帧时间和卡顿事件记录，
        恢复到初始状态。
        """
        self._frame_times.clear()
        self._jank_events.clear()
        self._prev_frame_time = 16.67
        self._session_start_time = None

    def set_thresholds(self, jank_threshold_ms: float, big_jank_threshold_ms: float) -> None:
        """
        设置卡顿检测阈值

        Args:
            jank_threshold_ms: Jank 阈值（毫秒）
            big_jank_threshold_ms: BigJank 阈值（毫秒）
        """
        self.jank_threshold_ms = jank_threshold_ms
        self.big_jank_threshold_ms = big_jank_threshold_ms

    def is_frame_smooth(self, frame_time_ms: float) -> bool:
        """
        判断给定帧时间是否流畅

        Args:
            frame_time_ms: 帧时间（毫秒）

        Returns:
            True 表示流畅，False 表示卡顿
        """
        return frame_time_ms <= self.jank_threshold_ms

    def get_session_duration(self, current_time: float = 0.0) -> float:
        """
        获取检测会话持续时间

        Args:
            current_time: 当前时间戳

        Returns:
            持续时间（秒）
        """
        if self._session_start_time is None:
            return 0.0
        return (current_time or time.time()) - self._session_start_time

    def get_summary(self) -> Dict[str, Any]:
        """
        获取卡顿检测摘要信息

        Returns:
            包含摘要信息的字典，适合展示在报告中
        """
        stats = self.get_statistics()
        min_fps, max_fps = self.get_fps_range()

        return {
            "statistics": stats.to_dict(),
            "current_fps": self.get_current_fps(),
            "fps_range": {"min": round(min_fps, 1), "max": round(max_fps, 1)},
            "jank_threshold_ms": self.jank_threshold_ms,
            "big_jank_threshold_ms": self.big_jank_threshold_ms,
            "session_duration": round(self.get_session_duration(), 2),
            "total_jank_events": len(self._jank_events),
        }


class AdaptiveJankDetector(JankDetector):
    """
    自适应卡顿检测器

    根据设备刷新率自动调整卡顿检测阈值。
    支持多种刷新率：60Hz、90Hz、120Hz、144Hz 等。

    阈值计算规则：
    - Jank: 帧时间 > 刷新周期 × 5
    - BigJank: 帧时间 > 刷新周期 × 7.5

    例如，120Hz 下：
    - 刷新周期 = 1000/120 ≈ 8.33ms
    - Jank 阈值 = 8.33 × 5 ≈ 41.67ms
    - BigJank 阈值 = 8.33 × 7.5 ≈ 62.5ms

    Attributes:
        refresh_rate: 设备刷新率（Hz）
    """

    def __init__(
        self,
        refresh_rate: float = 60.0,
        frame_window_size: int = 60,
    ):
        """
        初始化自适应卡顿检测器

        Args:
            refresh_rate: 设备刷新率（Hz），默认 60Hz
            frame_window_size: 帧时间窗口大小
        """
        self.refresh_rate = refresh_rate

        # 根据刷新率自动计算阈值
        frame_time = 1000.0 / refresh_rate

        super().__init__(
            jank_threshold_ms=frame_time * 5,
            big_jank_threshold_ms=frame_time * 7.5,
            frame_window_size=frame_window_size,
        )

    def set_refresh_rate(self, refresh_rate: float) -> None:
        """
        设置设备刷新率，自动更新卡顿阈值

        Args:
            refresh_rate: 刷新率（Hz）
        """
        self.refresh_rate = refresh_rate

        frame_time = 1000.0 / refresh_rate
        self.jank_threshold_ms = frame_time * 5
        self.big_jank_threshold_ms = frame_time * 7.5

    def get_refresh_rate_info(self) -> Dict[str, Any]:
        """
        获取刷新率相关信息

        Returns:
            包含刷新率、帧周期、阈值的字典
        """
        frame_time = 1000.0 / self.refresh_rate
        return {
            "refresh_rate": self.refresh_rate,
            "frame_time_ms": round(frame_time, 2),
            "jank_threshold_ms": round(self.jank_threshold_ms, 2),
            "big_jank_threshold_ms": round(self.big_jank_threshold_ms, 2),
        }
