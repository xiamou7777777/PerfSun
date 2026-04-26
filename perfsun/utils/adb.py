"""
PerfSun ADB 工具模块

本模块提供 ADB（Android Debug Bridge）命令的封装，
用于与 Android 设备进行通信和数据采集。

主要功能：
- 设备列表获取和状态检测
- Shell 命令执行
- 文件传输（push/pull）
- 端口转发（forward/reverse）
- 应用管理（安装/卸载/启动/清除数据）
- 屏幕截图
- 获取设备属性和 PID
"""

import subprocess
import logging
from typing import List, Dict, Tuple, Optional, Any


logger = logging.getLogger(__name__)


class ADBTools:
    """
    ADB 工具类

    提供常用的 ADB 操作封装，简化与 Android 设备的交互。
    所有方法都包含超时和错误处理，确保稳定性。

    Attributes:
        adb_path: adb 可执行文件路径
    """

    def __init__(self, adb_path: str = "adb"):
        """
        初始化 ADB 工具

        Args:
            adb_path: adb 可执行文件路径，默认为 "adb"（需在 PATH 中）
        """
        self.adb_path = adb_path

    def _run_command(self, args: List[str], timeout: int = 30) -> Tuple[str, str, int]:
        """
        执行 ADB 命令

        统一的命令执行入口，处理所有 ADB 命令的调用。

        Args:
            args: 命令参数列表
            timeout: 超时时间（秒）

        Returns:
            (stdout, stderr, returncode) 元组
        """
        cmd = [self.adb_path] + args
        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout,
                encoding='utf-8',
                errors='replace'
            )
            return result.stdout.strip(), result.stderr.strip(), result.returncode
        except subprocess.TimeoutExpired:
            logger.warning(f"ADB 命令超时: {' '.join(args)}")
            return "", "timeout", -1
        except Exception as e:
            logger.error(f"ADB 命令执行失败: {e}")
            return "", str(e), -1

    def get_devices(self) -> List[Dict[str, str]]:
        """
        获取已连接的 Android 设备列表

        执行 adb devices -l 获取已连接设备信息。

        Returns:
            设备列表，每个设备包含 id 和 state 等属性
        """
        stdout, _, returncode = self._run_command(["devices", "-l"])
        if returncode != 0:
            return []

        devices = []
        for line in stdout.split('\n')[1:]:
            if line.strip() and 'device' in line:
                parts = line.split()
                if len(parts) >= 2:
                    device_info = {"id": parts[0], "state": parts[1]}

                    # 解析设备属性（usb: 产品名: 型号等）
                    for part in parts[2:]:
                        if ':' in part:
                            key, value = part.split(':', 1)
                            device_info[key] = value

                    devices.append(device_info)

        return devices

    def shell(self, device_id: str, command: str, timeout: int = 30) -> Tuple[str, str]:
        """
        在指定设备上执行 shell 命令

        Args:
            device_id: 设备序列号，为空则使用唯一设备
            command: 要执行的 shell 命令
            timeout: 超时时间（秒）

        Returns:
            (stdout, stderr) 元组
        """
        if device_id:
            stdout, stderr, _ = self._run_command(
                ["-s", device_id, "shell", command],
                timeout=timeout
            )
        else:
            stdout, stderr, _ = self._run_command(
                ["shell", command],
                timeout=timeout
            )
        return stdout, stderr

    def get_prop(self, device_id: str, prop_name: str) -> Optional[str]:
        """
        获取 Android 系统属性

        Args:
            device_id: 设备序列号
            prop_name: 属性名，如 ro.product.model、ro.build.version.sdk 等

        Returns:
            属性值，获取失败则返回 None
        """
        stdout, _ = self.shell(device_id, f"getprop {prop_name}")
        return stdout if stdout else None

    def install(self, device_id: str, apk_path: str, reinstall: bool = False) -> bool:
        """
        安装 APK 到设备

        Args:
            device_id: 设备序列号
            apk_path: APK 文件路径
            reinstall: 是否覆盖安装（保留数据）

        Returns:
            是否安装成功
        """
        args = ["install"]
        if reinstall:
            args.append("-r")  # 保留应用数据的覆盖安装
        args.append(apk_path)

        if device_id:
            args = ["-s", device_id] + args

        _, stderr, returncode = self._run_command(args, timeout=120)
        return returncode == 0 and "Success" in stderr

    def uninstall(self, device_id: str, package_name: str) -> bool:
        """
        卸载设备上的应用

        Args:
            device_id: 设备序列号
            package_name: 包名

        Returns:
            是否卸载成功
        """
        args = ["uninstall", package_name]
        if device_id:
            args = ["-s", device_id] + args

        _, stderr, returncode = self._run_command(args)
        return returncode == 0

    def forward(self, device_id: str, local: str, remote: str) -> bool:
        """
        设置端口转发（本地 -> 设备）

        Args:
            device_id: 设备序列号
            local: 本地端口
            remote: 远程端口

        Returns:
            是否设置成功
        """
        args = ["forward", local, remote]
        if device_id:
            args = ["-s", device_id] + args

        _, _, returncode = self._run_command(args)
        return returncode == 0

    def reverse(self, device_id: str, local: str, remote: str) -> bool:
        """
        设置反向端口转发（设备 -> 本地）

        Args:
            device_id: 设备序列号
            local: 本地端口
            remote: 远程端口

        Returns:
            是否设置成功
        """
        args = ["reverse", remote, local]
        if device_id:
            args = ["-s", device_id] + args

        _, _, returncode = self._run_command(args)
        return returncode == 0

    def pull(self, device_id: str, remote_path: str, local_path: str) -> bool:
        """
        从设备拉取文件到本地

        Args:
            device_id: 设备序列号
            remote_path: 设备上的文件路径
            local_path: 本地保存路径

        Returns:
            是否拉取成功
        """
        args = ["pull", remote_path, local_path]
        if device_id:
            args = ["-s", device_id] + args

        _, _, returncode = self._run_command(args, timeout=300)
        return returncode == 0

    def push(self, device_id: str, local_path: str, remote_path: str) -> bool:
        """
        推送本地文件到设备

        Args:
            device_id: 设备序列号
            local_path: 本地文件路径
            remote_path: 设备上的保存路径

        Returns:
            是否推送成功
        """
        args = ["push", local_path, remote_path]
        if device_id:
            args = ["-s", device_id] + args

        _, _, returncode = self._run_command(args, timeout=300)
        return returncode == 0

    def screenshot(self, device_id: str, save_path: str) -> bool:
        """
        对设备进行截屏

        使用 screencap 命令截取设备屏幕并保存到本地。

        Args:
            device_id: 设备序列号
            save_path: 本地保存路径

        Returns:
            是否截图成功
        """
        remote_path = "/sdcard/screenshot_temp.png"
        stdout, stderr, _ = self._run_command(
            ["shell", "screencap", "-p", remote_path]
        )
        if "error" in stderr.lower():
            return False

        return self.pull(device_id, remote_path, save_path)

    def get_screen_resolution(self, device_id: str) -> Optional[Tuple[int, int]]:
        """
        获取设备屏幕分辨率

        Args:
            device_id: 设备序列号

        Returns:
            (width, height) 元组，获取失败则返回 None
        """
        stdout, _ = self.shell(device_id, "wm size")
        if stdout and "Physical" in stdout:
            parts = stdout.split(":")[-1].strip().split("x")
            if len(parts) == 2:
                try:
                    return int(parts[0]), int(parts[1])
                except ValueError:
                    pass
        return None

    def get_package_pid(self, device_id: str, package_name: str) -> Optional[int]:
        """
        获取指定应用的进程 PID

        Args:
            device_id: 设备序列号
            package_name: 应用包名

        Returns:
            PID，应用未运行则返回 None
        """
        stdout, _ = self.shell(device_id, f"pidof {package_name}")
        if stdout and stdout.strip().isdigit():
            return int(stdout.strip())
        return None

    def start_activity(self, device_id: str, package_name: str,
                       activity_name: str) -> bool:
        """
        启动指定 Activity

        Args:
            device_id: 设备序列号
            package_name: 包名
            activity_name: Activity 名称（完整路径）

        Returns:
            是否启动成功
        """
        component = f"{package_name}/{activity_name}"
        _, stderr, returncode = self._run_command(
            ["shell", "am", "start", "-n", component]
        )
        return returncode == 0

    def clear_app_data(self, device_id: str, package_name: str) -> bool:
        """
        清除应用数据

        Args:
            device_id: 设备序列号
            package_name: 包名

        Returns:
            是否清除成功
        """
        _, _, returncode = self._run_command(
            ["shell", "pm", "clear", package_name]
        )
        return returncode == 0

    def kill_process(self, device_id: str, package_name: str) -> bool:
        """
        强制停止应用进程

        Args:
            device_id: 设备序列号
            package_name: 包名

        Returns:
            是否停止成功
        """
        _, _, returncode = self._run_command(
            ["shell", "am", "force-stop", package_name]
        )
        return returncode == 0

    def get_battery_info(self, device_id: str) -> Dict[str, Any]:
        """
        获取设备电池信息

        Args:
            device_id: 设备序列号

        Returns:
            包含电池信息的字典
        """
        info = {"level": 0, "temperature": 0, "status": "unknown"}
        stdout, _ = self.shell(device_id, "dumpsys battery")
        if stdout:
            import re
            for line in stdout.split('\n'):
                line = line.strip()
                if line.startswith("level:"):
                    info["level"] = int(line.split()[-1])
                elif line.startswith("temperature:"):
                    info["temperature"] = int(line.split()[-1]) / 10.0
                elif line.startswith("status:"):
                    status_map = {1: "unknown", 2: "charging", 3: "discharging", 4: "not_charging", 5: "full"}
                    info["status"] = status_map.get(int(line.split()[-1]), "unknown")
        return info
