"""
PerfSun - 跨平台性能采集工具

对标 PerfDog 的跨平台（Windows、Android、iOS）性能数据采集工具。
无需 ROOT/越狱即可获取设备性能指标，包括 FPS、CPU、内存、GPU、网络等。

核心能力：
- Android：通过 ADB 连接，采集 FPS/CPU/内存/GPU/网络/温度
- iOS：通过 pymobiledevice3 连接，采集 FPS/CPU/内存/网络
- Windows：通过 PDH/psutil，采集 CPU/内存/GPU/网络/温度
- 数据导出：支持 CSV/JSON/Excel/HTML 交互式报告
- 卡顿检测：Jank/BigJank 检测算法
- 帧率平滑：多种平滑算法
- 功耗估算：基于性能指标的功耗模型
- 阈值告警：可自定义的告警规则系统
"""

__version__ = "1.0.0"
__author__ = "PerfSun Development Team"

from perfsun.core.data_point import DataPoint, MetricsSnapshot
from perfsun.core.collector_manager import CollectorManager
from perfsun.core.data_recorder import DataRecorder
from perfsun.core.data_exporter import DataExporter
from perfsun.core.alert_manager import AlertManager, AlertRule, AlertEvent, AlertSeverity

__all__ = [
    "DataPoint",
    "MetricsSnapshot",
    "CollectorManager",
    "DataRecorder",
    "DataExporter",
    "AlertManager",
    "AlertRule",
    "AlertEvent",
    "AlertSeverity",
]
