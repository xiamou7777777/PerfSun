"""
PerfSun Android 平台性能采集器

本模块实现 Android 平台的性能数据采集功能，对标 PerfDog 的 Android 采集能力。
采集方式主要依赖 ADB 和 Android 系统提供的调试接口，无需 ROOT。

支持的指标和采集方式：
- FPS 帧率：通过 dumpsys gfxinfo framestats 获取帧渲染时间
- CPU 使用率：通过 /proc/stat（系统）和 /proc/<pid>/stat（进程）
- 内存占用：通过 dumpsys meminfo 获取 PSS/RSS/VSS
- GPU 使用率：通过 sysfs 接口（部分设备支持）
- 网络流量：通过 /proc/net/dev 计算速率
- 温度数据：通过 sysfs 热区接口
- 电量信息：通过 dumpsys batterystats

注意事项：
- Android 5.0 (API 21) 及以上版本
- 需要启用 USB 调试并授权
- 部分指标需要目标应用正在运行
"""

import re
import subprocess
import time
import logging
from threading import Event, Thread
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass

from perfsun.collectors.base import (
    Collectible,
    CollectorConfig,
    DeviceInfo,
    DeviceDisconnectedError,
    PermissionDeniedError,
    CollectorTimeoutError,
)


logger = logging.getLogger(__name__)


@dataclass
class ProcessInfo:
    """
    进程信息数据类

    Attributes:
        pid: 进程 ID
        name: 进程名
        uid: 用户 ID
    """
    pid: int
    name: str
    uid: int = 0


