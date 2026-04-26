"""
PerfSun 数据记录器单元测试

测试 SQLite 数据持久化功能：
- 会话创建和管理
- 指标数据记录
- 标记添加和查询
- 数据查询和时间范围过滤
"""

import pytest
import time
import tempfile
import os
import shutil
from datetime import datetime

from perfsun.core.data_recorder import DataRecorder
from perfsun.core.data_point import (
    MetricsSnapshot, SessionInfo, Mark,
    FPSData, CPUData, MemoryData, GPUData,
    NetworkData, TemperatureData, JankStats,
)


class TestDataRecorder:
    """DataRecorder 测试类"""

    def setup_method(self):
        """每个测试方法执行前的 setup，创建临时数据库"""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_perfsun.db")
        self.recorder = DataRecorder(db_path=self.db_path)
        self.session_id = "test_session_" + str(int(time.time() * 1000000))

    def teardown_method(self):
        """每个测试方法执行后的 cleanup"""
        self.recorder.close()
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_session(self) -> str:
        """创建测试会话并返回 session_id"""
        session = SessionInfo(
            id=self.session_id,
            device_id="test_device",
            platform="android",
            package_name="com.example.app",
            start_time=time.time(),
            status="recording",
            sample_count=0,
        )
        self.recorder.create_session(session)
        return self.session_id

    def _create_test_snapshot(self, timestamp: float, fps_value: float = 60.0) -> MetricsSnapshot:
        """创建测试指标快照"""
        return MetricsSnapshot(
            timestamp=timestamp,
            device_id="test_device",
            platform="android",
            package_name="com.example.app",
            fps=FPSData(fps=fps_value, fps_min=55.0, fps_max=62.0, frame_time_avg=16.67),
            cpu=CPUData(total=35.2, process=12.5),
            memory=MemoryData(pss=256.0, rss=512.0, vss=1024.0),
            gpu=GPUData(usage=28.0),
            network=NetworkData(upload=1024.0, download=2048.0),
            temperature=TemperatureData(cpu=42.5, battery=35.0),
            battery_level=85.0,
            jank_stats=JankStats(jank_count=0, big_jank_count=0, jank_rate=0.0),
        )

    # ─── 会话管理测试 ───────────────────────────────

    def test_create_session(self):
        """测试创建会话"""
        session_id = self._create_test_session()
        assert session_id == self.session_id

    def test_get_session(self):
        """测试获取会话"""
        self._create_test_session()
        session = self.recorder.get_session(self.session_id)

        assert session is not None
        assert session.device_id == "test_device"
        assert session.platform == "android"
        assert session.package_name == "com.example.app"
        assert session.status == "recording"

    def test_get_nonexistent_session(self):
        """测试获取不存在的会话"""
        session = self.recorder.get_session("nonexistent")
        assert session is None

    def test_update_session(self):
        """测试更新会话"""
        self._create_test_session()
        session = self.recorder.get_session(self.session_id)

        session.status = "completed"
        session.end_time = time.time()
        session.duration = 60.0
        session.sample_count = 100
        self.recorder.update_session(session)

        updated = self.recorder.get_session(self.session_id)
        assert updated.status == "completed"
        assert updated.sample_count == 100

    def test_list_sessions(self):
        """测试列出会话"""
        # 创建多个会话
        for i in range(3):
            session = SessionInfo(
                id=f"session_{i}",
                device_id="test_device",
                platform="android",
                package_name="com.example.app",
                start_time=time.time(),
                status="completed",
                end_time=time.time() + 60,
                duration=60.0,
                sample_count=10,
            )
            self.recorder.create_session(session)

        sessions = self.recorder.list_sessions()
        assert len(sessions) == 3

    def test_delete_session(self):
        """测试删除会话"""
        self._create_test_session()
        assert self.recorder.get_session(self.session_id) is not None

        self.recorder.delete_session(self.session_id)
        assert self.recorder.get_session(self.session_id) is None

    # ─── 指标记录测试 ───────────────────────────────

    def test_record_metric(self):
        """测试记录指标"""
        session_id = self._create_test_session()
        snapshot = self._create_test_snapshot(1000.0)

        self.recorder.record_metric(snapshot, session_id)

        # 验证指标已记录
        metrics = self.recorder.get_session_metrics(session_id)
        assert len(metrics) == 1

    def test_record_multiple_metrics(self):
        """测试记录多条指标"""
        session_id = self._create_test_session()

        for i in range(10):
            snapshot = self._create_test_snapshot(1000.0 + i, fps_value=60.0 - i)
            self.recorder.record_metric(snapshot, session_id)

        metrics = self.recorder.get_session_metrics(session_id)
        assert len(metrics) == 10

        # 验证 FPS 值正确
        assert metrics[0].fps.fps == 60.0
        assert metrics[9].fps.fps == 51.0

    def test_get_session_metrics_empty(self):
        """测试获取空会话指标"""
        self._create_test_session()
        metrics = self.recorder.get_session_metrics(self.session_id)
        assert len(metrics) == 0

    def test_record_metric_updates_sample_count(self):
        """测试记录指标后样本数更新"""
        session_id = self._create_test_session()

        for i in range(5):
            snapshot = self._create_test_snapshot(1000.0 + i)
            self.recorder.record_metric(snapshot, session_id)

        session = self.recorder.get_session(self.session_id)
        assert session.sample_count == 5

    # ─── 标记测试 ───────────────────────────────

    def test_add_mark(self):
        """测试添加标记"""
        session_id = self._create_test_session()
        mark = Mark(
            timestamp=time.time(),
            name="start_game",
            mark_type="user",
            session_id=session_id,
        )

        self.recorder.add_mark(mark)

        marks = self.recorder.get_session_marks(session_id)
        assert len(marks) == 1
        assert marks[0].name == "start_game"
        assert marks[0].mark_type == "user"

    def test_add_multiple_marks(self):
        """测试添加多个标记"""
        session_id = self._create_test_session()

        for i in range(3):
            mark = Mark(
                timestamp=time.time() + i,
                name=f"mark_{i}",
                mark_type="user",
                session_id=session_id,
            )
            self.recorder.add_mark(mark)

        marks = self.recorder.get_session_marks(session_id)
        assert len(marks) == 3

    # ─── 数据查询测试 ───────────────────────────────

    def test_query_metrics_by_time_range(self):
        """测试按时间范围查询指标"""
        session_id = self._create_test_session()

        for i in range(20):
            snapshot = self._create_test_snapshot(1000.0 + i * 2)  # 间隔2秒
            self.recorder.record_metric(snapshot, session_id)

        # 查询中间时间段
        results = self.recorder.query_metrics_by_time_range(
            session_id, 1005.0, 1025.0
        )
        assert len(results) > 0
        for r in results:
            assert 1005.0 <= r.timestamp <= 1025.0

    def test_get_stats(self):
        """测试获取统计信息"""
        self._create_test_session()
        snapshot = self._create_test_snapshot(1000.0)
        self.recorder.record_metric(snapshot, self.session_id)

        stats = self.recorder.get_stats()
        assert stats["session_count"] >= 1
        assert stats["metric_count"] >= 1
        assert "db_path" in stats

    # ─── 错误处理测试 ───────────────────────────────

    def test_record_metric_invalid_session(self):
        """测试记录指标到无效会话"""
        snapshot = self._create_test_snapshot(1000.0)
        # 不应抛出异常，应静默处理
        self.recorder.record_metric(snapshot, "nonexistent_session")

    def test_concurrent_session_creation(self):
        """测试并发创建会话（线程安全）"""
        import threading

        def create_session_thread(session_id: str):
            session = SessionInfo(
                id=session_id,
                device_id="test_device",
                platform="android",
                package_name="com.example.app",
                start_time=time.time(),
                status="completed",
            )
            self.recorder.create_session(session)

        threads = []
        for i in range(5):
            t = threading.Thread(target=create_session_thread, args=(f"concurrent_{i}",))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        sessions = self.recorder.list_sessions()
        concurrent_sessions = [s for s in sessions if s.id.startswith("concurrent_")]
        assert len(concurrent_sessions) == 5


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
