"""
PerfSun 采集器管理器

本模块负责管理所有平台采集器的生命周期，包括：
- 注册和注销平台采集器
- 启动和停止数据采集
- 管理并发采集会话
- 将数据路由到记录器和实时回调
- 处理采集器健康检查和重连

类似于 PerfDog 中采集引擎的核心调度器。
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from threading import Thread, Event, Lock
from datetime import datetime
import logging
import uuid

from perfsun.core.data_point import MetricsSnapshot, SessionInfo
from perfsun.core.data_recorder import DataRecorder
from perfsun.collectors.base import Collectible, CollectorConfig


logger = logging.getLogger(__name__)


@dataclass
class CollectorStatus:
    """
    采集器运行状态

    记录单个采集器的实时运行状态信息，
    用于监控采集器健康和进度。

    Attributes:
        device_id: 设备唯一标识符
        platform: 平台类型 (android/ios/windows)
        is_running: 采集器是否正在运行
        last_sample_time: 最近一次成功采样的时间戳
        sample_count: 已采集的样本总数
        error_count: 发生的错误次数
        last_error: 最近一次错误信息
    """
    device_id: str
    platform: str
    is_running: bool = False
    last_sample_time: Optional[float] = None
    sample_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """将状态转换为字典"""
        return {
            "device_id": self.device_id,
            "platform": self.platform,
            "is_running": self.is_running,
            "last_sample_time": self.last_sample_time,
            "sample_count": self.sample_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }


class CollectorManager:
    """
    集中式采集器管理器

    管理和协调所有平台采集器的核心类，提供统一的采集控制接口。
    支持同时连接多台设备并分别采集性能数据。

    功能对标 PerfDog 的"多设备并发采集"能力。

    Attributes:
        collectors: 设备ID到采集器实例的映射字典
        statuses: 设备ID到采集器状态的映射字典
        recorder: 用于持久化存储的 DataRecorder 实例
        callback: 实时数据推送的回调函数
    """

    def __init__(self, recorder: Optional[DataRecorder] = None):
        """
        初始化 CollectorManager

        Args:
            recorder: 可选的 DataRecorder 实例，用于数据持久化。
                      如果不提供，将自动创建新的 DataRecorder。
        """
        self.collectors: Dict[str, Collectible] = {}
        self.statuses: Dict[str, CollectorStatus] = {}
        self.recorder = recorder or DataRecorder()
        self.callback: Optional[Callable[[MetricsSnapshot], None]] = None
        self._lock = Lock()
        self._collection_thread: Optional[Thread] = None
        self._stop_event = Event()
        self._sessions: Dict[str, SessionInfo] = {}
        logger.info("采集器管理器初始化完成")

    def register_collector(self, collector: Collectible, device_id: str) -> None:
        """
        注册一个新的平台采集器

        将采集器实例与设备ID关联，以便后续管理。

        Args:
            collector: 要注册的采集器实例
            device_id: 设备的唯一标识符

        Raises:
            ValueError: 如果该 device_id 已注册了采集器
        """
        with self._lock:
            if device_id in self.collectors:
                raise ValueError(
                    f"设备 {device_id} 已注册了采集器"
                )

            platform = collector.config.platform
            self.collectors[device_id] = collector
            self.statuses[device_id] = CollectorStatus(
                device_id=device_id,
                platform=platform,
            )
            logger.info(
                f"已注册 {platform} 采集器，设备: {device_id}"
            )

    def unregister_collector(self, device_id: str) -> None:
        """
        注销指定设备的采集器

        如果采集器正在运行，会先停止采集再注销。

        Args:
            device_id: 要注销的设备 ID

        Raises:
            KeyError: 如果该 device_id 没有注册采集器
        """
        with self._lock:
            if device_id not in self.collectors:
                raise KeyError(f"未找到设备 {device_id} 的采集器")

            collector = self.collectors[device_id]
            if self.statuses[device_id].is_running:
                collector.stop()
                self.statuses[device_id].is_running = False

            del self.collectors[device_id]
            del self.statuses[device_id]
            logger.info(f"已注销设备 {device_id} 的采集器")

    def get_collector(self, device_id: str) -> Optional[Collectible]:
        """
        获取指定设备的采集器

        Args:
            device_id: 要查询的设备 ID

        Returns:
            采集器实例，如果未找到则返回 None
        """
        return self.collectors.get(device_id)

    def get_status(self, device_id: str) -> Optional[CollectorStatus]:
        """
        获取指定采集器的运行状态

        Args:
            device_id: 要查询的设备 ID

        Returns:
            CollectorStatus 对象，如果未找到则返回 None
        """
        return self.statuses.get(device_id)

    def list_collectors(self) -> List[CollectorStatus]:
        """
        获取所有已注册采集器的状态列表

        Returns:
            所有注册采集器的状态列表
        """
        return list(self.statuses.values())

    def set_realtime_callback(
        self,
        callback: Callable[[MetricsSnapshot], None]
    ) -> None:
        """
        设置实时数据回调函数

        每当采集到新的指标快照时，都会调用此回调。
        可用于实现实时仪表盘、WebSocket 推送等功能。

        Args:
            callback: 接收 MetricsSnapshot 的回调函数
        """
        self.callback = callback
        logger.debug("实时数据回调已设置")

    def start_collection(
        self,
        device_id: str,
        package_name: str = "",
        interval: float = 1.0,
        session_id: Optional[str] = None,
    ) -> str:
        """
        开始对指定设备进行数据采集

        创建新的录制会话，启动采集线程，
        并设置数据处理的回调链。

        Args:
            device_id: 要采集的设备 ID
            package_name: 目标应用的包名/BundleID
            interval: 采样间隔（秒）
            session_id: 可选的会话 ID，不提供则自动生成

        Returns:
            本次采集的会话 ID

        Raises:
            KeyError: 如果该 device_id 没有注册采集器
        """
        with self._lock:
            if device_id not in self.collectors:
                raise KeyError(f"未找到设备 {device_id} 的采集器")

            collector = self.collectors[device_id]
            status = self.statuses[device_id]

            if status.is_running:
                logger.warning(
                    f"设备 {device_id} 的采集器已在运行中"
                )
                return self._sessions[device_id].id if device_id in self._sessions else ""

            # 更新采集器配置
            collector.config.package_name = package_name
            collector.config.interval = interval

            # 生成或使用提供的会话 ID
            if session_id is None:
                session_id = str(uuid.uuid4())

            # 创建会话信息
            session = SessionInfo(
                id=session_id,
                device_id=device_id,
                platform=collector.config.platform,
                package_name=package_name,
                start_time=datetime.now().timestamp(),
                status="recording",
            )
            self._sessions[device_id] = session

            # 设置采样回调并启动采集
            collector.on_sample = self._create_sample_handler(device_id)
            collector.start()

            status.is_running = True
            status.sample_count = 0
            logger.info(
                f"开始采集 - 设备: {device_id}, "
                f"会话: {session_id}, 间隔: {interval}s"
            )

            return session_id

    def stop_collection(self, device_id: str) -> Optional[SessionInfo]:
        """
        停止指定设备的数据采集

        停止采集器，更新会话的结束信息和统计数据。

        Args:
            device_id: 要停止采集的设备 ID

        Returns:
            采集结束时的 SessionInfo 对象，如果无活跃会话则返回 None

        Raises:
            KeyError: 如果该 device_id 没有注册采集器
        """
        with self._lock:
            if device_id not in self.collectors:
                raise KeyError(f"未找到设备 {device_id} 的采集器")

            collector = self.collectors[device_id]
            status = self.statuses[device_id]

            if not status.is_running:
                logger.warning(
                    f"设备 {device_id} 的采集器未在运行"
                )
                return None

            # 停止采集器
            collector.stop()
            status.is_running = False

            # 更新会话信息
            if device_id in self._sessions:
                session = self._sessions[device_id]
                session.end_time = datetime.now().timestamp()
                session.update_duration()
                session.sample_count = status.sample_count
                session.status = "completed"
                logger.info(
                    f"停止采集 - 设备: {device_id}, "
                    f"时长: {session.duration:.2f}s, "
                    f"样本数: {session.sample_count}"
                )
                return session

            return None

    def _create_sample_handler(
        self,
        device_id: str
    ) -> Callable[[MetricsSnapshot], None]:
        """
        创建针对指定设备的采样回调处理器

        该处理器负责：
        1. 更新采集器状态（上次采样时间、样本数）
        2. 将数据持久化到数据库
        3. 触发实时回调

        Args:
            device_id: 该处理器关联的设备 ID

        Returns:
            处理采集样本的回调函数
        """
        def handle_sample(snapshot: MetricsSnapshot) -> None:
            try:
                status = self.statuses[device_id]
                status.last_sample_time = snapshot.timestamp
                status.sample_count += 1

                # 持久化到数据库
                if device_id in self._sessions:
                    session = self._sessions[device_id]
                    snapshot.package_name = session.package_name
                    self.recorder.record_metric(snapshot, session.id)

                # 触发实时回调（如 WebSocket 推送、GUI 更新）
                if self.callback:
                    self.callback(snapshot)

            except Exception as e:
                status = self.statuses[device_id]
                status.error_count += 1
                status.last_error = str(e)
                logger.error(
                    f"处理设备 {device_id} 的样本时出错: {e}"
                )

        return handle_sample

    def start_all(self, package_name: str = "", interval: float = 1.0) -> Dict[str, str]:
        """
        在所有已注册采集器上启动采集

        批量启动所有设备的数据采集，适用于多设备并发测试。

        Args:
            package_name: 目标应用的包名/BundleID
            interval: 采样间隔（秒）

        Returns:
            设备ID到会话ID的映射字典
        """
        session_ids = {}
        for device_id in self.collectors:
            try:
                session_id = self.start_collection(
                    device_id,
                    package_name,
                    interval,
                )
                session_ids[device_id] = session_id
            except Exception as e:
                logger.error(
                    f"启动设备 {device_id} 的采集失败: {e}"
                )
        return session_ids

    def stop_all(self) -> Dict[str, Optional[SessionInfo]]:
        """
        停止所有采集器的采集

        Returns:
            设备ID到 SessionInfo 的映射字典
        """
        sessions = {}
        for device_id in list(self.collectors.keys()):
            try:
                sessions[device_id] = self.stop_collection(device_id)
            except Exception as e:
                logger.error(
                    f"停止设备 {device_id} 的采集失败: {e}"
                )
        return sessions

    def reconnect(self, device_id: str) -> bool:
        """
        尝试重新连接已断开的采集器

        使用指数退避策略进行重试，适用于 USB 断开
        或网络波动导致的连接中断场景。

        Args:
            device_id: 要重连的设备 ID

        Returns:
            重连成功返回 True，否则返回 False
        """
        with self._lock:
            if device_id not in self.collectors:
                logger.error(f"未找到设备 {device_id} 的采集器")
                return False

            collector = self.collectors[device_id]
            status = self.statuses[device_id]

            try:
                if collector.reconnect():
                    status.error_count = 0
                    status.last_error = None
                    logger.info(f"设备 {device_id} 重连成功")
                    return True
                else:
                    logger.warning(f"设备 {device_id} 重连失败")
                    return False

            except Exception as e:
                status.last_error = str(e)
                logger.error(f"设备 {device_id} 重连出错: {e}")
                return False

    def get_sessions(self) -> List[SessionInfo]:
        """
        获取所有录制会话列表

        Returns:
            SessionInfo 对象列表
        """
        return list(self._sessions.values())

    def get_session(self, device_id: str) -> Optional[SessionInfo]:
        """
        获取指定设备的会话信息

        Args:
            device_id: 要查询的设备 ID

        Returns:
            SessionInfo 对象，如果不存在则返回 None
        """
        return self._sessions.get(device_id)

    def cleanup(self) -> None:
        """
        清理所有采集器资源

        关闭应用程序时应调用此方法，它会：
        1. 停止所有正在进行的采集
        2. 清除采集器列表
        3. 清除所有会话信息
        """
        logger.info("正在清理采集器管理器...")

        self.stop_all()

        with self._lock:
            self.collectors.clear()
            self.statuses.clear()
            self._sessions.clear()

        logger.info("采集器管理器清理完成")
