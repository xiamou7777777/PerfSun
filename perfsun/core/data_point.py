"""
PerfSun 数据点与指标快照定义

本模块定义了整个性能采集系统的核心数据结构，包括：
- 单条指标数据点 (DataPoint)
- 各类指标的数据容器 (FPSData, CPUData, MemoryData, GPUData, NetworkData, TemperatureData)
- 卡顿统计 (JankStats)
- 完整指标快照 (MetricsSnapshot)
- 自定义标记 (Mark)
- 会话信息 (SessionInfo)

这些数据结构贯穿数据采集、存储、导出全流程。
"""

from dataclasses import dataclass, field, asdict
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum
import json


class MetricType(Enum):
    """
    支持的指标类型枚举

    定义了 PerfSun 中所有可采集的性能指标类型，
    每种类型对应一个特定的性能指标标识符。
    """
    FPS = "fps"                          # 每秒帧数
    CPU_TOTAL = "cpu_total"              # 系统总CPU使用率
    CPU_PROCESS = "cpu_process"          # 目标进程CPU使用率
    CPU_THREAD = "cpu_thread"            # 线程级CPU使用率
    MEMORY_PSS = "memory_pss"            # 比例分配内存 (Proportional Set Size)
    MEMORY_RSS = "memory_rss"            # 常驻内存 (Resident Set Size)
    MEMORY_VSS = "memory_vss"            # 虚拟内存 (Virtual Set Size)
    GPU = "gpu"                          # GPU使用率
    NETWORK_UPLOAD = "network_upload"    # 网络上行速率
    NETWORK_DOWNLOAD = "network_download"  # 网络下行速率
    TEMPERATURE_CPU = "temperature_cpu"  # CPU温度
    TEMPERATURE_BATTERY = "temperature_battery"  # 电池温度
    BATTERY_LEVEL = "battery_level"      # 电池电量百分比
    FRAME_TIME = "frame_time"            # 帧渲染时间
    JANK = "jank"                        # 卡顿次数
    BIG_JANK = "big_jank"               # 严重卡顿次数


