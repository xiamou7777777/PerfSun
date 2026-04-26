"""
PerfSun 采集器基础接口和配置定义

本模块定义了所有平台采集器的抽象基类和通用配置，
所有平台特定的采集器（Android/iOS/Windows）都应实现 Collectible 接口。

遵循面向接口编程原则，使新增平台支持变得简单。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Callable, Dict, Any, List
from enum import Enum
import logging


logger = logging.getLogger(__name__)


class Platform(Enum):
    """
    支持的平台类型枚举

    用于标识采集器运行的平台环境。
    """
    ANDROID = "android"   # Android 平台
    IOS = "ios"           # iOS 平台
    WINDOWS = "windows"   # Windows 平台
    UNKNOWN = "unknown"   # 未知平台


@dataclass
class CollectorConfig:
    """
    采集器配置类

    定义了采集器运行所需的所有配置参数。
    包括目标信息、采集频率、指标开关等。

    Attributes:
        platform: 目标平台类型
        package_name: 目标应用的包名（Android）/ BundleID（iOS）/ 进程名（Windows）
        interval: 采样间隔（秒），默认 1.0 秒
        enable_fps: 是否采集 FPS 帧率
        enable_cpu: 是否采集 CPU 使用率
        enable_memory: 是否采集内存使用量
        enable_gpu: 是否采集 GPU 使用率
        enable_network: 是否采集网络流量
        enable_temperature: 是否采集温度
        device_id: 设备 ID
        adb_path: ADB 可执行文件路径（Android 专用）
        frame_window_size: 帧率平滑窗口大小
        jank_threshold_ms: Jank 判定阈值（毫秒）
        big_jank_threshold_ms: BigJank 判定阈值（毫秒）
    """
    platform: str = "android"
    package_name: str = ""
    interval: float = 1.0
    enable_fps: bool = True
    enable_cpu: bool = True
    enable_memory: bool = True
    enable_gpu: bool = True
    enable_network: bool = True
    enable_temperature: bool = True
    device_id: str = ""
    adb_path: str = "adb"
    frame_window_size: int = 5
    jank_threshold_ms: float = 84.0
    big_jank_threshold_ms: float = 125.0

    def to_dict(self) -> Dict[str, Any]:
        """将配置转换为字典"""
        return {
            "platform": self.platform,
            "package_name": self.package_name,
            "interval": self.interval,
            "enable_fps": self.enable_fps,
            "enable_cpu": self.enable_cpu,
            "enable_memory": self.enable_memory,
            "enable_gpu": self.enable_gpu,
            "enable_network": self.enable_network,
            "enable_temperature": self.enable_temperature,
            "device_id": self.device_id,
        }

    def get_disabled_metrics(self) -> List[str]:
        """
        获取已禁用的指标列表

        Returns:
            被禁用的指标名称列表
        """
        disabled = []
        if not self.enable_fps:
            disabled.append("fps")
        if not self.enable_cpu:
            disabled.append("cpu")
        if not self.enable_memory:
            disabled.append("memory")
        if not self.enable_gpu:
            disabled.append("gpu")
        if not self.enable_network:
            disabled.append("network")
        if not self.enable_temperature:
            disabled.append("temperature")
        return disabled


class Collectible(ABC):
    """
    性能采集器抽象基类

    所有平台特定的采集器必须实现此接口。
    定义了采集器的生命周期方法和关键行为。

    核心生命周期：
    1. 初始化（__init__）→ 2. 启动采集（start）→ 3. 数据采集（collect）
    → 4. 停止采集（stop）→ 5. 清理

    对比 PerfDog：相当于 PerfDog 中各个平台的采集引擎插件。

    Attributes:
        config: 采集器配置
        _is_running: 运行状态标志
        _on_sample_callback: 采样回调函数
    """

    def __init__(self, config: CollectorConfig):
        """
        初始化采集器

        Args:
            config: 采集器配置
        """
        self.config = config
        self._is_running = False
        self._on_sample_callback: Optional[Callable] = None
        logger.debug(f"{self.__class__.__name__} 初始化完成，配置: {config}")

    @property
    def is_running(self) -> bool:
        """
        检查采集器是否正在运行

        Returns:
            是否正在运行
        """
        return self._is_running

    @property
    def on_sample(self) -> Optional[Callable]:
        """
        获取采样回调函数

        Returns:
            回调函数
        """
        return self._on_sample_callback

    @on_sample.setter
    def on_sample(self, callback: Callable) -> None:
        """
        设置采样回调函数

        每次采集到数据时，都会调用此回调将数据传递给上层管理器。

        Args:
            callback: 回调函数，接收 MetricsSnapshot 参数
        """
        self._on_sample_callback = callback

    @abstractmethod
    def start(self) -> None:
        """
        开始采集数据

        子类应实现具体的启动逻辑，包括：
        - 建立设备连接
        - 初始化采集环境
        - 启动采集线程或定时器
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        停止采集数据

        子类应实现具体的停止逻辑，包括：
        - 停止采集线程或定时器
        - 清理采集环境
        - 关闭设备连接
        """
        pass

    @abstractmethod
    def collect(self) -> bool:
        """
        执行一次数据采集

        Returns:
            采集是否成功
        """
        pass

    @abstractmethod
    def reconnect(self) -> bool:
        """
        尝试重新连接设备

        当设备断开连接时调用此方法尝试重连。

        Returns:
            重连是否成功
        """
        pass

    @abstractmethod
    def get_device_info(self) -> Dict[str, Any]:
        """
        获取设备信息

        Returns:
            设备信息字典，包含：
            - device_id: 设备 ID
            - platform: 平台类型
            - model: 设备型号
            - os_version: 系统版本
            - manufacturer: 制造商
        """
        pass

    @abstractmethod
    def is_connected(self) -> bool:
        """
        检查设备是否已连接

        Returns:
            是否已连接
        """
        pass

    def get_supported_metrics(self) -> List[str]:
        """
        获取采集器支持的指标列表

        根据配置中启用的指标类型返回对应的指标标识符。

        Returns:
            支持的指标类型列表
        """
        metrics = []
        if self.config.enable_fps:
            metrics.extend(["fps", "frame_time"])
        if self.config.enable_cpu:
            metrics.extend(["cpu_total", "cpu_process"])
        if self.config.enable_memory:
            metrics.extend(["memory_pss", "memory_rss", "memory_vss"])
        if self.config.enable_gpu:
            metrics.append("gpu")
        if self.config.enable_network:
            metrics.extend(["network_upload", "network_download"])
        if self.config.enable_temperature:
            metrics.extend(["temperature_cpu", "temperature_battery"])
        return metrics

    def validate_config(self) -> bool:
        """
        验证配置是否有效

        检查各项配置参数的合法性。

        Returns:
            配置是否有效
        """
        if self.config.interval <= 0:
            logger.error("无效的采样间隔: 必须为正数")
            return False

        if self.config.interval < 0.1:
            logger.warning(f"采样间隔 {self.config.interval}s 非常小，可能影响设备性能")

        if not self.config.package_name:
            logger.warning("包名为空，将采集系统级指标而非进程级指标")

        return True


class DeviceInfo:
    """
    设备信息数据类

    存储采集目标的设备信息，用于识别和展示。

    Attributes:
        device_id: 设备唯一标识符
        platform: 平台类型 (android/ios/windows)
        model: 设备型号
        os_version: 操作系统版本
        manufacturer: 制造商
        sdk_version: SDK 版本（Android 专用）
        bundle_id: 应用 BundleID（iOS 专用）
    """

    def __init__(
        self,
        device_id: str,
        platform: str,
        model: str = "",
        os_version: str = "",
        manufacturer: str = "",
        **kwargs
    ):
        self.device_id = device_id
        self.platform = platform
        self.model = model
        self.os_version = os_version
        self.manufacturer = manufacturer
        self.sdk_version = kwargs.get("sdk_version", "")
        self.bundle_id = kwargs.get("bundle_id", "")

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "device_id": self.device_id,
            "platform": self.platform,
            "model": self.model,
            "os_version": self.os_version,
            "manufacturer": self.manufacturer,
            "sdk_version": self.sdk_version,
            "bundle_id": self.bundle_id,
        }

    def __repr__(self) -> str:
        return f"DeviceInfo({self.platform}, {self.device_id}, {self.model})"


class CollectorError(Exception):
    """
    采集器异常基类

    所有采集器相关异常的基类。
    """
    pass


class DeviceDisconnectedError(CollectorError):
    """
    设备断开连接异常

    当采集过程中设备断开连接时抛出。
    """
    def __init__(self, message: str = "设备断开连接"):
        super().__init__(message)


class PermissionDeniedError(CollectorError):
    """
    权限被拒绝异常

    当设备未授权或权限不足时抛出。
    例如：Android 设备未授权 USB 调试。
    """
    def __init__(self, message: str = "权限被拒绝"):
        super().__init__(message)


class UnsupportedMetricError(CollectorError):
    """
    不支持的指标异常

    当尝试采集当前平台不支持的指标时抛出。

    Attributes:
        metric: 不支持的指标名称
        platform: 当前平台
    """
    def __init__(self, metric: str, platform: str):
        self.metric = metric
        self.platform = platform
        super().__init__(f"指标 '{metric}' 在平台 '{platform}' 上不受支持")


class CollectorTimeoutError(CollectorError):
    """
    采集超时异常

    当采集操作超时时抛出。
    """
    def __init__(self, message: str = "采集操作超时"):
        super().__init__(message)


class CollectorInitError(CollectorError):
    """
    采集器初始化异常

    当采集器初始化失败时抛出。
    例如：ADB 未安装、设备驱动缺失等。
    """
    def __init__(self, message: str = "采集器初始化失败"):
        super().__init__(message)
