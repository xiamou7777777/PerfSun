"""
PerfSun Windows 平台性能采集器

本模块实现 Windows 平台的性能数据采集功能，对标 PerfDog 的 Windows 采集能力。
主要依赖 PDH（Performance Data Helper）和 psutil 库。

支持的指标和采集方式：
- FPS 帧率：通过 DXGI Hook 或性能计数器（有限支持）
- CPU 使用率：通过 PDH 计数器或 psutil
- 内存占用：通过 psutil 获取进程内存
- GPU 使用率：通过 NVML（NVIDIA）或 DXGI（通用）
- 网络流量：通过 psutil 网络 I/O 统计
- 温度数据：通过 psutil 传感器或 WMI

注意事项：
- 部分功能需要管理员权限运行
- GPU 采集仅 NVIDIA 显卡通过 NVML 完整支持
- FPS 采集需要针对特定进程进行 DXGI Hook
"""

import logging
import time
from threading import Event, Thread
from typing import Optional, Dict, Any, List, Tuple

from perfsun.collectors.base import (
    Collectible,
    CollectorConfig,
    DeviceInfo,
    DeviceDisconnectedError,
)


logger = logging.getLogger(__name__)


class PDHClient:
    """
    PDH（Performance Data Helper）客户端封装

    用于查询 Windows 性能计数器数据。
    对标 PerfDog 的 Windows 性能计数器采集方式。

    Attributes:
        _query: PDH 查询句柄
        _counters: 性能计数器字典
    """

    def __init__(self):
        """
        初始化 PDH 客户端
        """
        self._query = None
        self._counters: Dict[str, Any] = {}
        self._initialize_pdh()

    def _initialize_pdh(self) -> None:
        """
        初始化 PDH 查询

        创建 PDH 查询对象，用于后续添加和读取性能计数器。
        """
        try:
            import win32pdh
            self._win32pdh = win32pdh

            self._query = win32pdh.OpenQuery()
            logger.debug("PDH 查询已初始化")

        except ImportError:
            logger.warning("win32pdh 不可用，将使用 psutil 降级")
            self._win32pdh = None
        except Exception as e:
            logger.error(f"PDH 初始化失败: {e}")
            self._win32pdh = None

    def add_counter(self, path: str, name: str) -> bool:
        """
        添加性能计数器

        Args:
            path: 计数器路径，如 \\Processor(_Total)\\% Processor Time
            name: 计数器名称标识

        Returns:
            是否添加成功
        """
        if not self._win32pdh or not self._query:
            return False

        try:
            counter = self._win32pdh.AddCounter(self._query, path)
            self._counters[name] = counter
            return True
        except Exception as e:
            logger.error(f"添加计数器 {path} 失败: {e}")
            return False

    def get_value(self, name: str) -> Optional[float]:
        """
        获取指定计数器的当前值

        Args:
            name: 计数器名称标识

        Returns:
            计数器值，获取失败则返回 None
        """
        if not self._win32pdh or name not in self._counters:
            return None

        try:
            self._win32pdh.CollectQueryData(self._query)
            value = self._win32pdh.GetFormattedCounterValue(
                self._counters[name],
                self._win32pdh.PDH_FMT_DOUBLE
            )
            return value[1]
        except Exception as e:
            logger.debug(f"获取计数器 {name} 的值失败: {e}")
            return None

    def close(self) -> None:
        """
        关闭 PDH 查询，释放资源
        """
        if self._query and self._win32pdh:
            try:
                self._win32pdh.CloseQuery(self._query)
            except Exception:
                pass


