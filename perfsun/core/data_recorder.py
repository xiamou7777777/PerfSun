"""
PerfSun 数据记录器

本模块负责将采集的性能数据持久化到 SQLite 数据库，包括：
- 会话管理（创建、更新、查询、删除会话）
- 指标数据记录和查询
- 自定义标记管理
- 数据库统计信息
- 支持多线程安全访问

对标 PerfDog 的数据录制功能，提供完整的会话录制和数据管理能力。
"""

import sqlite3
import json
import threading
import logging
from datetime import datetime
from typing import List, Optional, Dict, Any, Tuple
from contextlib import contextmanager
from pathlib import Path

from perfsun.core.data_point import MetricsSnapshot, SessionInfo, Mark


logger = logging.getLogger(__name__)


class DatabaseSchema:
    """
    数据库表结构定义

    定义了 PerfSun 使用的 SQLite 数据库完整 schema。
    包含三个表：sessions（会话）、metrics（指标）、marks（标记）。
    """
    # 会话表：存储录制会话的元信息
    SESSIONS_TABLE = """
    CREATE TABLE IF NOT EXISTS sessions (
        id TEXT PRIMARY KEY,             -- 会话唯一标识
        device_id TEXT NOT NULL,         -- 设备ID
        platform TEXT NOT NULL,          -- 平台类型
        package_name TEXT,               -- 应用包名
        start_time REAL NOT NULL,        -- 开始时间戳
        end_time REAL,                   -- 结束时间戳
        duration REAL DEFAULT 0,         -- 持续时长（秒）
        sample_count INTEGER DEFAULT 0,  -- 样本数量
        status TEXT DEFAULT 'recording'   -- 会话状态
    )
    """

    # 指标表：存储所有性能采集数据
    METRICS_TABLE = """
    CREATE TABLE IF NOT EXISTS metrics (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
        session_id TEXT NOT NULL,               -- 所属会话ID
        timestamp REAL NOT NULL,                -- 采集时间戳
        device_id TEXT NOT NULL,                -- 设备ID
        platform TEXT NOT NULL,                 -- 平台类型
        package_name TEXT,                      -- 应用包名
        fps REAL,                              -- 帧率
        fps_min REAL,                          -- 最小帧率
        fps_max REAL,                          -- 最大帧率
        frame_time_avg REAL,                   -- 平均帧时间
        cpu_total REAL,                        -- 系统CPU使用率
        cpu_process REAL,                      -- 进程CPU使用率
        memory_pss REAL,                       -- PSS内存
        memory_rss REAL,                       -- RSS内存
        memory_vss REAL,                       -- VSS内存
        gpu REAL,                              -- GPU使用率
        network_upload REAL,                   -- 网络上行速率
        network_download REAL,                 -- 网络下行速率
        jank_count INTEGER,                    -- Jank次数
        big_jank_count INTEGER,                -- BigJank次数
        jank_rate REAL,                        -- Jank率
        temperature_cpu REAL,                  -- CPU温度
        temperature_battery REAL,              -- 电池温度
        battery_level REAL,                    -- 电池电量
        marks TEXT,                            -- 标记列表
        metadata TEXT,                         -- 元数据(JSON)
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """

    # 标记表：存储用户自定义标记
    MARKS_TABLE = """
    CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,  -- 自增主键
        session_id TEXT NOT NULL,               -- 所属会话ID
        timestamp REAL NOT NULL,                -- 标记时间戳
        mark_name TEXT NOT NULL,                -- 标记名称
        mark_type TEXT DEFAULT 'custom',        -- 标记类型
        metadata TEXT,                          -- 元数据(JSON)
        FOREIGN KEY (session_id) REFERENCES sessions(id)
    )
    """

    # 索引：按会话ID查询指标
    INDEX_METRICS_SESSION = """
    CREATE INDEX IF NOT EXISTS idx_metrics_session
    ON metrics(session_id)
    """

    # 索引：按时序查询指标
    INDEX_METRICS_TIMESTAMP = """
    CREATE INDEX IF NOT EXISTS idx_metrics_timestamp
    ON metrics(timestamp)
    """

    # 索引：按会话ID查询标记
    INDEX_MARKS_SESSION = """
    CREATE INDEX IF NOT EXISTS idx_marks_session
    ON marks(session_id)
    """


