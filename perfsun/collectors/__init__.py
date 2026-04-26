"""
PerfSun 平台采集器模块

本模块包含所有平台特定的性能采集器实现。
目前支持以下平台：
- Android：通过 ADB 连接，采集 FPS/CPU/内存/GPU/网络/温度等指标
- iOS：通过 pymobiledevice3 连接，采集 FPS/CPU/内存/网络等指标
- Windows：通过 PDH/psutil 采集 CPU/内存/GPU/网络/温度等指标

每个采集器都继承自 Collectible 抽象基类，确保统一的接口和行为。
"""

from perfsun.collectors.base import Collectible, CollectorConfig, DeviceInfo
from perfsun.collectors.android import AndroidCollector
from perfsun.collectors.ios import IOSCollector
from perfsun.collectors.windows import WindowsCollector

__all__ = [
    "Collectible",
    "CollectorConfig",
    "DeviceInfo",
    "AndroidCollector",
    "IOSCollector",
    "WindowsCollector",
]
