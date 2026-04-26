"""
PerfSun 工具模块

本模块提供各类工具类和算法实现：
- ADBTools：ADB 命令封装，用于 Android 设备通信
- FrameRateSmoother：帧率平滑器，提供多种平滑算法
- JankDetector：卡顿检测器，实现 Jank/BigJank 判定
"""

from perfsun.utils.adb import ADBTools
from perfsun.utils.frame_smoother import FrameRateSmoother, ExponentialSmoother, KalmanSmoother
from perfsun.utils.jank_detector import JankDetector, AdaptiveJankDetector

__all__ = [
    "ADBTools",
    "FrameRateSmoother",
    "ExponentialSmoother",
    "KalmanSmoother",
    "JankDetector",
    "AdaptiveJankDetector",
]
