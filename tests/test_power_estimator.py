"""
PerfSun 功耗估算器单元测试

测试功耗估算功能：
- 不同设备类型的功耗参数
- 基于快照的功耗估算
- 基于指标字典的功耗估算
- 平均功耗和累计能耗计算
"""

import pytest
import time
from perfsun.utils.power_estimator import (
    PowerEstimator,
    PowerEstimate,
    PowerModelParams,
    DeviceType,
)
from perfsun.core.data_point import (
    MetricsSnapshot, FPSData, CPUData, MemoryData,
    GPUData, NetworkData, TemperatureData, JankStats,
)


class TestDeviceType:
    """DeviceType 枚举测试类"""

    def test_device_type_values(self):
        """测试设备类型枚举值"""
        assert DeviceType.PHONE.value == "phone"
        assert DeviceType.TABLET.value == "tablet"
        assert DeviceType.LAPTOP.value == "laptop"
        assert DeviceType.DESKTOP.value == "desktop"
        assert len(set(DeviceType)) == 4


class TestPowerModelParams:
    """PowerModelParams 测试类"""

    def test_default_params(self):
        """测试默认参数"""
        params = PowerModelParams()
        assert params.cpu_power_per_core == 0.5
        assert params.gpu_power == 2.0
        assert params.screen_power == 1.0
        assert params.network_power == 0.5
        assert params.base_power == 0.3
        assert params.thermal_coefficient == 0.02

    def test_custom_params(self):
        """测试自定义参数"""
        params = PowerModelParams(
            cpu_power_per_core=1.0,
            gpu_power=3.0,
            screen_power=2.0,
        )
        assert params.cpu_power_per_core == 1.0
        assert params.gpu_power == 3.0
        assert params.screen_power == 2.0
        assert params.base_power == 0.3  # 默认值保持不变

    def test_to_dict(self):
        """测试参数转换为字典"""
        params = PowerModelParams()
        data = params.to_dict()
        assert data["cpu_power_per_core"] == 0.5
        assert "gpu_power" in data
        assert "thermal_coefficient" in data
        assert len(data) == 6


class TestPowerEstimate:
    """PowerEstimate 测试类"""

    def test_estimate_creation(self):
        """测试功耗估算结果创建"""
        estimate = PowerEstimate(
            timestamp=1000.0,
            total_power=2.5,
            cpu_power=1.0,
            gpu_power=0.8,
            screen_power=0.5,
            network_power=0.1,
            base_power=0.2,
            battery_drain_rate=5.0,
            temperature=42.0,
        )
        assert estimate.total_power == 2.5
        assert estimate.battery_drain_rate == 5.0

    def test_total_power_mw(self):
        """测试总功耗毫瓦转换"""
        estimate = PowerEstimate(timestamp=1000.0, total_power=2.5)
        assert estimate.total_power_mw == 2500.0

    def test_to_dict(self):
        """测试转换为字典"""
        estimate = PowerEstimate(
            timestamp=1000.0,
            total_power=2.543,
            cpu_power=1.0,
            battery_drain_rate=5.123,
            temperature=42.5,
        )
        data = estimate.to_dict()
        assert data["total_power"] == 2.543
        assert data["battery_drain_rate"] == 5.12  # 四舍五入到2位
        assert data["temperature"] == 42.5