@dataclass
class DataPoint:
    """
    单条指标数据点

    表示在某个时间点采集的单个性能指标值。
    这是最基础的数据单元，所有采集的原始数据都以 DataPoint 形式存储。

    Attributes:
        timestamp: 数据采集时的 Unix 时间戳（秒）
        device_id: 源设备的唯一标识符
        platform: 平台类型 (android/ios/windows)
        metric_type: 指标类型，如 fps/cpu/memory 等
        value: 指标的数值
        unit: 计量单位 (fps/percent/MB/Bs/celsius 等)
        metadata: 附加的上下文元数据
    """
    timestamp: float
    device_id: str
    platform: str
    metric_type: str
    value: float
    unit: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        将 DataPoint 转换为字典格式

        Returns:
            包含所有字段的字典
        """
        return {
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "platform": self.platform,
            "metric_type": self.metric_type,
            "value": self.value,
            "unit": self.unit,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """
        序列化为 JSON 字符串

        Returns:
            DataPoint 的 JSON 字符串表示
        """
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DataPoint":
        """
        从字典创建 DataPoint 实例

        Args:
            data: 包含 DataPoint 字段的字典

        Returns:
            反序列化的 DataPoint 实例
        """
        return cls(
            timestamp=data["timestamp"],
            device_id=data["device_id"],
            platform=data["platform"],
            metric_type=data["metric_type"],
            value=data["value"],
            unit=data.get("unit", ""),
            metadata=data.get("metadata", {}),
        )


@dataclass
class FPSData:
    """
    FPS（每秒帧数）指标数据容器

    包含帧率相关的各项指标，用于评估画面流畅度。
    帧率越高，画面越流畅。通常 60fps 为流畅基准。

    Attributes:
        fps: 当前帧率值
        fps_min: 采集窗口内的最小帧率
        fps_max: 采集窗口内的最大帧率
        frame_time_avg: 平均帧渲染时间（毫秒）
        frame_time_min: 最小帧渲染时间（毫秒）
        frame_time_max: 最大帧渲染时间（毫秒）
    """
    fps: float = 0.0
    fps_min: float = 0.0
    fps_max: float = 0.0
    frame_time_avg: float = 0.0
    frame_time_min: float = 0.0
    frame_time_max: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """将 FPS 数据转换为字典"""
        return asdict(self)

    @property
    def unit(self) -> str:
        """返回计量单位"""
        return "fps"


@dataclass
class CPUData:
    """
    CPU 使用率指标数据容器

    包含系统级和进程级的 CPU 使用情况。
    同时记录线程数用于辅助分析 CPU 负载模式。

    Attributes:
        total: 系统总 CPU 使用率百分比 (0-100)
        process: 目标进程 CPU 使用率百分比 (0-100)
        thread_count: 目标进程的线程数
    """
    total: float = 0.0
    process: float = 0.0
    thread_count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """将 CPU 数据转换为字典"""
        return asdict(self)

    @property
    def unit(self) -> str:
        """返回计量单位"""
        return "percent"


@dataclass
class MemoryData:
    """
    内存使用指标数据容器

    包含多种内存度量方式，不同平台关注的重点不同：
    - Android: PSS 是最准确的内存占用量
    - iOS: 主要关注 RSS (phys_footprint)
    - Windows: 主要关注 RSS 和 VSS

    Attributes:
        pss: 比例分配内存 (Proportional Set Size)，Android 专用指标（MB）
        rss: 常驻内存 (Resident Set Size)，进程实际占用的物理内存（MB）
        vss: 虚拟内存 (Virtual Set Size)，进程虚拟地址空间大小（MB）
        available: 系统可用内存，仅 Android 支持（MB）
        free: 系统空闲内存（MB）
    """
    pss: float = 0.0
    rss: float = 0.0
    vss: float = 0.0
    available: float = 0.0
    free: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """将内存数据转换为字典"""
        return asdict(self)

    @property
    def unit(self) -> str:
        """返回计量单位"""
        return "MB"


@dataclass
class GPUData:
    """
    GPU 使用率指标数据容器

    包含 GPU 的负载和使用情况。
    注意：部分平台（如非越狱 iOS）无法获取 GPU 数据。

    Attributes:
        usage: GPU 使用率百分比 (0-100)
        memory: GPU 显存使用量（MB）
        temperature: GPU 温度（摄氏度）
    """
    usage: float = 0.0
    memory: float = 0.0
    temperature: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """将 GPU 数据转换为字典"""
        return asdict(self)

    @property
    def unit(self) -> str:
        """返回计量单位"""
        return "percent"


@dataclass
class NetworkData:
    """
    网络流量指标数据容器

    包含网络上行/下行的速率和总量数据。
    速率通过连续两次采样的差值除以时间间隔计算得出。

    Attributes:
        upload: 上行速率 (Bytes/s)
        download: 下行速率 (Bytes/s)
        total_upload: 自会话开始的总上行字节数
        total_download: 自会话开始的总下行字节数
    """
    upload: float = 0.0
    download: float = 0.0
    total_upload: float = 0.0
    total_download: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """将网络数据转换为字典"""
        return asdict(self)

    @property
    def unit(self) -> str:
        """返回计量单位"""
        return "B/s"


@dataclass
class TemperatureData:
    """
    温度指标数据容器

    包含设备和主要芯片的温度数据。
    温度过高可能导致降频，影响性能表现。

    Attributes:
        cpu: CPU 温度（摄氏度）
        battery: 电池温度（摄氏度）
        gpu: GPU 温度（摄氏度，部分设备支持）
    """
    cpu: float = 0.0
    battery: float = 0.0
    gpu: float = 0.0

    def to_dict(self) -> Dict[str, float]:
        """将温度数据转换为字典"""
        return asdict(self)

    @property
    def unit(self) -> str:
        """返回计量单位"""
        return "celsius"


@dataclass
class JankStats:
    """
    卡顿（Jank）统计容器

    卡顿是指帧渲染时间显著超过正常值导致的画面停顿现象。
    定义两个卡顿等级：
    - Jank: 帧时间 > 84ms（60Hz 下超过 2 倍预期帧时间 16.67ms）
    - BigJank: 帧时间 > 125ms（严重卡顿）

    Attributes:
        jank_count: Jank 帧数
        big_jank_count: BigJank 帧数
        total_frames: 总分析帧数
        jank_rate: Jank 率（百分比），即 jank_count / total_frames
        big_jank_rate: BigJank 率（百分比）
    """
    jank_count: int = 0
    big_jank_count: int = 0
    total_frames: int = 0
    jank_rate: float = 0.0
    big_jank_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """将卡顿统计转换为字典"""
        return asdict(self)

    def update(self, jank_type: Optional[str] = None) -> None:
        """
        根据检测到的卡顿类型更新统计数据

        Args:
            jank_type: 检测到的卡顿类型 ('jank', 'big_jank', 或 None)
        """
        self.total_frames += 1
        if jank_type == "big_jank":
            self.big_jank_count += 1
        elif jank_type == "jank":
            self.jank_count += 1

        if self.total_frames > 0:
            self.jank_rate = (self.jank_count / self.total_frames) * 100
            self.big_jank_rate = (self.big_jank_count / self.total_frames) * 100


@dataclass
class MetricsSnapshot:
    """
    完整指标快照

    这是 PerfSun 中最核心的数据结构，代表在某个时间点上
    所有性能指标的完整快照。它聚合了所有类型的指标数据
    到一个对象中，用于实时监控和数据持久化。

    对比 PerfDog：相当于 PerfDog 中单次采样的完整数据包。

    Attributes:
        timestamp: 快照生成时的 Unix 时间戳
        device_id: 源设备的唯一标识符
        platform: 平台类型 (android/ios/windows)
        package_name: 目标应用的包名/BundleID/进程名
        fps: FPS 指标容器
        cpu: CPU 指标容器
        memory: 内存指标容器
        gpu: GPU 指标容器
        network: 网络指标容器
        temperature: 温度指标容器
        battery_level: 电池电量百分比 (0-100)，-1 表示不可用
        jank_stats: 卡顿统计容器
        marks: 当前时间点的自定义标记列表
        metadata: 附加的上下文元数据
    """
    timestamp: float
    device_id: str
    platform: str
    package_name: str = ""
    fps: FPSData = field(default_factory=FPSData)
    cpu: CPUData = field(default_factory=CPUData)
    memory: MemoryData = field(default_factory=MemoryData)
    gpu: GPUData = field(default_factory=GPUData)
    network: NetworkData = field(default_factory=NetworkData)
    temperature: TemperatureData = field(default_factory=TemperatureData)
    battery_level: float = -1.0
    jank_stats: JankStats = field(default_factory=JankStats)
    marks: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        将 MetricsSnapshot 转换为字典

        嵌套的指标对象会递归转换为字典。

        Returns:
            包含所有快照数据的字典
        """
        return {
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "platform": self.platform,
            "package_name": self.package_name,
            "metrics": {
                "fps": self.fps.to_dict(),
                "cpu": self.cpu.to_dict(),
                "memory": self.memory.to_dict(),
                "gpu": self.gpu.to_dict(),
                "network": self.network.to_dict(),
                "temperature": self.temperature.to_dict(),
                "battery_level": self.battery_level,
            },
            "jank_stats": self.jank_stats.to_dict(),
            "marks": self.marks,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """
        序列化为 JSON 字符串

        Returns:
            快照的 JSON 字符串表示
        """
        return json.dumps(self.to_dict(), default=str)

    def to_csv_row(self) -> Dict[str, Any]:
        """
        转换为适合 CSV 导出的扁平字典

        将嵌套的指标数据展平为单层字典，
        每个指标字段独立为一列。

        Returns:
            展平的指标字段字典
        """
        return {
            "timestamp": self.timestamp,
            "device_id": self.device_id,
            "platform": self.platform,
            "package_name": self.package_name,
            "fps": self.fps.fps,
            "fps_min": self.fps.fps_min,
            "fps_max": self.fps.fps_max,
            "frame_time_avg": self.fps.frame_time_avg,
            "cpu_total": self.cpu.total,
            "cpu_process": self.cpu.process,
            "memory_pss": self.memory.pss,
            "memory_rss": self.memory.rss,
            "memory_vss": self.memory.vss,
            "gpu": self.gpu.usage,
            "network_upload": self.network.upload,
            "network_download": self.network.download,
            "jank_count": self.jank_stats.jank_count,
            "big_jank_count": self.jank_stats.big_jank_count,
            "jank_rate": self.jank_stats.jank_rate,
            "temperature_cpu": self.temperature.cpu,
            "temperature_battery": self.temperature.battery,
            "battery_level": self.battery_level,
            "marks": "|".join(self.marks) if self.marks else "",
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MetricsSnapshot":
        """
        从字典创建 MetricsSnapshot 实例

        Args:
            data: 包含快照字段的字典

        Returns:
            反序列化的 MetricsSnapshot 实例
        """
        metrics = data.get("metrics", {})

        fps_data = metrics.get("fps", {})
        cpu_data = metrics.get("cpu", {})
        memory_data = metrics.get("memory", {})
        gpu_data = metrics.get("gpu", {})
        network_data = metrics.get("network", {})
        temperature_data = metrics.get("temperature", {})
        jank_data = data.get("jank_stats", {})

        return cls(
            timestamp=data["timestamp"],
            device_id=data["device_id"],
            platform=data["platform"],
            package_name=data.get("package_name", ""),
            fps=FPSData(**fps_data) if fps_data else FPSData(),
            cpu=CPUData(**cpu_data) if cpu_data else CPUData(),
            memory=MemoryData(**memory_data) if memory_data else MemoryData(),
            gpu=GPUData(**gpu_data) if gpu_data else GPUData(),
            network=NetworkData(**network_data) if network_data else NetworkData(),
            temperature=TemperatureData(**temperature_data) if temperature_data else TemperatureData(),
            battery_level=metrics.get("battery_level", -1.0),
            jank_stats=JankStats(**jank_data) if jank_data else JankStats(),
            marks=data.get("marks", []),
            metadata=data.get("metadata", {}),
        )

    @property
    def datetime(self) -> datetime:
        """
        获取时间戳对应的 datetime 对象

        Returns:
            表示快照时间的 datetime 对象
        """
        return datetime.fromtimestamp(self.timestamp)

    def get_summary(self) -> Dict[str, Any]:
        """
        获取指标摘要信息

        返回当前快照中所有非零指标的概要，
        便于快速了解设备性能状态。

        Returns:
            指标摘要字典
        """
        summary = {}
        if self.fps.fps > 0:
            summary["fps"] = round(self.fps.fps, 1)
        if self.cpu.total > 0:
            summary["cpu"] = round(self.cpu.total, 1)
        if self.memory.rss > 0:
            summary["memory_mb"] = round(self.memory.rss, 1)
        if self.gpu.usage > 0:
            summary["gpu"] = round(self.gpu.usage, 1)
        if self.battery_level >= 0:
            summary["battery"] = round(self.battery_level, 1)
        summary["janks"] = self.jank_stats.jank_count + self.jank_stats.big_jank_count
        return summary


@dataclass
class Mark:
    """
    自定义标记

    用于在性能采集过程中标记特定事件，类似于 PerfDog 的"打点"功能。
    标记会出现在时间轴上，方便将性能数据与特定场景关联分析。

    使用场景：
    - 场景切换（如进入游戏副本、加载新地图）
    - 用户操作（如点击按钮、触发动画）
    - 业务事件（如广告展示、支付流程）

    Attributes:
        timestamp: 标记添加时的 Unix 时间戳
        name: 标记名称/标签
        mark_type: 标记类型 (custom/scene_change/user_action/network_request 等)
        session_id: 标记所属的录制会话 ID
        metadata: 附加的上下文信息
    """
    timestamp: float
    name: str
    mark_type: str = "custom"
    session_id: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """
        将 Mark 转换为字典格式

        Returns:
            包含所有字段的字典
        """
        return {
            "timestamp": self.timestamp,
            "name": self.name,
            "mark_type": self.mark_type,
            "session_id": self.session_id,
            "metadata": self.metadata,
        }

    def to_json(self) -> str:
        """
        序列化为 JSON 字符串

        Returns:
            Mark 的 JSON 字符串表示
        """
        return json.dumps(self.to_dict())


@dataclass
class SessionInfo:
    """
    录制会话信息

    记录一次性能采集会话的完整信息，包括：
    - 会话标识和关联的设备/应用信息
    - 开始/结束时间和持续时长
    - 采集的样本数量和当前状态

    Attributes:
        id: 会话唯一标识符 (UUID)
        device_id: 设备标识符
        platform: 平台类型 (android/ios/windows)
        package_name: 目标应用的包名/BundleID/进程名
        start_time: 会话开始时的 Unix 时间戳
        end_time: 会话结束时的 Unix 时间戳（进行中则为 None）
        duration: 会话持续时长（秒）
        sample_count: 已采集的样本数量
        status: 会话状态 (recording/paused/completed)
    """
    id: str
    device_id: str
    platform: str
    package_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: float = 0.0
    sample_count: int = 0
    status: str = "recording"

    def to_dict(self) -> Dict[str, Any]:
        """
        将 SessionInfo 转换为字典

        Returns:
            包含所有会话信息的字典
        """
        return asdict(self)

    def is_active(self) -> bool:
        """
        检查会话是否处于活跃状态

        Returns:
            如果会话状态为 recording 或 paused 则返回 True
        """
        return self.status in ("recording", "paused")

    def update_duration(self) -> None:
        """更新会话持续时长"""
        if self.end_time is not None:
            self.duration = self.end_time - self.start_time
        else:
            self.duration = datetime.now().timestamp() - self.start_time

    def get_start_datetime(self) -> datetime:
        """
        获取会话开始时间的 datetime 对象

        Returns:
            表示会话开始时间的 datetime
        """
        return datetime.fromtimestamp(self.start_time)

    def get_end_datetime(self) -> Optional[datetime]:
        """
        获取会话结束时间的 datetime 对象

        Returns:
            表示会话结束时间的 datetime，未结束时返回 None
        """
        if self.end_time:
            return datetime.fromtimestamp(self.end_time)
        return None
