"""
PerfSun 功耗估算模块

本模块实现设备功耗的估算功能，对标 PerfDog 的电量/功耗分析能力。
由于非侵入式工具无法直接测量设备功耗，采用基于性能指标的估算模型。

功耗估算模型基于以下因素：
1. CPU 使用率：CPU 是主要的功耗来源
2. GPU 使用率：GPU 渲染同样消耗大量电能
3. 屏幕亮度：屏幕是移动设备最大的耗电部件
4. 网络活动：无线通信模块的功耗
5. 温度影响：高温会增加漏电流

注意：估算值仅供参考，精确功耗需要硬件测量设备。
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum
import logging
import time

from perfsun.core.data_point import MetricsSnapshot


logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """设备类型枚举，不同设备的功耗参数不同"""
    PHONE = "phone"           # 手机
    TABLET = "tablet"         # 平板
    LAPTOP = "laptop"         # 笔记本
    DESKTOP = "desktop"       # 台式机


@dataclass
class PowerModelParams:
    """
    功耗模型参数

    定义不同设备类型和平台的功耗估算参数。
    这些参数基于典型设备的功耗特性统计得出。

    Attributes:
        cpu_power_per_core: 每核心CPU满载功耗（瓦）
        gpu_power: GPU满载功耗（瓦）
        screen_power: 屏幕典型功耗（瓦）
        network_power: 网络模块典型功耗（瓦）
        base_power: 基础功耗（瓦），系统运行本身消耗
        thermal_coefficient: 温度影响系数
    """
    cpu_power_per_core: float = 0.5      # 每核心 CPU 满载功耗（W）
    gpu_power: float = 2.0               # GPU 满载功耗（W）
    screen_power: float = 1.0            # 屏幕典型功耗（W）
    network_power: float = 0.5           # 网络模块功耗（W）
    base_power: float = 0.3              # 基础功耗（W）
    thermal_coefficient: float = 0.02    # 温度影响系数

    def to_dict(self) -> Dict[str, float]:
        """转换为字典"""
        return {
            "cpu_power_per_core": self.cpu_power_per_core,
            "gpu_power": self.gpu_power,
            "screen_power": self.screen_power,
            "network_power": self.network_power,
            "base_power": self.base_power,
            "thermal_coefficient": self.thermal_coefficient,
        }


@dataclass
class PowerEstimate:
    """
    功耗估算结果

    Attributes:
        timestamp: 估算时间戳
        total_power: 总功耗（瓦）
        cpu_power: CPU 功耗（瓦）
        gpu_power: GPU 功耗（瓦）
        screen_power: 屏幕功耗（瓦）
        network_power: 网络功耗（瓦）
        base_power: 基础功耗（瓦）
        battery_drain_rate: 电池消耗速率（% / 小时）
        temperature: 当前温度（摄氏度）
    """
    timestamp: float
    total_power: float = 0.0
    cpu_power: float = 0.0
    gpu_power: float = 0.0
    screen_power: float = 0.0
    network_power: float = 0.0
    base_power: float = 0.0
    battery_drain_rate: float = 0.0
    temperature: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "timestamp": self.timestamp,
            "total_power": round(self.total_power, 3),
            "cpu_power": round(self.cpu_power, 3),
            "gpu_power": round(self.gpu_power, 3),
            "screen_power": round(self.screen_power, 3),
            "network_power": round(self.network_power, 3),
            "base_power": round(self.base_power, 3),
            "battery_drain_rate": round(self.battery_drain_rate, 2),
            "temperature": round(self.temperature, 1),
        }

    @property
    def total_power_mw(self) -> float:
        """
        获取总功耗（毫瓦）

        Returns:
            总功耗（mW）
        """
        return self.total_power * 1000


class PowerEstimator:
    """
    功耗估算器

    基于性能指标估算设备功耗。
    对标 PerfDog 的功耗分析功能。

    使用线性模型结合多个性能指标估算功耗：
    - CPU 功耗 = CPU 使用率 × CPU 核心数 × cpu_power_per_core
    - GPU 功耗 = GPU 使用率 × gpu_power
    - 网络功耗 = 网络活跃度 × network_power
    - 基础功耗 = base_power

    Attributes:
        device_type: 设备类型
        cpu_cores: CPU 核心数
        params: 功耗模型参数
        estimates: 历史估算记录
    """

    # 不同设备类型的默认参数
    DEVICE_PARAMS = {
        DeviceType.PHONE: PowerModelParams(
            cpu_power_per_core=0.4,
            gpu_power=1.5,
            screen_power=0.8,
            network_power=0.3,
            base_power=0.2,
        ),
        DeviceType.TABLET: PowerModelParams(
            cpu_power_per_core=0.5,
            gpu_power=2.0,
            screen_power=1.5,
            network_power=0.4,
            base_power=0.3,
        ),
        DeviceType.LAPTOP: PowerModelParams(
            cpu_power_per_core=1.0,
            gpu_power=3.0,
            screen_power=2.0,
            network_power=0.5,
            base_power=0.5,
        ),
        DeviceType.DESKTOP: PowerModelParams(
            cpu_power_per_core=2.0,
            gpu_power=5.0,
            screen_power=3.0,
            network_power=0.5,
            base_power=1.0,
        ),
    }

    def __init__(
        self,
        device_type: DeviceType = DeviceType.PHONE,
        cpu_cores: int = 8,
        battery_capacity: float = 4000,
        custom_params: Optional[PowerModelParams] = None,
    ):
        """
        初始化功耗估算器

        Args:
            device_type: 设备类型，用于选择默认参数
            cpu_cores: CPU 核心数
            battery_capacity: 电池容量（mAh）
            custom_params: 自定义功耗模型参数，覆盖默认值
        """
        self.device_type = device_type
        self.cpu_cores = cpu_cores
        self.battery_capacity = battery_capacity  # mAh
        self.params = custom_params or self.DEVICE_PARAMS.get(device_type, PowerModelParams())
        self.estimates: List[PowerEstimate] = []

        logger.info(
            f"功耗估算器初始化完成，设备类型: {device_type.value}, "
            f"核心数: {cpu_cores}, 电池容量: {battery_capacity}mAh"
        )

    def estimate_from_snapshot(self, snapshot: MetricsSnapshot) -> PowerEstimate:
        """
        基于指标快照估算功耗

        Args:
            snapshot: 性能指标快照

        Returns:
            功耗估算结果
        """
        # CPU 功耗
        cpu_usage = snapshot.cpu.total / 100.0 if snapshot.cpu.total > 0 else 0
        cpu_power = cpu_usage * self.cpu_cores * self.params.cpu_power_per_core

        # GPU 功耗
        gpu_usage = snapshot.gpu.usage / 100.0
        gpu_power = gpu_usage * self.params.gpu_power

        # 屏幕功耗（屏幕常亮采集，按 80% 亮度估算）
        screen_power = self.params.screen_power * 0.8

        # 网络功耗（基于网络活跃度）
        net_activity = min(1.0, (snapshot.network.upload + snapshot.network.download) / 1_000_000)
        network_power = net_activity * self.params.network_power

        # 温度影响
        temp = snapshot.temperature.cpu
        thermal_factor = 1.0 + max(0, (temp - 40)) * self.params.thermal_coefficient if temp > 0 else 1.0

        # 总功耗
        base_power = self.params.base_power
        total_power = (cpu_power + gpu_power + screen_power + network_power + base_power) * thermal_factor

        # 电池消耗速率（%/小时）
        if self.battery_capacity > 0:
            voltage = 3.7  # 典型锂电池电压
            power_to_current = total_power / voltage  # 电流（安培）
            drain_current_ma = power_to_current * 1000  # 电流（毫安）
            battery_drain_rate = (drain_current_ma / self.battery_capacity) * 100  # %/小时
        else:
            battery_drain_rate = 0.0

        estimate = PowerEstimate(
            timestamp=snapshot.timestamp,
            total_power=total_power,
            cpu_power=cpu_power,
            gpu_power=gpu_power,
            screen_power=screen_power,
            network_power=network_power,
            base_power=base_power,
            battery_drain_rate=battery_drain_rate,
            temperature=temp,
        )

        self.estimates.append(estimate)
        return estimate

    def estimate_from_metrics(self, metrics: Dict[str, float]) -> PowerEstimate:
        """
        基于指标字典估算功耗

        Args:
            metrics: 包含 cpu_total、gpu、network_upload 等指标的字典

        Returns:
            功耗估算结果
        """
        cpu_usage = (metrics.get("cpu_total", 0) or 0) / 100.0
        gpu_usage = (metrics.get("gpu", 0) or 0) / 100.0
        net_up = metrics.get("network_upload", 0) or 0
        net_down = metrics.get("network_download", 0) or 0
        temp = metrics.get("temperature_cpu", 0) or 0

        cpu_power = cpu_usage * self.cpu_cores * self.params.cpu_power_per_core
        gpu_power = gpu_usage * self.params.gpu_power
        screen_power = self.params.screen_power * 0.8
        net_activity = min(1.0, (net_up + net_down) / 1_000_000)
        network_power = net_activity * self.params.network_power
        thermal_factor = 1.0 + max(0, (temp - 40)) * self.params.thermal_coefficient if temp > 0 else 1.0
        base_power = self.params.base_power
        total_power = (cpu_power + gpu_power + screen_power + network_power + base_power) * thermal_factor

        if self.battery_capacity > 0:
            voltage = 3.7
            drain_current_ma = (total_power / voltage) * 1000
            battery_drain_rate = (drain_current_ma / self.battery_capacity) * 100
        else:
            battery_drain_rate = 0.0

        estimate = PowerEstimate(
            timestamp=time.time(),
            total_power=total_power,
            cpu_power=cpu_power,
            gpu_power=gpu_power,
            screen_power=screen_power,
            network_power=network_power,
            base_power=base_power,
            battery_drain_rate=battery_drain_rate,
            temperature=temp,
        )

        self.estimates.append(estimate)
        return estimate

    def get_average_power(self, window_size: int = 10) -> float:
        """
        获取最近 N 次估算的平均功耗

        Args:
            window_size: 窗口大小

        Returns:
            平均功耗（瓦）
        """
        if not self.estimates:
            return 0.0

        recent = self.estimates[-window_size:]
        return sum(e.total_power for e in recent) / len(recent)

    def get_total_energy(self) -> float:
        """
        获取累计能耗（焦耳）

        根据所有估算记录计算总能耗。

        Returns:
            累计能耗（焦耳，J）
        """
        if len(self.estimates) < 2:
            return 0.0

        total_energy = 0.0
        for i in range(1, len(self.estimates)):
            dt = self.estimates[i].timestamp - self.estimates[i - 1].timestamp
            avg_power = (self.estimates[i].total_power + self.estimates[i - 1].total_power) / 2
            total_energy += avg_power * dt  # 能量 = 功率 × 时间（焦耳）

        return total_energy

    def reset(self) -> None:
        """
        重置估算记录
        """
        self.estimates.clear()

    def set_device_type(self, device_type: DeviceType) -> None:
        """
        设置设备类型并更新参数

        Args:
            device_type: 设备类型
        """
        self.device_type = device_type
        self.params = self.DEVICE_PARAMS.get(device_type, PowerModelParams())
        logger.info(f"设备类型已更新为: {device_type.value}")

    def get_summary(self) -> Dict[str, Any]:
        """
        获取功耗分析摘要

        Returns:
            包含功耗分析信息的字典
        """
        if not self.estimates:
            return {"status": "no_data"}

        recent_powers = [e.total_power for e in self.estimates]
        return {
            "device_type": self.device_type.value,
            "current_power_w": round(self.estimates[-1].total_power, 3),
            "current_power_mw": round(self.estimates[-1].total_power_mw, 1),
            "avg_power_w": round(sum(recent_powers) / len(recent_powers), 3),
            "max_power_w": round(max(recent_powers), 3),
            "min_power_w": round(min(recent_powers), 3),
            "avg_battery_drain": round(
                sum(e.battery_drain_rate for e in self.estimates) / len(self.estimates), 2
            ),
            "total_energy_j": round(self.get_total_energy(), 2),
            "total_energy_mah": round(self.get_total_energy() / (3.7 * 3.6), 2),  # J → mAh 估算
            "sample_count": len(self.estimates),
        }