class TestPowerEstimator:
    """PowerEstimator 测试类"""

    def setup_method(self):
        """每个测试方法执行前的 setup"""
        self.estimator = PowerEstimator(
            device_type=DeviceType.PHONE,
            cpu_cores=8,
            battery_capacity=4000,
        )

    def test_initialization(self):
        """测试初始化"""
        assert self.estimator.device_type == DeviceType.PHONE
        assert self.estimator.cpu_cores == 8
        assert self.estimator.battery_capacity == 4000
        assert len(self.estimator.estimates) == 0

    def test_phone_params(self):
        """测试手机功耗参数"""
        assert self.estimator.params.cpu_power_per_core == 0.4
        assert self.estimator.params.gpu_power == 1.5
        assert self.estimator.params.screen_power == 0.8

    def test_tablet_params(self):
        """测试平板功耗参数"""
        estimator = PowerEstimator(device_type=DeviceType.TABLET)
        assert estimator.params.cpu_power_per_core == 0.5

    def test_laptop_params(self):
        """测试笔记本功耗参数"""
        estimator = PowerEstimator(device_type=DeviceType.LAPTOP)
        assert estimator.params.cpu_power_per_core == 1.0
        assert estimator.params.gpu_power == 3.0

    def test_desktop_params(self):
        """测试台式机功耗参数"""
        estimator = PowerEstimator(device_type=DeviceType.DESKTOP)
        assert estimator.params.cpu_power_per_core == 2.0
        assert estimator.params.gpu_power == 5.0

    def test_estimate_from_snapshot(self):
        """测试基于快照的功耗估算"""
        snapshot = MetricsSnapshot(
            timestamp=1000.0,
            device_id="test",
            platform="android",
            fps=FPSData(fps=60.0),
            cpu=CPUData(total=50.0, process=20.0),
            memory=MemoryData(pss=512.0),
            gpu=GPUData(usage=30.0),
            network=NetworkData(upload=1024.0, download=2048.0),
            temperature=TemperatureData(cpu=45.0, battery=35.0),
            jank_stats=JankStats(),
        )

        estimate = self.estimator.estimate_from_snapshot(snapshot)

        assert estimate.total_power > 0
        assert estimate.cpu_power > 0
        assert estimate.gpu_power > 0
        assert estimate.screen_power > 0
        assert estimate.temperature == 45.0
        assert len(self.estimator.estimates) == 1

    def test_estimate_from_metrics(self):
        """测试基于指标字典的功耗估算"""
        metrics = {
            "cpu_total": 60.0,
            "gpu": 40.0,
            "network_upload": 2048.0,
            "network_download": 4096.0,
            "temperature_cpu": 50.0,
        }

        estimate = self.estimator.estimate_from_metrics(metrics)

        assert estimate.total_power > 0
        assert estimate.cpu_power > 0
        assert estimate.gpu_power > 0
        assert len(self.estimator.estimates) == 1

    def test_idle_power(self):
        """测试空闲状态功耗"""
        snapshot = MetricsSnapshot(
            timestamp=1000.0,
            device_id="test",
            platform="android",
            cpu=CPUData(total=0.0),
            gpu=GPUData(usage=0.0),
            network=NetworkData(upload=0.0, download=0.0),
            temperature=TemperatureData(cpu=30.0),
        )

        estimate = self.estimator.estimate_from_snapshot(snapshot)
        # 空闲状态只有屏幕功耗 + 基础功耗
        expected_base = (0.8 * 0.8 + 0.2)  # screen*0.8 + base
        assert estimate.total_power == pytest.approx(expected_base, rel=0.5)

    def test_full_load_power(self):
        """测试满载功耗"""
        snapshot = MetricsSnapshot(
            timestamp=1000.0,
            device_id="test",
            platform="android",
            cpu=CPUData(total=100.0),
            gpu=GPUData(usage=100.0),
            network=NetworkData(upload=500000.0, download=500000.0),
            temperature=TemperatureData(cpu=60.0),
        )

        estimate = self.estimator.estimate_from_snapshot(snapshot)

        # 满载功耗应明显高于空闲
        assert estimate.total_power > 1.0
        assert estimate.cpu_power > 2.0  # 100% * 8核 * 0.4W
        assert estimate.gpu_power == 1.5  # 100% * 1.5W

    def test_battery_drain_calculation(self):
        """测试电池消耗速率计算"""
        snapshot = MetricsSnapshot(
            timestamp=1000.0,
            device_id="test",
            platform="android",
            cpu=CPUData(total=50.0),
            gpu=GPUData(usage=30.0),
        )

        estimate = self.estimator.estimate_from_snapshot(snapshot)

        # 电池消耗速率应为正值
        assert estimate.battery_drain_rate > 0

        # 更大功耗应导致更高消耗速率
        high_load_snapshot = MetricsSnapshot(
            timestamp=1001.0,
            device_id="test",
            platform="android",
            cpu=CPUData(total=100.0),
            gpu=GPUData(usage=100.0),
        )
        high_estimate = self.estimator.estimate_from_snapshot(high_load_snapshot)
        assert high_estimate.battery_drain_rate > estimate.battery_drain_rate

    def test_thermal_effect(self):
        """测试温度影响"""
        cool_snapshot = MetricsSnapshot(
            timestamp=1000.0,
            device_id="test",
            platform="android",
            cpu=CPUData(total=50.0),
            gpu=GPUData(usage=30.0),
            temperature=TemperatureData(cpu=35.0),
        )

        hot_snapshot = MetricsSnapshot(
            timestamp=1001.0,
            device_id="test",
            platform="android",
            cpu=CPUData(total=50.0),
            gpu=GPUData(usage=30.0),
            temperature=TemperatureData(cpu=80.0),  # 高温
        )

        cool_estimate = self.estimator.estimate_from_snapshot(cool_snapshot)
        hot_estimate = self.estimator.estimate_from_snapshot(hot_snapshot)

        # 同等负载下，高温导致更高功耗
        assert hot_estimate.total_power > cool_estimate.total_power

    def test_average_power(self):
        """测试平均功耗计算"""
        for i in range(5):
            snapshot = MetricsSnapshot(
                timestamp=float(1000 + i),
                device_id="test",
                platform="android",
                cpu=CPUData(total=float(10 + i * 10)),
            )
            self.estimator.estimate_from_snapshot(snapshot)

        avg = self.estimator.get_average_power(window_size=3)
        assert avg > 0

        # 空列表时返回0
        empty_estimator = PowerEstimator()
        assert empty_estimator.get_average_power() == 0.0

    def test_total_energy(self):
        """测试累计能耗计算"""
        # 添加两个采样点计算能量
        snapshot1 = MetricsSnapshot(timestamp=1000.0, device_id="test", platform="android", cpu=CPUData(total=50.0))
        snapshot2 = MetricsSnapshot(timestamp=1001.0, device_id="test", platform="android", cpu=CPUData(total=60.0))

        self.estimator.estimate_from_snapshot(snapshot1)
        self.estimator.estimate_from_snapshot(snapshot2)

        energy = self.estimator.get_total_energy()
        assert energy > 0

        # 单个采样点返回0
        single_estimator = PowerEstimator()
        snapshot3 = MetricsSnapshot(timestamp=1000.0, device_id="test", platform="android", cpu=CPUData(total=50.0))
        single_estimator.estimate_from_snapshot(snapshot3)
        assert single_estimator.get_total_energy() == 0.0

    def test_reset(self):
        """测试重置"""
        snapshot = MetricsSnapshot(timestamp=1000.0, device_id="test", platform="android", cpu=CPUData(total=50.0))
        self.estimator.estimate_from_snapshot(snapshot)
        assert len(self.estimator.estimates) == 1

        self.estimator.reset()
        assert len(self.estimator.estimates) == 0
        assert self.estimator.get_average_power() == 0.0

    def test_set_device_type(self):
        """测试设置设备类型"""
        self.estimator.set_device_type(DeviceType.DESKTOP)
        assert self.estimator.device_type == DeviceType.DESKTOP
        assert self.estimator.params.cpu_power_per_core == 2.0

    def test_get_summary(self):
        """测试获取摘要"""
        # 无数据时
        summary = self.estimator.get_summary()
        assert summary["status"] == "no_data"

        # 有数据时
        snapshot = MetricsSnapshot(timestamp=1000.0, device_id="test", platform="android", cpu=CPUData(total=50.0))
        self.estimator.estimate_from_snapshot(snapshot)

        summary = self.estimator.get_summary()
        assert summary["device_type"] == "phone"
        assert "avg_power_w" in summary
        assert "max_power_w" in summary
        assert "total_energy_j" in summary
        assert "sample_count" in summary
        assert summary["sample_count"] == 1


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