class DataRecorder:
    """
    性能数据记录器

    负责将采集的性能数据持久化到 SQLite 数据库。
    提供线程安全的读写操作，支持多采集器并发写入。
    对标 PerfDog 的数据录制引擎。

    Attributes:
        db_path: 数据库文件路径
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        初始化数据记录器

        Args:
            db_path: 数据库文件路径，默认为当前目录下的 perfsun.db
        """
        if db_path is None:
            db_path = "perfsun.db"

        self.db_path = db_path
        self._local = threading.local()
        self._lock = threading.Lock()
        self._init_database()
        logger.info(f"数据记录器初始化完成，数据库: {db_path}")

    def _get_connection(self) -> sqlite3.Connection:
        """
        获取线程安全的数据库连接

        每个线程维护自己的连接实例，避免多线程共享连接的问题。

        Returns:
            sqlite3.Connection 对象
        """
        if not hasattr(self._local, 'connection') or self._local.connection is None:
            self._local.connection = sqlite3.connect(
                self.db_path,
                check_same_thread=False,  # 允许多线程访问
                timeout=30.0              # 连接超时
            )
            self._local.connection.row_factory = sqlite3.Row  # 行工厂
        return self._local.connection

    @contextmanager
    def _transaction(self):
        """
        事务上下文管理器

        自动处理事务的提交和回滚。
        发生异常时自动回滚，正常结束时自动提交。
        """
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库事务错误: {e}")
            raise

    def _init_database(self) -> None:
        """
        初始化数据库表结构

        创建必要的表和索引（如果不存在）。
        确保数据库处于可用状态。
        """
        try:
            with self._transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(DatabaseSchema.SESSIONS_TABLE)
                cursor.execute(DatabaseSchema.METRICS_TABLE)
                cursor.execute(DatabaseSchema.MARKS_TABLE)
                cursor.execute(DatabaseSchema.INDEX_METRICS_SESSION)
                cursor.execute(DatabaseSchema.INDEX_METRICS_TIMESTAMP)
                cursor.execute(DatabaseSchema.INDEX_MARKS_SESSION)
            logger.info("数据库表结构初始化完成")
        except Exception as e:
            logger.error(f"数据库表结构初始化失败: {e}")
            raise

    def create_session(self, session: SessionInfo) -> None:
        """
        创建新的录制会话

        Args:
            session: 包含会话信息的 SessionInfo 对象
        """
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO sessions
                        (id, device_id, platform, package_name, start_time, status)
                        VALUES (?, ?, ?, ?, ?, ?)
                        """,
                        (
                            session.id,
                            session.device_id,
                            session.platform,
                            session.package_name,
                            session.start_time,
                            session.status,
                        )
                    )
                logger.debug(f"已创建会话: {session.id}")
            except sqlite3.IntegrityError:
                logger.warning(f"会话已存在: {session.id}")

    def update_session(self, session: SessionInfo) -> None:
        """
        更新会话信息

        采集结束后更新会话的结束时间、采样数、状态等字段。

        Args:
            session: 包含更新信息的 SessionInfo 对象
        """
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        UPDATE sessions
                        SET end_time = ?,
                            duration = ?,
                            sample_count = ?,
                            status = ?
                        WHERE id = ?
                        """,
                        (
                            session.end_time,
                            session.duration,
                            session.sample_count,
                            session.status,
                            session.id,
                        )
                    )
                logger.debug(f"已更新会话: {session.id}")
            except Exception as e:
                logger.error(f"更新会话失败: {e}")

    def record_metric(self, snapshot: MetricsSnapshot, session_id: str) -> None:
        """
        记录单条性能指标数据

        将 MetricsSnapshot 对象写入数据库的 metrics 表。
        该方法是非阻塞的，异常时只记录日志不会影响采集流程。

        Args:
            snapshot: 包含性能数据的 MetricsSnapshot 对象
            session_id: 所属会话 ID
        """
        try:
            with self._transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT INTO metrics (
                        session_id, timestamp, device_id, platform, package_name,
                        fps, fps_min, fps_max, frame_time_avg,
                        cpu_total, cpu_process,
                        memory_pss, memory_rss, memory_vss,
                        gpu, network_upload, network_download,
                        jank_count, big_jank_count, jank_rate,
                        temperature_cpu, temperature_battery, battery_level,
                        marks, metadata
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        session_id,
                        snapshot.timestamp,
                        snapshot.device_id,
                        snapshot.platform,
                        snapshot.package_name,
                        snapshot.fps.fps,
                        snapshot.fps.fps_min,
                        snapshot.fps.fps_max,
                        snapshot.fps.frame_time_avg,
                        snapshot.cpu.total,
                        snapshot.cpu.process,
                        snapshot.memory.pss,
                        snapshot.memory.rss,
                        snapshot.memory.vss,
                        snapshot.gpu.usage,
                        snapshot.network.upload,
                        snapshot.network.download,
                        snapshot.jank_stats.jank_count,
                        snapshot.jank_stats.big_jank_count,
                        snapshot.jank_stats.jank_rate,
                        snapshot.temperature.cpu,
                        snapshot.temperature.battery,
                        snapshot.battery_level,
                        "|".join(snapshot.marks) if snapshot.marks else "",
                        json.dumps(snapshot.metadata),
                    )
                )
                # 更新会话采样计数
                cursor.execute(
                    "UPDATE sessions SET sample_count = sample_count + 1 WHERE id = ?",
                    (session_id,),
                )
        except Exception as e:
            logger.error(f"记录指标数据失败: {e}")

    def add_mark(self, mark: Mark) -> None:
        """
        添加自定义标记

        Args:
            mark: 包含标记信息的 Mark 对象
        """
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT INTO marks (session_id, timestamp, mark_name, mark_type, metadata)
                        VALUES (?, ?, ?, ?, ?)
                        """,
                        (
                            mark.session_id,
                            mark.timestamp,
                            mark.name,
                            mark.mark_type,
                            json.dumps(mark.metadata),
                        )
                    )
                logger.debug(f"已添加标记: {mark.name} 在时间 {mark.timestamp}")
            except Exception as e:
                logger.error(f"添加标记失败: {e}")

    def get_session(self, session_id: str) -> Optional[SessionInfo]:
        """
        根据会话 ID 获取会话信息

        Args:
            session_id: 要查询的会话 ID

        Returns:
            SessionInfo 对象，如果不存在则返回 None
        """
        try:
            with self._transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM sessions WHERE id = ?",
                    (session_id,)
                )
                row = cursor.fetchone()
                if row:
                    return SessionInfo(
                        id=row["id"],
                        device_id=row["device_id"],
                        platform=row["platform"],
                        package_name=row["package_name"] or "",
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration=row["duration"],
                        sample_count=row["sample_count"],
                        status=row["status"],
                    )
        except Exception as e:
            logger.error(f"获取会话信息失败: {e}")
        return None

    def get_session_metrics(
        self,
        session_id: str,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[MetricsSnapshot]:
        """
        获取指定会话的所有指标数据

        Args:
            session_id: 要查询的会话 ID
            limit: 最大返回条数限制
            offset: 起始偏移量，用于分页

        Returns:
            MetricsSnapshot 对象列表，按时间戳升序排列
        """
        try:
            with self._transaction() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM metrics WHERE session_id = ? ORDER BY timestamp"
                params = [session_id]

                if limit is not None:
                    query += " LIMIT ? OFFSET ?"
                    params.extend([limit, offset])

                cursor.execute(query, params)
                rows = cursor.fetchall()

                snapshots = []
                for row in rows:
                    snapshot = self._row_to_snapshot(row)
                    snapshots.append(snapshot)

                return snapshots
        except Exception as e:
            logger.error(f"获取会话指标数据失败: {e}")
            return []

    def _row_to_snapshot(self, row: sqlite3.Row) -> MetricsSnapshot:
        """
        将数据库行转换为 MetricsSnapshot 对象

        Args:
            row: sqlite3.Row 对象

        Returns:
            反序列化的 MetricsSnapshot 对象
        """
        from perfsun.core.data_point import (
            FPSData, CPUData, MemoryData, GPUData,
            NetworkData, TemperatureData, JankStats
        )

        # 解析 FPS 数据
        fps = FPSData(
            fps=row["fps"] or 0.0,
            fps_min=row["fps_min"] or 0.0,
            fps_max=row["fps_max"] or 0.0,
            frame_time_avg=row["frame_time_avg"] or 0.0,
        )

        # 解析 CPU 数据
        cpu = CPUData(
            total=row["cpu_total"] or 0.0,
            process=row["cpu_process"] or 0.0,
        )

        # 解析内存数据
        memory = MemoryData(
            pss=row["memory_pss"] or 0.0,
            rss=row["memory_rss"] or 0.0,
            vss=row["memory_vss"] or 0.0,
        )

        # 解析 GPU 数据
        gpu = GPUData(usage=row["gpu"] or 0.0)

        # 解析网络数据
        network = NetworkData(
            upload=row["network_upload"] or 0.0,
            download=row["network_download"] or 0.0,
        )

        # 解析温度数据
        temperature = TemperatureData(
            cpu=row["temperature_cpu"] or 0.0,
            battery=row["temperature_battery"] or 0.0,
        )

        # 解析卡顿统计
        jank = JankStats(
            jank_count=row["jank_count"] or 0,
            big_jank_count=row["big_jank_count"] or 0,
            jank_rate=row["jank_rate"] or 0.0,
        )

        # 解析标记和元数据
        marks = row["marks"].split("|") if row["marks"] else []
        metadata = json.loads(row["metadata"]) if row["metadata"] else {}

        return MetricsSnapshot(
            timestamp=row["timestamp"],
            device_id=row["device_id"],
            platform=row["platform"],
            package_name=row["package_name"] or "",
            fps=fps,
            cpu=cpu,
            memory=memory,
            gpu=gpu,
            network=network,
            temperature=temperature,
            battery_level=row["battery_level"] or -1.0,
            jank_stats=jank,
            marks=marks,
            metadata=metadata,
        )

    def get_session_marks(self, session_id: str) -> List[Mark]:
        """
        获取指定会话的所有标记

        Args:
            session_id: 要查询的会话 ID

        Returns:
            Mark 对象列表，按时间戳升序排列
        """
        try:
            with self._transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "SELECT * FROM marks WHERE session_id = ? ORDER BY timestamp",
                    (session_id,)
                )
                rows = cursor.fetchall()

                marks = []
                for row in rows:
                    marks.append(Mark(
                        timestamp=row["timestamp"],
                        name=row["mark_name"],
                        mark_type=row["mark_type"],
                        session_id=row["session_id"],
                        metadata=json.loads(row["metadata"]) if row["metadata"] else {},
                    ))
                return marks
        except Exception as e:
            logger.error(f"获取会话标记失败: {e}")
            return []

    def list_sessions(
        self,
        device_id: Optional[str] = None,
        platform: Optional[str] = None,
        status: Optional[str] = None,
    ) -> List[SessionInfo]:
        """
        列出所有会话，支持按条件过滤

        Args:
            device_id: 按设备 ID 过滤
            platform: 按平台类型过滤
            status: 按会话状态过滤 (recording/completed/paused)

        Returns:
            SessionInfo 对象列表，按开始时间降序排列
        """
        try:
            with self._transaction() as conn:
                cursor = conn.cursor()
                query = "SELECT * FROM sessions WHERE 1=1"
                params = []

                if device_id:
                    query += " AND device_id = ?"
                    params.append(device_id)
                if platform:
                    query += " AND platform = ?"
                    params.append(platform)
                if status:
                    query += " AND status = ?"
                    params.append(status)

                query += " ORDER BY start_time DESC"

                cursor.execute(query, params)
                rows = cursor.fetchall()

                sessions = []
                for row in rows:
                    sessions.append(SessionInfo(
                        id=row["id"],
                        device_id=row["device_id"],
                        platform=row["platform"],
                        package_name=row["package_name"] or "",
                        start_time=row["start_time"],
                        end_time=row["end_time"],
                        duration=row["duration"],
                        sample_count=row["sample_count"],
                        status=row["status"],
                    ))
                return sessions
        except Exception as e:
            logger.error(f"列出会话失败: {e}")
            return []

    def delete_session(self, session_id: str) -> bool:
        """
        删除指定会话及其所有关联数据

        级联删除会话的指标数据和标记数据。

        Args:
            session_id: 要删除的会话 ID

        Returns:
            是否删除成功
        """
        with self._lock:
            try:
                with self._transaction() as conn:
                    cursor = conn.cursor()
                    # 删除关联的指标数据
                    cursor.execute("DELETE FROM metrics WHERE session_id = ?", (session_id,))
                    # 删除关联的标记数据
                    cursor.execute("DELETE FROM marks WHERE session_id = ?", (session_id,))
                    # 删除会话本身
                    cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
                logger.info(f"已删除会话及其关联数据: {session_id}")
                return True
            except Exception as e:
                logger.error(f"删除会话失败: {e}")
                return False

    def get_stats(self) -> Dict[str, Any]:
        """
        获取数据库统计信息

        返回会话数、指标数、标记数等总体统计。

        Returns:
            包含统计信息的字典
        """
        try:
            with self._transaction() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) as count FROM sessions")
                session_count = cursor.fetchone()["count"]

                cursor.execute("SELECT COUNT(*) as count FROM metrics")
                metric_count = cursor.fetchone()["count"]

                cursor.execute("SELECT COUNT(*) as count FROM marks")
                mark_count = cursor.fetchone()["count"]

                return {
                    "session_count": session_count,  # 会话总数
                    "metric_count": metric_count,    # 指标数据条数
                    "mark_count": mark_count,        # 标记总数
                    "db_path": self.db_path,          # 数据库路径
                }
        except Exception as e:
            logger.error(f"获取数据库统计信息失败: {e}")
            return {}

    def query_metrics_by_time_range(
        self,
        session_id: str,
        start_time: float,
        end_time: float,
    ) -> List[MetricsSnapshot]:
        """
        按时间范围查询指标数据

        Args:
            session_id: 会话 ID
            start_time: 起始时间戳
            end_time: 结束时间戳

        Returns:
            指定时间范围内的 MetricsSnapshot 列表
        """
        try:
            with self._transaction() as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT * FROM metrics
                    WHERE session_id = ? AND timestamp >= ? AND timestamp <= ?
                    ORDER BY timestamp
                    """,
                    (session_id, start_time, end_time)
                )
                rows = cursor.fetchall()
                return [self._row_to_snapshot(row) for row in rows]
        except Exception as e:
            logger.error(f"按时间范围查询失败: {e}")
            return []

    def close(self) -> None:
        """
        关闭数据库连接

        释放资源，应在不再需要记录器时调用。
        """
        if hasattr(self._local, 'connection') and self._local.connection:
            self._local.connection.close()
            self._local.connection = None
            logger.debug("数据库连接已关闭")