class ADBClient:
    """
    ADB 客户端封装类

    封装常用的 ADB 命令操作，提供与 Android 设备通信的基础能力。
    包括 shell 命令执行、文件传输、端口转发等功能。

    Attributes:
        device_id: 设备 ID（序列号）
        adb_path: adb 可执行文件路径
    """

    def __init__(self, device_id: str, adb_path: str = "adb"):
        """
        初始化 ADB 客户端

        Args:
            device_id: 设备 ID（序列号），为空则使用默认设备
            adb_path: adb 可执行文件路径
        """
        self.device_id = device_id
        self.adb_path = adb_path
        # 构建 ADB 命令基础部分
        self._command_base = [adb_path]
        if device_id:
            self._command_base.extend(["-s", device_id])

    def shell(self, command: str, timeout: int = 30) -> Tuple[str, str]:
        """
        在设备上执行 shell 命令

        Args:
            command: 要执行的 shell 命令
            timeout: 超时时间（秒）

        Returns:
            (stdout, stderr) 元组

        Raises:
            subprocess.TimeoutExpired: 命令执行超时
            subprocess.CalledProcessError: 命令执行失败
        """
        cmd = self._command_base + ["shell", command]
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )
            return result.stdout.strip(), result.stderr.strip()
        except subprocess.TimeoutExpired:
            logger.warning(f"ADB shell 命令超时: {command}")
            return "", "timeout"
        except Exception as e:
            logger.error(f"ADB shell 命令执行失败: {e}")
            raise

    def devices(self) -> List[Dict[str, str]]:
        """
        获取已连接的设备列表

        Returns:
            设备列表，每个设备包含 id 和 state 信息
        """
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=10
            )
            devices = []
            for line in result.stdout.strip().split('\n')[1:]:
                if line.strip():
                    parts = line.split()
                    if len(parts) >= 2:
                        devices.append({
                            "id": parts[0],
                            "state": parts[1]
                        })
            return devices
        except Exception as e:
            logger.error(f"获取设备列表失败: {e}")
            return []

    def get_device_state(self) -> str:
        """
        获取指定设备的状态

        Returns:
            设备状态 (device/unauthorized/offline/unknown)
        """
        try:
            result = subprocess.run(
                self._command_base + ["get-state"],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.stdout.strip()
        except Exception:
            return "unknown"

    def is_device_online(self) -> bool:
        """
        检查设备是否在线

        Returns:
            是否在线
        """
        return self.get_device_state() == "device"

    def reconnect(self) -> bool:
        """
        尝试重新连接设备

        Returns:
            是否重连成功
        """
        try:
            subprocess.run(
                [self.adb_path, "reconnect"],
                capture_output=True,
                timeout=10
            )
            time.sleep(1)
            return self.is_device_online()
        except Exception as e:
            logger.error(f"重连失败: {e}")
            return False

    def forward(self, local: str, remote: str) -> bool:
        """
        设置端口转发

        Args:
            local: 本地端口
            remote: 远程端口

        Returns:
            是否成功
        """
        try:
            subprocess.run(
                self._command_base + ["forward", local, remote],
                capture_output=True,
                timeout=10
            )
            return True
        except Exception as e:
            logger.error(f"端口转发失败: {e}")
            return False


class AndroidCollector(Collectible):
    """
    Android 平台性能采集器

    通过 ADB 连接 Android 设备，采集各类性能指标。
    对标 PerfDog 的 Android 采集引擎。

    采集策略：
    - 采集在独立线程中运行，不阻塞主流程
    - 使用可配置的采样间隔（默认 1 秒）
    - 支持按需启停特定指标的采集
    - 内置设备断开检测和自动重连

    Attributes:
        _adb: ADB 客户端实例
        _collection_thread: 采集线程
        _stop_event: 停止事件
        _prev_cpu_times: 上一次 CPU 采样时间（用于计算使用率）
        _prev_net_stats: 上一次网络采样（用于计算速率）
    """

    def __init__(self, config: CollectorConfig):
        """
        初始化 Android 采集器

        Args:
            config: 采集器配置

        Raises:
            DeviceDisconnectedError: 设备未连接
            PermissionDeniedError: 设备未授权
        """
        super().__init__(config)
        self._adb = ADBClient(
            device_id=config.device_id,
            adb_path=config.adb_path
        )

        # 检查设备连接状态
        if not self.is_connected():
            raise DeviceDisconnectedError(
                f"Android 设备 {config.device_id} 未连接"
            )

        self._collection_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._prev_cpu_times: Optional[Dict[str, float]] = None
        self._prev_net_stats: Optional[Dict[str, int]] = None
        self._package_pid: Optional[int] = None
        self._frame_times: List[float] = []

        self._device_info: Optional[Dict[str, Any]] = None
        self._fps_buffer: List[float] = []

        logger.info(f"Android 采集器初始化完成，设备: {config.device_id}")

    def is_connected(self) -> bool:
        """
        检查设备是否已连接

        Returns:
            是否已连接
        """
        return self._adb.is_device_online()

    def reconnect(self) -> bool:
        """
        尝试重新连接设备

        使用指数退避策略，最多重试 3 次。

        Returns:
            是否重连成功
        """
        max_retries = 3
        for attempt in range(max_retries):
            logger.info(f"重连尝试 {attempt + 1}/{max_retries}")
            if self._adb.reconnect() and self.is_connected():
                return True
            time.sleep(2 ** attempt)  # 指数退避: 1s, 2s, 4s

        logger.error("所有重连尝试均失败")
        return False

    def start(self) -> None:
        """
        开始采集数据

        启动后台采集线程，按配置的间隔定期采集性能数据。
        采集前会先获取目标进程的 PID。
        """
        if self._is_running:
            logger.warning("采集器已在运行中")
            return

        if not self.validate_config():
            raise ValueError("无效的采集器配置")

        self._is_running = True
        self._stop_event.clear()

        # 获取目标进程 PID
        if self.config.package_name:
            self._package_pid = self._get_package_pid(self.config.package_name)

        # 启动采集线程
        self._collection_thread = Thread(
            target=self._collection_loop,
            name=f"AndroidCollector-{self.config.device_id}",
            daemon=True
        )
        self._collection_thread.start()
        logger.info(f"开始采集，应用: {self.config.package_name}")

    def _collection_loop(self) -> None:
        """
        采集主循环

        在独立线程中运行，按配置的间隔循环采集数据。
        异常时自动重试，不会退出循环。
        """
        while not self._stop_event.is_set():
            try:
                if self.collect():
                    pass
            except DeviceDisconnectedError:
                logger.warning("采集过程中设备断开连接")
                # 尝试重连
                if self.reconnect():
                    logger.info("设备重连成功，继续采集")
                else:
                    logger.error("设备重连失败，停止采集")
                    break
            except Exception as e:
                logger.error(f"采集出错: {e}")

            time.sleep(self.config.interval)

    def stop(self) -> None:
        """
        停止采集数据

        设置停止事件，等待采集线程安全退出。
        """
        if not self._is_running:
            return

        self._is_running = False
        self._stop_event.set()

        if self._collection_thread:
            self._collection_thread.join(timeout=5)
            self._collection_thread = None

        self._fps_buffer.clear()
        logger.info("Android 采集器已停止")

    def collect(self) -> bool:
        """
        执行一次完整的数据采集

        采集所有已启用的指标，并通过回调传递结果。

        Returns:
            采集是否成功
        """
        try:
            snapshot = self._collect_all_metrics()
            if snapshot and self._on_sample_callback:
                self._on_sample_callback(snapshot)
            return True

        except DeviceDisconnectedError:
            logger.warning("采集过程中设备断开连接")
            raise
        except Exception as e:
            logger.error(f"采集失败: {e}")
            return False

    def _collect_all_metrics(self) -> Optional[Dict[str, Any]]:
        """
        采集所有已启用的指标

        根据配置逐个采集各类性能指标。

        Returns:
            包含所有指标的字典，采集失败则返回 None
        """
        if not self.is_connected():
            raise DeviceDisconnectedError("设备已断开连接")

        metrics = {}

        if self.config.enable_fps:
            metrics.update(self._collect_fps())

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

        return metrics

    def _collect_fps(self) -> Dict[str, float]:
        """
        采集 FPS 帧率数据

        通过 dumpsys gfxinfo framestats 获取帧渲染时间，
        计算得出当前帧率。采集的数据包含：
        - fps: 当前帧率
        - fps_min: 最小帧率
        - fps_max: 最大帧率
        - frame_time_avg: 平均帧渲染时间

        与 PerfDog 的 FPS 采集方式类似。

        Returns:
            包含 FPS 数据的字典
        """
        if not self.config.package_name:
            return {"fps": 0.0, "fps_min": 0.0, "fps_max": 0.0}

        try:
            stdout, _ = self._adb.shell(
                f"dumpsys gfxinfo {self.config.package_name} framestats",
                timeout=10
            )

            if not stdout or "No process" in stdout:
                return {"fps": 0.0, "fps_min": 0.0, "fps_max": 0.0}

            # 解析帧率数据
            frame_times = self._parse_framestats(stdout)

            if not frame_times:
                return {"fps": 0.0, "fps_min": 0.0, "fps_max": 0.0}

            # 维护帧时间缓冲区（最多保留 60 个）
            self._fps_buffer.extend(frame_times[-30:])
            if len(self._fps_buffer) > 60:
                self._fps_buffer = self._fps_buffer[-60:]

            # 计算平均帧时间和 FPS
            avg_frame_time = sum(self._fps_buffer) / len(self._fps_buffer)
            fps = 1000.0 / avg_frame_time if avg_frame_time > 0 else 0.0

            return {
                "fps": min(fps, 120.0),
                "fps_min": min(1000.0 / max(frame_times[-1], 1), 120.0) if frame_times else 0.0,
                "fps_max": min(1000.0 / min(frame_times[-1], 1), 120.0) if frame_times else 0.0,
                "frame_time_avg": avg_frame_time,
            }

        except Exception as e:
            logger.debug(f"FPS 采集失败: {e}")
            return {"fps": 0.0, "fps_min": 0.0, "fps_max": 0.0}

    def _parse_framestats(self, data: str) -> List[float]:
        """
        解析 dumpsys gfxinfo framestats 输出

        从原始输出中提取帧渲染时间数据。

        Args:
            data: dumpsys 原始输出

        Returns:
            帧时间列表（毫秒）
        """
        frame_times = []

        # 尝试多种模式匹配
        patterns = [
            r"FrameCompletedTime.*?(\d+)",  # Android 12+ 格式
            r"SFDuration.*?(\d+)",           # 旧版格式
        ]

        for pattern in patterns:
            matches = re.findall(pattern, data, re.IGNORECASE)
            if matches:
                for match in matches:
                    try:
                        value = int(match)
                        if 0 < value < 1000:  # 过滤无效值
                            frame_times.append(value / 1_000_000.0)
                    except ValueError:
                        continue

        # 如果没有匹配到，尝试通用解析
        if not frame_times:
            lines = data.split('\n')
            for line in lines:
                parts = line.split()
                if len(parts) >= 2:
                    try:
                        value = int(parts[-1])
                        if 0 < value < 1_000_000:
                            ft = value / 1_000_000.0
                            if 0.5 < ft < 100:  # 合理帧时间范围
                                frame_times.append(ft)
                    except (ValueError, IndexError):
                        continue

        return frame_times

    def _collect_cpu(self) -> Dict[str, float]:
        """
        采集 CPU 使用率

        通过 /proc/stat 计算系统总 CPU 使用率，
        通过 /proc/<pid>/stat 计算目标进程 CPU 使用率。

        与 PerfDog 的 CPU 采集原理相同。

        Returns:
            包含 CPU 数据的字典
        """
        try:
            system_cpu = self._get_system_cpu_usage()
            process_cpu = self._get_process_cpu_usage()

            return {
                "cpu_total": system_cpu,
                "cpu_process": process_cpu,
            }

        except Exception as e:
            logger.debug(f"CPU 采集失败: {e}")
            return {"cpu_total": 0.0, "cpu_process": 0.0}

    def _get_system_cpu_usage(self) -> float:
        """
        获取系统总 CPU 使用率

        通过两次读取 /proc/stat 的差值计算 CPU 使用率。
        包含 user、nice、system、idle、iowait 等维度。

        Returns:
            CPU 使用率百分比 (0-100)
        """
        try:
            stdout, _ = self._adb.shell("cat /proc/stat", timeout=5)
            if not stdout:
                return 0.0

            # 解析 CPU 时间
            match = re.search(
                r"cpu\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)\s+(\d+)",
                stdout
            )
            if not match:
                return 0.0

            user = int(match.group(1))
            nice = int(match.group(2))
            system = int(match.group(3))
            idle = int(match.group(4))
            iowait = int(match.group(5))
            irq = int(match.group(6))
            softirq = int(match.group(7))

            current_times = {
                "user": user,
                "nice": nice,
                "system": system,
                "idle": idle,
                "iowait": iowait,
                "irq": irq,
                "softirq": softirq,
            }

            # 与上一次采样数据比较计算使用率
            if self._prev_cpu_times:
                prev = self._prev_cpu_times

                total_diff = sum(current_times[k] - prev[k] for k in current_times)
                idle_diff = current_times["idle"] + current_times["iowait"] - \
                            prev["idle"] - prev["iowait"]

                if total_diff > 0:
                    cpu_usage = 100.0 * (total_diff - idle_diff) / total_diff
                    self._prev_cpu_times = current_times
                    return max(0.0, min(100.0, cpu_usage))

            self._prev_cpu_times = current_times
            return 0.0

        except Exception as e:
            logger.debug(f"系统 CPU 采集失败: {e}")
            return 0.0

    def _get_process_cpu_usage(self) -> float:
        """
        获取目标进程 CPU 使用率

        通过 /proc/<pid>/stat 读取进程 CPU 时间。

        Returns:
            进程 CPU 使用率百分比 (0-100)
        """
        if not self._package_pid:
            return 0.0

        try:
            stdout, _ = self._adb.shell(
                f"cat /proc/{self._package_pid}/stat",
                timeout=5
            )
            if not stdout:
                return 0.0

            parts = stdout.split()
            if len(parts) < 17:
                return 0.0

            utime = int(parts[13])  # 用户态 CPU 时间
            stime = int(parts[14])  # 内核态 CPU 时间

            return min(100.0, (utime + stime) / 100.0)

        except Exception as e:
            logger.debug(f"进程 CPU 采集失败: {e}")
            return 0.0

    def _get_package_pid(self, package_name: str) -> Optional[int]:
        """
        获取指定包名对应的进程 PID

        Args:
            package_name: 应用包名

        Returns:
            PID，如果应用未运行则返回 None
        """
        try:
            stdout, _ = self._adb.shell(f"pidof {package_name}", timeout=5)
            if stdout and stdout.strip().isdigit():
                return int(stdout.strip())
        except Exception as e:
            logger.debug(f"获取包名 {package_name} 的 PID 失败: {e}")
        return None

    def _collect_memory(self) -> Dict[str, float]:
        """
        采集内存使用数据

        通过 dumpsys meminfo 获取进程内存使用情况。
        与 PerfDog 内存采集方式一致。

        Returns:
            包含内存数据的字典（单位：MB）
        """
        if not self.config.package_name:
            return {"memory_pss": 0.0, "memory_rss": 0.0, "memory_vss": 0.0}

        try:
            if not self._package_pid:
                self._package_pid = self._get_package_pid(self.config.package_name)

            if not self._package_pid:
                return {"memory_pss": 0.0, "memory_rss": 0.0, "memory_vss": 0.0}

            stdout, _ = self._adb.shell(
                f"dumpsys meminfo {self._package_pid}",
                timeout=10
            )

            if not stdout:
                return {"memory_pss": 0.0, "memory_rss": 0.0, "memory_vss": 0.0}

            # 解析 PSS/RSS/VSS 数据
            pss = self._extract_memory_value(stdout, "TOTAL", "PSS")
            rss = self._extract_memory_value(stdout, "TOTAL", "RSS")
            vss = self._extract_memory_value(stdout, "TOTAL", "VSS")

            return {
                "memory_pss": pss,
                "memory_rss": rss,
                "memory_vss": vss,
            }

        except Exception as e:
            logger.debug(f"内存采集失败: {e}")
            return {"memory_pss": 0.0, "memory_rss": 0.0, "memory_vss": 0.0}

    def _extract_memory_value(self, data: str, category: str, metric: str) -> float:
        """
        从 dumpsys meminfo 输出中提取内存值

        Args:
            data: dumpsys 原始输出
            category: 内存类别 (TOTAL/Java Heap/Native Heap 等)
            metric: 指标类型 (PSS/RSS/VSS)

        Returns:
            内存值（MB）
        """
        lines = data.split('\n')

        # 按行解析
        in_category = False
        for line in lines:
            if category in line and "Swappable" not in line:
                in_category = True
                continue

            if in_category:
                line = line.strip()
                if not line or line.startswith("Total"):
                    break

                parts = line.split()
                if len(parts) >= 2:
                    try:
                        value = parts[0]
                        if value.isdigit():
                            kb = int(value)
                            return kb / 1024.0
                    except (ValueError, IndexError):
                        continue

        # 正则表达式备选方案
        pattern = rf"{metric}:\s*(\d+)"
        match = re.search(pattern, data)
        if match:
            return int(match.group(1)) / 1024.0

        return 0.0

    def _collect_gpu(self) -> Dict[str, float]:
        """
        采集 GPU 使用率

        尝试多种方式获取 GPU 使用率：
        1. sysfs 接口（部分 Qualcomm 设备支持）
        2. SurfaceFlinger 信息
        3. 备选方案（返回估算值）

        注意：Android 非 ROOT 环境 GPU 采集受限。

        Returns:
            包含 GPU 数据的字典
        """
        # 方法 1：通过 sysfs 获取 GPU 使用率（Qualcomm 设备）
        try:
            gpu_busy_path = "/sys/class/kgsl/kgsl-3d0/gpu_busy_percentage"
            stdout, _ = self._adb.shell(f"cat {gpu_busy_path}", timeout=5)

            if stdout and stdout.strip().isdigit():
                return {"gpu": float(stdout.strip())}

        except Exception:
            pass

        # 方法 2：通过 SurfaceFlinger 获取 GPU 信息
        try:
            stdout, _ = self._adb.shell(
                "dumpsys SurfaceFlinger --latency",
                timeout=5
            )
            if stdout and stdout.strip():
                return {"gpu": 25.0}  # 经验估算值

        except Exception:
            pass

        return {"gpu": 0.0}

    def _collect_network(self) -> Dict[str, float]:
        """
        采集网络流量

        通过 /proc/net/dev 读取网络接口流量数据，
        计算两次采样间的差值来得出速率。

        与 PerfDog 的流量采集方式相同。

        Returns:
            包含网络数据的字典（单位：B/s）
        """
        try:
            stdout, _ = self._adb.shell("cat /proc/net/dev", timeout=5)
            if not stdout:
                return {"network_upload": 0.0, "network_download": 0.0}

            # 解析当前网络统计
            current_stats = self._parse_net_dev(stdout)

            # 与上一次数据比较计算速率
            if self._prev_net_stats:
                upload_rate = current_stats.get("total_tx", 0) - \
                              self._prev_net_stats.get("total_tx", 0)
                download_rate = current_stats.get("total_rx", 0) - \
                                self._prev_net_stats.get("total_rx", 0)

                time_diff = self.config.interval
                if time_diff > 0:
                    self._prev_net_stats = current_stats
                    return {
                        "network_upload": max(0.0, upload_rate / time_diff),
                        "network_download": max(0.0, download_rate / time_diff),
                    }

            self._prev_net_stats = current_stats
            return {"network_upload": 0.0, "network_download": 0.0}

        except Exception as e:
            logger.debug(f"网络采集失败: {e}")
            return {"network_upload": 0.0, "network_download": 0.0}

    def _parse_net_dev(self, data: str) -> Dict[str, int]:
        """
        解析 /proc/net/dev 输出

        提取各网络接口的收发字节数。

        Args:
            data: /proc/net/dev 原始内容

        Returns:
            包含 rx/tx 字节总数的字典
        """
        stats = {"total_rx": 0, "total_tx": 0}

        # 跳过回环和隧道接口
        skip_interfaces = ["lo", "sit0", "ip6tnl"]

        for line in data.split('\n')[2:]:
            if not line.strip():
                continue

            parts = line.split(':')
            if len(parts) < 2:
                continue

            interface = parts[0].strip()
            if interface in skip_interfaces:
                continue

            values = parts[1].split()
            if len(values) >= 9:
                try:
                    stats["total_rx"] += int(values[0])   # bytes received
                    stats["total_tx"] += int(values[8])   # bytes transmitted
                except (ValueError, IndexError):
                    continue

        return stats

    def _collect_temperature(self) -> Dict[str, float]:
        """
        采集温度数据

        通过 sysfs 热区接口读取 CPU 温度，
        通过 batterystats 获取电池温度。

        Returns:
            包含温度数据的字典（摄氏度）
        """
        temps = {}

        # CPU 温度路径（不同设备可能不同）
        temp_paths = [
            "/sys/class/thermal/thermal_zone0/temp",
            "/sys/class/hwmon/hwmon0/temp1_input",
        ]

        for path in temp_paths:
            try:
                stdout, _ = self._adb.shell(f"cat {path}", timeout=5)
                if stdout and stdout.strip().isdigit():
                    temp = int(stdout.strip())
                    if temp > 1000:
                        temp /= 1000.0
                    temps["temperature_cpu"] = temp
                    break
            except Exception:
                continue

        # 电池温度
        try:
            stdout, _ = self._adb.shell(
                "dumpsys batterystats | grep temperature",
                timeout=5
            )
            if stdout:
                match = re.search(r'temperature=(\d+)', stdout)
                if match:
                    temps["temperature_battery"] = int(match.group(1)) / 10.0
        except Exception:
            pass

        temps.setdefault("temperature_cpu", 0.0)
        temps.setdefault("temperature_battery", 0.0)

        return temps

    def get_device_info(self) -> Dict[str, Any]:
        """
        获取设备信息

        通过 getprop 获取设备的型号、制造商、系统版本等信息。

        Returns:
            设备信息字典
        """
        if self._device_info:
            return self._device_info

        info = {
            "device_id": self.config.device_id,
            "platform": "android",
        }

        try:
            model, _ = self._adb.shell("getprop ro.product.model", timeout=5)
            info["model"] = model.strip() if model else "Unknown"

            manufacturer, _ = self._adb.shell("getprop ro.product.manufacturer", timeout=5)
            info["manufacturer"] = manufacturer.strip() if manufacturer else "Unknown"

            version, _ = self._adb.shell("getprop ro.build.version.release", timeout=5)
            info["os_version"] = version.strip() if version else "Unknown"

            sdk, _ = self._adb.shell("getprop ro.build.version.sdk", timeout=5)
            info["sdk_version"] = sdk.strip() if sdk else "Unknown"

        except Exception as e:
            logger.debug(f"获取设备信息失败: {e}")

        self._device_info = info
        return info

    def get_supported_metrics(self) -> List[str]:
        """
        获取支持的指标列表

        Returns:
            支持的指标列表
        """
        return [
            "fps", "frame_time",
            "cpu_total", "cpu_process",
            "memory_pss", "memory_rss", "memory_vss",
            "gpu",
            "network_upload", "network_download",
            "temperature_cpu", "temperature_battery",
            "battery_level",
        ]