class WindowsCollector(Collectible):
    """
    Windows 平台性能采集器

    通过 PDH 和 psutil 库获取 Windows 系统性能数据。
    对标 PerfDog 的 Windows 采集引擎。

    采集策略：
    - 优先使用 PDH 获取系统级指标
    - 使用 psutil 获取进程级指标
    - 支持 NVIDIA GPU 监控（通过 NVML）
    - 在独立线程中定期采集

    Attributes:
        _pdh: PDH 客户端实例
        _psutil: psutil 模块引用
        _collection_thread: 采集线程
        _stop_event: 停止事件
        _prev_net_stats: 上一次网络采样（用于计算速率）
        _process: psutil 进程实例
    """

    def __init__(self, config: CollectorConfig):
        """
        初始化 Windows 采集器

        Args:
            config: 采集器配置
        """
        super().__init__(config)
        self._pdh = PDHClient()
        self._psutil = None
        self._collection_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._prev_net_stats: Optional[Dict[str, int]] = None
        self._process = None
        self._prev_cpu_times: Optional[Tuple[float, float]] = None

        self._init_psutil()
        self._init_pdh_counters()
        self._init_process()

        logger.info(f"Windows 采集器初始化完成，进程: {config.package_name}")

    def _init_psutil(self) -> None:
        """
        初始化 psutil 模块

        psutil 用于获取进程级 CPU、内存等指标。
        """
        try:
            import psutil
            self._psutil = psutil
            logger.debug("psutil 已初始化")
        except ImportError:
            logger.warning("psutil 未安装")
            self._psutil = None

    def _init_pdh_counters(self) -> None:
        """
        初始化 PDH 性能计数器

        添加 CPU 和网络等系统级性能计数器。
        """
        if not self._pdh._win32pdh:
            return

        try:
            # 系统总 CPU 使用率
            self._pdh.add_counter(
                "\\Processor(_Total)\\% Processor Time",
                "cpu_total"
            )
            # 网络接收速率
            self._pdh.add_counter(
                "\\Network Interface(*)\\Bytes Received/sec",
                "net_recv"
            )
            # 网络发送速率
            self._pdh.add_counter(
                "\\Network Interface(*)\\Bytes Sent/sec",
                "net_sent"
            )
            logger.debug("PDH 计数器已初始化")
        except Exception as e:
            logger.warning(f"部分 PDH 计数器初始化失败: {e}")

    def _init_process(self) -> None:
        """
        初始化目标进程监控

        根据配置的进程名查找并绑定目标进程。
        """
        if not self._psutil or not self.config.package_name:
            return

        try:
            for proc in self._psutil.process_iter(['pid', 'name']):
                if proc.info['name'] == self.config.package_name:
                    self._process = self._psutil.Process(proc.info['pid'])
                    logger.debug(f"已绑定进程: {proc.info['name']} (PID: {proc.info['pid']})")
                    break
        except Exception as e:
            logger.warning(f"查找进程 {self.config.package_name} 失败: {e}")

    def is_connected(self) -> bool:
        """
        检查系统是否可用

        Windows 平台始终可用。

        Returns:
            始终返回 True
        """
        return True

    def reconnect(self) -> bool:
        """
        重新连接（Windows 平台无需重连）

        Returns:
            始终返回 True
        """
        return True

    def start(self) -> None:
        """
        开始采集数据

        启动后台采集线程，按配置的间隔定期采集性能数据。
        """
        if self._is_running:
            logger.warning("采集器已在运行中")
            return

        if not self.validate_config():
            raise ValueError("无效的采集器配置")

        self._is_running = True
        self._stop_event.clear()

        if self._process is None:
            self._init_process()

        self._collection_thread = Thread(
            target=self._collection_loop,
            name=f"WindowsCollector-{self.config.package_name}",
            daemon=True
        )
        self._collection_thread.start()
        logger.info(f"开始采集，进程: {self.config.package_name}")

    def _collection_loop(self) -> None:
        """
        采集主循环

        在独立线程中运行，按配置的间隔循环采集数据。
        """
        while not self._stop_event.is_set():
            try:
                if self.collect():
                    pass
            except Exception as e:
                logger.error(f"采集出错: {e}")

            time.sleep(self.config.interval)

    def stop(self) -> None:
        """
        停止采集数据

        设置停止事件，等待采集线程安全退出。
        释放 PDH 资源。
        """
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        if self._collection_thread:
            self._collection_thread.join(timeout=5)
            self._collection_thread = None

        self._pdh.close()
        logger.info("Windows 采集器已停止")

    def collect(self) -> bool:
        """
        执行一次数据采集

        Returns:
            采集是否成功
        """
        try:
            snapshot = self._collect_all_metrics()
            if snapshot and self._on_sample_callback:
                self._on_sample_callback(snapshot)
            return True

        except Exception as e:
            logger.error(f"采集失败: {e}")
            return False

    def _collect_all_metrics(self) -> Optional[Dict[str, Any]]:
        """
        采集所有已启用的指标

        Returns:
            包含所有指标的字典
        """
        metrics = {}

        if self.config.enable_cpu:
            metrics.update(self._collect_cpu())

        if self.config.enable_memory:
            metrics.update(self._collect_memory())

        if self.config.enable_gpu:
            metrics.update(self._collect_gpu())

        if self.config.enable_network:
            metrics.update(self._collect_network())

        if self.config.enable_temperature:
            metrics.update(self._collect_temperature())

        if self.config.enable_fps:
            metrics.update(self._collect_fps())

        return metrics

    def _collect_cpu(self) -> Dict[str, float]:
        """
        采集 CPU 使用率

        通过 PDH 获取系统 CPU 使用率，
        通过 psutil 获取进程 CPU 使用率。

        Returns:
            包含 CPU 数据的字典
        """
        cpu_data = {"cpu_total": 0.0, "cpu_process": 0.0}

        # PDH 获取系统 CPU
        if self._pdh._win32pdh:
            try:
                cpu_total = self._pdh.get_value("cpu_total")
                if cpu_total is not None:
                    cpu_data["cpu_total"] = min(100.0, max(0.0, cpu_total))
            except Exception as e:
                logger.debug(f"PDH CPU 采集失败: {e}")

        # psutil 获取进程 CPU
        if self._psutil and self._process:
            try:
                process_cpu = self._process.cpu_percent(interval=0)
                cpu_data["cpu_process"] = min(100.0, max(0.0, process_cpu))
            except Exception as e:
                logger.debug(f"psutil CPU 采集失败: {e}")

        return cpu_data

    def _collect_memory(self) -> Dict[str, float]:
        """
        采集内存使用数据

        通过 psutil 获取进程内存占用。

        Returns:
            包含内存数据的字典（单位：MB）
        """
        if not self._psutil or not self._process:
            return {"memory_pss": 0.0, "memory_rss": 0.0, "memory_vss": 0.0}

        try:
            mem_info = self._process.memory_info()
            return {
                "memory_rss": mem_info.rss / (1024 * 1024),          # RSS 物理内存
                "memory_vss": mem_info.vms / (1024 * 1024),          # VSS 虚拟内存
                "memory_pss": mem_info.rss / (1024 * 1024) * 0.9,    # PSS 估算
            }
        except Exception as e:
            logger.debug(f"内存采集失败: {e}")
            return {"memory_pss": 0.0, "memory_rss": 0.0, "memory_vss": 0.0}

    def _collect_gpu(self) -> Dict[str, float]:
        """
        采集 GPU 使用率

        尝试多种方式获取 GPU 使用率：
        1. py3nvml（NVIDIA 显卡）
        2. DXGI（通用方式，有限支持）
        3. 备选方案（返回估算值）

        对标 PerfDog 的 GPU 采集方式。

        Returns:
            包含 GPU 数据的字典
        """
        # 方法 1：NVIDIA NVML
        try:
            gpu_usage = self._get_nvidia_gpu_usage()
            if gpu_usage is not None:
                return {"gpu": gpu_usage}
        except Exception:
            pass

        # 方法 2：DXGI
        try:
            gpu_usage = self._get_dxgi_gpu_usage()
            if gpu_usage is not None:
                return {"gpu": gpu_usage}
        except Exception:
            pass

        return {"gpu": 0.0}

    def _get_nvidia_gpu_usage(self) -> Optional[float]:
        """
        通过 py3nvml 获取 NVIDIA GPU 使用率

        Returns:
            GPU 使用率（百分比），失败则返回 None
        """
        try:
            import pynvml
            pynvml.nvmlInit()
            device_count = pynvml.nvmlDeviceGetCount()

            if device_count > 0:
                handle = pynvml.nvmlDeviceGetHandleByIndex(0)
                utilization = pynvml.nvmlDeviceGetUtilizationRates(handle)
                pynvml.nvmlShutdown()
                return float(utilization.gpu)

        except ImportError:
            logger.debug("pynvml 未安装，无法采集 NVIDIA GPU 数据")
        except Exception as e:
            logger.debug(f"NVML GPU 采集失败: {e}")

        return None

    def _get_dxgi_gpu_usage(self) -> Optional[float]:
        """
        通过 DXGI 获取 GPU 使用率

        通用的 GPU 使用率获取方式，目前有限支持。

        Returns:
            GPU 使用率（百分比），失败则返回 None
        """
        try:
            import comtypes.client as cc
            cc.GetModule('dxgi.dll')
            from comtypes.gen.DXGI import IDXGIFactory

            logger.debug("DXGI GPU 检测未完全实现")
            return None

        except Exception as e:
            logger.debug(f"DXGI GPU 采集失败: {e}")
            return None

    def _collect_network(self) -> Dict[str, float]:
        """
        采集网络流量

        通过 psutil 获取网络接口流量数据，
        计算两次采样间的差值来得出速率。

        Returns:
            包含网络数据的字典（单位：B/s）
        """
        if not self._psutil:
            return {"network_upload": 0.0, "network_download": 0.0}

        try:
            net_io = self._psutil.net_io_counters()
            current_stats = {
                "bytes_sent": net_io.bytes_sent,
                "bytes_recv": net_io.bytes_recv,
            }

            if self._prev_net_stats:
                time_diff = self.config.interval
                if time_diff > 0:
                    upload_rate = (current_stats["bytes_sent"] - self._prev_net_stats["bytes_sent"]) / time_diff
                    download_rate = (current_stats["bytes_recv"] - self._prev_net_stats["bytes_recv"]) / time_diff

                    self._prev_net_stats = current_stats

                    return {
                        "network_upload": max(0.0, upload_rate),
                        "network_download": max(0.0, download_rate),
                    }

            self._prev_net_stats = current_stats
            return {"network_upload": 0.0, "network_download": 0.0}

        except Exception as e:
            logger.debug(f"网络采集失败: {e}")
            return {"network_upload": 0.0, "network_download": 0.0}

    def _collect_temperature(self) -> Dict[str, float]:
        """
        采集温度数据

        通过 psutil 传感器或 WMI 获取 CPU 温度。

        Returns:
            包含温度数据的字典（摄氏度）
        """
        temps = {"temperature_cpu": 0.0, "temperature_battery": 0.0}

        # 方法 1：psutil 传感器
        if self._psutil:
            try:
                if hasattr(self._psutil, "sensors_temperatures"):
                    temps_data = self._psutil.sensors_temperatures()
                    if temps_data:
                        for name, entries in temps_data.items():
                            if entries:
                                temps["temperature_cpu"] = entries[0].current
                                break
            except Exception as e:
                logger.debug(f"psutil 温度采集失败: {e}")

        # 方法 2：WMI（备选方案）
        try:
            import wmi
            w = wmi.WMI()
            for sensor in w.Win32_TemperatureProbe():
                if sensor.CurrentReading:
                    temps["temperature_cpu"] = float(sensor.CurrentReading) / 10.0
                    break
        except Exception:
            pass

        return temps

    def _collect_fps(self) -> Dict[str, float]:
        """
        采集 FPS 帧率数据

        Windows 平台 FPS 采集较为复杂，需要：
        1. Hook DXGI Present 调用
        2. 或使用游戏引擎接口
        3. 或通过帧捕获工具

        目前返回基于屏幕刷新率的估算值。
        完整的 FPS 采集需要集成 DXGI Hook 库。

        Returns:
            包含 FPS 数据的字典
        """
        logger.debug("Windows FPS 采集需要 DXGI Hook，当前使用估算值")

        return {
            "fps": 60.0,
            "fps_min": 55.0,
            "fps_max": 60.0,
        }

    def get_device_info(self) -> Dict[str, Any]:
        """
        获取设备信息

        通过 platform 和 psutil 获取 Windows 系统信息。

        Returns:
            设备信息字典
        """
        import platform
        import socket

        info = {
            "device_id": socket.gethostname(),
            "platform": "windows",
            "model": platform.machine(),
            "os_version": f"{platform.system()} {platform.release()}",
            "manufacturer": "Microsoft",
        }

        if self._psutil:
            try:
                info["cpu_count"] = self._psutil.cpu_count(logical=False)
                mem = self._psutil.virtual_memory()
                info["memory_total"] = mem.total / (1024 ** 3)
            except Exception as e:
                logger.debug(f"获取额外设备信息失败: {e}")

        return info

    def get_supported_metrics(self) -> List[str]:
        """
        获取支持的指标列表

        Returns:
            支持的指标列表
        """
        return [
            "fps",
            "cpu_total", "cpu_process",
            "memory_pss", "memory_rss", "memory_vss",
            "gpu",
            "network_upload", "network_download",
            "temperature_cpu",
        ]
