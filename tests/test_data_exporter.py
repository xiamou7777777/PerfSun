"""
数据导出器单元测试

测试数据导出功能:
- CSV导出
- JSON导出
- Excel导出
- HTML导出
"""

import pytest
import json
import csv
import tempfile
import os
from datetime import datetime
from pathlib import Path

from perfsun.core.data_point import (
    MetricsSnapshot, FPSData, CPUData, MemoryData,
    GPUData, NetworkData, TemperatureData, JankStats, SessionInfo, Mark
)
from perfsun.core.data_exporter import DataExporter, ExportOptions, ExportFormat


class TestDataExporter:
    """
    DataExporter测试类
    """

    def setup_method(self):
        """
        每个测试方法执行前的setup
        """
        self.exporter = DataExporter()

        self.sample_snapshot = MetricsSnapshot(
            timestamp=1713456789.123,
            device_id="test_device",
            platform="android",
            package_name="com.example.app",
            fps=FPSData(fps=58.5, fps_min=45.0, fps_max=62.0, frame_time_avg=17.1),
            cpu=CPUData(total=35.2, process=12.5),
            memory=MemoryData(pss=256.0, rss=512.0, vss=1024.0),
            gpu=GPUData(usage=28.0),
            network=NetworkData(upload=1024.0, download=2048.0),
            temperature=TemperatureData(cpu=42.5, battery=35.0),
            battery_level=85.0,
            jank_stats=JankStats(jank_count=2, big_jank_count=0, jank_rate=0.5),
            marks=["start_game"],
        )

        self.sample_session = SessionInfo(
            id="test_session_123",
            device_id="test_device",
            platform="android",
            package_name="com.example.app",
            start_time=1713456789.0,
            end_time=1713456790.0,
            duration=1.0,
            sample_count=10,
            status="completed",
        )

        self.sample_marks = [
            Mark(timestamp=1713456789.5, name="start_game", mark_type="user", session_id="test_session_123"),
            Mark(timestamp=1713456790.0, name="level_2", mark_type="scene", session_id="test_session_123"),
        ]

    def test_export_csv(self):
        """
        测试CSV导出
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            snapshots = [self.sample_snapshot]
            options = ExportOptions(format=ExportFormat.CSV)

            result = self.exporter.export(snapshots, output_path, options)

            assert result is True
            assert os.path.exists(output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 1
                assert rows[0]['fps'] == '58.5'
                assert rows[0]['device_id'] == 'test_device'

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_export_json(self):
        """
        测试JSON导出
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            output_path = f.name

        try:
            snapshots = [self.sample_snapshot]
            options = ExportOptions(
                format=ExportFormat.JSON,
                session_info=self.sample_session,
                marks=self.sample_marks,
            )

            result = self.exporter.export(snapshots, output_path, options)

            assert result is True
            assert os.path.exists(output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                assert 'metrics' in data
                assert 'session' in data
                assert 'marks' in data
                assert len(data['metrics']) == 1

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_export_excel(self):
        """
        测试Excel导出
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xlsx', delete=False) as f:
            output_path = f.name

        try:
            snapshots = [self.sample_snapshot]
            options = ExportOptions(format=ExportFormat.EXCEL)

            result = self.exporter.export(snapshots, output_path, options)

            assert result is True
            assert os.path.exists(output_path)

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_export_html(self):
        """
        测试HTML导出
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as f:
            output_path = f.name

        try:
            snapshots = [self.sample_snapshot]
            options = ExportOptions(
                format=ExportFormat.HTML,
                session_info=self.sample_session,
                marks=self.sample_marks,
            )

            result = self.exporter.export(snapshots, output_path, options)

            assert result is True
            assert os.path.exists(output_path)

            with open(output_path, 'r', encoding='utf-8') as f:
                content = f.read()
                assert 'PerfSun 性能报告' in content
                assert 'Chart' in content or 'chart' in content.lower()

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_export_empty_snapshots(self):
        """
        测试空数据导出
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            result = self.exporter.export([], output_path)

            assert result is False

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_export_batch(self):
        """
        测试批量导出
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            session_ids = ["session1", "session2", "session3"]

            results = self.exporter.export_batch(
                session_ids,
                tmpdir,
                format=ExportFormat.CSV
            )

            for session_id, success in results.items():
                assert success is False

    def test_multiple_snapshots_csv(self):
        """
        测试多快照CSV导出
        """
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
            output_path = f.name

        try:
            snapshots = []
            for i in range(10):
                snapshot = MetricsSnapshot(
                    timestamp=1713456789.0 + i,
                    device_id="test_device",
                    platform="android",
                    fps=FPSData(fps=60.0 - i * 0.5),
                )
                snapshots.append(snapshot)

            options = ExportOptions(format=ExportFormat.CSV)
            result = self.exporter.export(snapshots, output_path, options)

            assert result is True

            with open(output_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                rows = list(reader)
                assert len(rows) == 10

        finally:
            if os.path.exists(output_path):
                os.unlink(output_path)

    def test_csv_fieldnames(self):
        """
        测试CSV字段名
        """
        expected_fields = [
            "timestamp", "device_id", "platform", "package_name",
            "fps", "fps_min", "fps_max", "frame_time_avg",
            "cpu_total", "cpu_process", "memory_pss", "memory_rss", "memory_vss",
            "gpu", "network_upload", "network_download",
            "jank_count", "big_jank_count", "jank_rate",
            "temperature_cpu", "temperature_battery", "battery_level", "marks",
        ]

        assert self.exporter._csv_fieldnames == expected_fields


class TestMetricsSnapshot:
    """
    MetricsSnapshot测试类
    """

    def test_to_csv_row(self):
        """
        测试转换为CSV行
        """
        snapshot = MetricsSnapshot(
            timestamp=1713456789.123,
            device_id="test_device",
            platform="android",
            package_name="com.example.app",
            fps=FPSData(fps=58.5),
            cpu=CPUData(total=35.2, process=12.5),
            memory=MemoryData(pss=256.0, rss=512.0, vss=1024.0),
            jank_stats=JankStats(jank_count=2, big_jank_count=0),
        )

        row = snapshot.to_csv_row()

        assert row['timestamp'] == 1713456789.123
        assert row['device_id'] == 'test_device'
        assert row['platform'] == 'android'
        assert row['fps'] == 58.5
        assert row['cpu_total'] == 35.2
        assert row['memory_pss'] == 256.0

    def test_to_dict(self):
        """
        测试转换为字典
        """
        snapshot = MetricsSnapshot(
            timestamp=1713456789.123,
            device_id="test_device",
            platform="android",
        )

        data = snapshot.to_dict()

        assert data['timestamp'] == 1713456789.123
        assert data['device_id'] == 'test_device'
        assert 'metrics' in data
        assert 'fps' in data['metrics']
        assert 'cpu' in data['metrics']
        assert 'memory' in data['metrics']

    def test_to_json(self):
        """
        测试转换为JSON
        """
        snapshot = MetricsSnapshot(
            timestamp=1713456789.123,
            device_id="test_device",
            platform="android",
        )

        json_str = snapshot.to_json()

        data = json.loads(json_str)
        assert data['timestamp'] == 1713456789.123
        assert data['device_id'] == 'test_device'

    def test_datetime_property(self):
        """
        测试datetime属性
        """
        snapshot = MetricsSnapshot(
            timestamp=1713456789.0,
            device_id="test_device",
            platform="android",
        )

        dt = snapshot.datetime
        assert isinstance(dt, datetime)
        assert dt.timestamp() == 1713456789.0


class TestExportOptions:
    """
    ExportOptions测试类
    """

    def test_default_options(self):
        """
        测试默认选项
        """
        options = ExportOptions()

        assert options.format == ExportFormat.CSV
        assert options.include_marks is True
        assert options.include_metadata is False
        assert options.session_info is None
        assert options.marks is None

    def test_custom_options(self):
        """
        测试自定义选项
        """
        session = SessionInfo(
            id="test",
            device_id="device",
            platform="android",
            package_name="com.example",
            start_time=1234567890.0,
        )

        options = ExportOptions(
            format=ExportFormat.JSON,
            include_marks=False,
            session_info=session,
        )

        assert options.format == ExportFormat.JSON
        assert options.include_marks is False
        assert options.session_info == session


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
