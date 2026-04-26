"""
PerfSun 数据导出器

本模块负责将性能采集数据导出为多种格式，包括：
- CSV：适用于大数据量分析和 Excel 导入
- JSON：适用于 API 集成和 Web 前端展示
- Excel：适用于报告生成和图表展示（带格式美化）
- HTML：生成包含交互式图表的可视化报告（基于 Chart.js）

对标 PerfDog 的数据导出功能，提供完整的数据回放和报告能力。
"""

import csv
import json
import logging
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from dataclasses import dataclass

from perfsun.core.data_point import MetricsSnapshot, SessionInfo, Mark
from perfsun.core.data_recorder import DataRecorder


logger = logging.getLogger(__name__)


class ExportFormat:
    """
    支持的导出格式枚举
    """
    CSV = "csv"          # 逗号分隔值格式
    JSON = "json"        # JSON 数据交换格式
    EXCEL = "excel"      # Microsoft Excel 格式
    HTML = "html"        # HTML 交互式报告


@dataclass
class ExportOptions:
    """
    导出选项配置

    控制导出的格式、内容和附加信息。

    Attributes:
        format: 导出格式 (csv/json/excel/html)
        include_marks: 是否包含标记数据
        include_metadata: 是否包含元数据
        session_info: 会话信息（用于报告头）
        marks: 标记列表（用于报告中的标记表格）
    """
    format: str = ExportFormat.CSV
    include_marks: bool = True
    include_metadata: bool = False
    session_info: Optional[SessionInfo] = None
    marks: Optional[List[Mark]] = None


class DataExporter:
    """
    数据导出器

    负责将性能数据从数据库或内存中导出为多种文件格式。
    支持单会话导出和批量导出。

    Attributes:
        recorder: 可选的 DataRecorder 实例，用于从数据库读取数据
    """

    def __init__(self, recorder: Optional[DataRecorder] = None):
        """
        初始化数据导出器

        Args:
            recorder: 可选的 DataRecorder 实例。
                      提供后可以直接通过会话 ID 导出。
        """
        self.recorder = recorder
        # CSV 字段名定义，决定了 CSV 输出的列顺序和名称
        self._csv_fieldnames = [
            "timestamp",        # 时间戳
            "device_id",        # 设备ID
            "platform",         # 平台类型
            "package_name",     # 应用包名
            "fps",              # 帧率
            "fps_min",          # 最小帧率
            "fps_max",          # 最大帧率
            "frame_time_avg",   # 平均帧时间(ms)
            "cpu_total",        # 系统CPU使用率(%)
            "cpu_process",      # 进程CPU使用率(%)
            "memory_pss",       # PSS内存(MB)
            "memory_rss",       # RSS内存(MB)
            "memory_vss",       # VSS内存(MB)
            "gpu",              # GPU使用率(%)
            "network_upload",   # 网络上行(B/s)
            "network_download", # 网络下行(B/s)
            "jank_count",       # Jank次数
            "big_jank_count",   # BigJank次数
            "jank_rate",        # Jank率(%)
            "temperature_cpu",  # CPU温度(℃)
            "temperature_battery", # 电池温度(℃)
            "battery_level",    # 电池电量(%)
            "marks",            # 标记列表
        ]
        logger.info("数据导出器初始化完成")

    def export_session(
        self,
        session_id: str,
        output_path: str,
        options: Optional[ExportOptions] = None,
    ) -> bool:
        """
        从数据库导出指定会话的数据

        通过会话 ID 从 DataRecorder 读取数据并导出。

        Args:
            session_id: 会话 ID
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            是否导出成功
        """
        if not self.recorder:
            logger.error("没有可用的数据记录器")
            return False

        if options is None:
            options = ExportOptions()

        # 获取会话信息和标记
        options.session_info = self.recorder.get_session(session_id)
        options.marks = self.recorder.get_session_marks(session_id)
        snapshots = self.recorder.get_session_metrics(session_id)

        if not snapshots:
            logger.warning(f"会话 {session_id} 中没有数据")
            return False

        return self.export(snapshots, output_path, options)

    def export(
        self,
        snapshots: List[MetricsSnapshot],
        output_path: str,
        options: Optional[ExportOptions] = None,
    ) -> bool:
        """
        将 MetricsSnapshot 列表导出到文件

        根据导出格式调用对应的导出方法。

        Args:
            snapshots: MetricsSnapshot 列表
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            是否导出成功
        """
        if not snapshots:
            logger.warning("没有数据可导出")
            return False

        if options is None:
            options = ExportOptions()

        output_path = Path(output_path)
        export_format = options.format.lower()

        try:
            if export_format == ExportFormat.CSV:
                return self._export_csv(snapshots, output_path, options)
            elif export_format == ExportFormat.JSON:
                return self._export_json(snapshots, output_path, options)
            elif export_format == ExportFormat.EXCEL:
                return self._export_excel(snapshots, output_path, options)
            elif export_format == ExportFormat.HTML:
                return self._export_html(snapshots, output_path, options)
            else:
                logger.error(f"不支持的导出格式: {export_format}")
                return False

        except Exception as e:
            logger.error(f"导出失败: {e}")
            return False

    def _export_csv(
        self,
        snapshots: List[MetricsSnapshot],
        output_path: Path,
        options: ExportOptions,
    ) -> bool:
        """
        导出为 CSV 格式

        CSV 格式通用性强，适合导入 Excel 或进行数据分析。

        Args:
            snapshots: MetricsSnapshot 列表
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            是否导出成功
        """
        try:
            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.DictWriter(f, fieldnames=self._csv_fieldnames)
                writer.writeheader()

                for snapshot in snapshots:
                    row = snapshot.to_csv_row()
                    writer.writerow(row)

            logger.info(f"成功导出 {len(snapshots)} 条记录到 CSV: {output_path}")
            return True

        except Exception as e:
            logger.error(f"CSV 导出失败: {e}")
            return False

    def _export_json(
        self,
        snapshots: List[MetricsSnapshot],
        output_path: Path,
        options: ExportOptions,
    ) -> bool:
        """
        导出为 JSON 格式

        JSON 格式包含完整的结构化数据，适合程序处理。
        包含会话信息、标记和指标数据的嵌套结构。

        Args:
            snapshots: MetricsSnapshot 列表
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            是否导出成功
        """
        try:
            data = {
                "export_time": datetime.now().isoformat(),           # 导出时间
                "export_tool": "PerfSun",                              # 导出工具
                "export_version": "1.0.0",                             # 导出版本
                "session": options.session_info.to_dict() if options.session_info else None,
                "marks": [mark.to_dict() for mark in options.marks] if options.include_marks and options.marks else [],
                "metrics_count": len(snapshots),                       # 指标总数
                "metrics": [snapshot.to_dict() for snapshot in snapshots],
            }

            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)

            logger.info(f"成功导出 {len(snapshots)} 条记录到 JSON: {output_path}")
            return True

        except Exception as e:
            logger.error(f"JSON 导出失败: {e}")
            return False

    def _export_excel(
        self,
        snapshots: List[MetricsSnapshot],
        output_path: Path,
        options: ExportOptions,
    ) -> bool:
        """
        导出为 Excel 格式

        使用 pandas + xlsxwriter 生成格式丰富的 Excel 文件。
        包含多个工作表：指标数据、标记信息、会话摘要。
        数值列会自动设置合适的数字格式。

        Args:
            snapshots: MetricsSnapshot 列表
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            是否导出成功
        """
        try:
            import pandas as pd

            # 主数据表
            df_data = [snapshot.to_csv_row() for snapshot in snapshots]
            df = pd.DataFrame(df_data)

            with pd.ExcelWriter(output_path, engine='xlsxwriter') as writer:
                # 写入指标数据表
                df.to_excel(writer, sheet_name='指标数据', index=False)

                # 写入标记表
                if options.include_marks and options.marks:
                    marks_data = [mark.to_dict() for mark in options.marks]
                    marks_df = pd.DataFrame(marks_data)
                    marks_df.to_excel(writer, sheet_name='标记信息', index=False)

                # 写入会话摘要表
                if options.session_info:
                    summary_data = [{
                        "会话ID": options.session_info.id,
                        "设备ID": options.session_info.device_id,
                        "平台": options.session_info.platform,
                        "应用包名": options.session_info.package_name,
                        "开始时间": datetime.fromtimestamp(options.session_info.start_time).isoformat(),
                        "结束时间": datetime.fromtimestamp(options.session_info.end_time).isoformat() if options.session_info.end_time else "",
                        "持续时长": f"{options.session_info.duration:.2f}s",
                        "样本数量": options.session_info.sample_count,
                    }]
                    summary_df = pd.DataFrame(summary_data)
                    summary_df.to_excel(writer, sheet_name='会话摘要', index=False)

                # 设置 Excel 格式
                workbook = writer.book
                number_format = workbook.add_format({'num_format': '0.00'})

                # 为数值列设置格式
                worksheet = writer.sheets['指标数据']
                for idx, field in enumerate(self._csv_fieldnames):
                    if field in ['fps', 'fps_min', 'fps_max', 'frame_time_avg',
                                 'cpu_total', 'cpu_process', 'gpu', 'jank_rate',
                                 'temperature_cpu', 'temperature_battery']:
                        worksheet.set_column(idx, idx, 12, number_format)

            logger.info(f"成功导出 {len(snapshots)} 条记录到 Excel: {output_path}")
            return True

        except ImportError:
            logger.error("缺少 pandas 或 xlsxwriter 库，请安装: pip install pandas xlsxwriter")
            return False
        except Exception as e:
            logger.error(f"Excel 导出失败: {e}")
            return False

    def _export_html(
        self,
        snapshots: List[MetricsSnapshot],
        output_path: Path,
        options: ExportOptions,
    ) -> bool:
        """
        导出为 HTML 交互式报告

        使用 Chart.js 生成包含 FPS、CPU、内存等指标趋势图的
        交互式 HTML 报告。类似 PerfDog 的 Web 报告功能。

        Args:
            snapshots: MetricsSnapshot 列表
            output_path: 输出文件路径
            options: 导出选项

        Returns:
            是否导出成功
        """
        try:
            from jinja2 import Environment, BaseLoader, Template

            # 准备图表数据
            timestamps = [datetime.fromtimestamp(s.timestamp).strftime('%H:%M:%S') for s in snapshots]
            fps_values = [s.fps.fps for s in snapshots]
            cpu_values = [s.cpu.total for s in snapshots]
            memory_values = [s.memory.pss for s in snapshots]
            gpu_values = [s.gpu.usage for s in snapshots]
            jank_values = [s.jank_stats.jank_count + s.jank_stats.big_jank_count for s in snapshots]
            frame_time_values = [s.fps.frame_time_avg for s in snapshots]
            net_up_values = [s.network.upload for s in snapshots]
            net_down_values = [s.network.download for s in snapshots]
            temp_cpu_values = [s.temperature.cpu for s in snapshots]

            # 计算统计汇总
            valid_fps = [v for v in fps_values if v > 0]
            valid_cpu = [v for v in cpu_values if v > 0]
            valid_mem = [v for v in memory_values if v > 0]

            # 注册自定义 Jinja2 过滤器
            def timestamp_to_time(ts):
                """将 Unix 时间戳转换为 HH:MM:SS 格式"""
                return datetime.fromtimestamp(ts).strftime('%H:%M:%S')

            env = Environment(loader=BaseLoader())
            env.filters['timestamp_to_time'] = timestamp_to_time

            # 读取模板文件
            template_path = Path(__file__).parent.parent / "templates" / "report.html"
            if template_path.exists():
                with open(template_path, 'r', encoding='utf-8') as f:
                    template = env.from_string(f.read())
            else:
                template = env.from_string(self._get_default_html_template())

            # 渲染模板
            html_content = template.render(
                session=options.session_info,
                marks=options.marks if options.include_marks else [],
                timestamps=json.dumps(timestamps),
                fps_values=json.dumps(fps_values),
                cpu_values=json.dumps(cpu_values),
                memory_values=json.dumps(memory_values),
                gpu_values=json.dumps(gpu_values),
                jank_values=json.dumps(jank_values),
                frame_time_values=json.dumps(frame_time_values),
                net_up_values=json.dumps(net_up_values),
                net_down_values=json.dumps(net_down_values),
                temp_cpu_values=json.dumps(temp_cpu_values),
                metrics_count=len(snapshots),
                export_time=datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
                avg_fps=sum(valid_fps) / len(valid_fps) if valid_fps else 0,
                avg_cpu=sum(valid_cpu) / len(valid_cpu) if valid_cpu else 0,
                avg_memory=sum(valid_mem) / len(valid_mem) if valid_mem else 0,
                avg_gpu=sum(gpu_values) / len(gpu_values) if gpu_values else 0,
                total_janks=sum(jank_values) if jank_values else 0,
            )

            with open(output_path, 'w', encoding='utf-8') as f:
                f.write(html_content)

            logger.info(f"成功导出 HTML 报告: {output_path}")
            return True

        except ImportError:
            logger.error("缺少 jinja2 库，请安装: pip install jinja2")
            return False
        except Exception as e:
            logger.error(f"HTML 导出失败: {e}")
            return False

    def _get_default_html_template(self) -> str:
        """
        获取默认的 HTML 报告模板

        当模板文件不存在时使用的内嵌模板。
        生成包含多条趋势图和统计摘要的交互式报告。

        Returns:
            HTML 模板字符串
        """
        return """
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>PerfSun Performance Report</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; padding: 20px; }
        .container { max-width: 1400px; margin: 0 auto; }
        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; border-radius: 10px; margin-bottom: 20px; }
        .header h1 { font-size: 28px; margin-bottom: 10px; }
        .header .info { opacity: 0.9; font-size: 14px; }
        .summary { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .summary-card { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .summary-card h3 { color: #666; font-size: 12px; text-transform: uppercase; margin-bottom: 8px; }
        .summary-card .value { font-size: 28px; font-weight: bold; color: #333; }
        .summary-card .unit { font-size: 14px; color: #999; }
        .summary-card.good { border-left: 4px solid #22c55e; }
        .summary-card.warn { border-left: 4px solid #f97316; }
        .summary-card.bad { border-left: 4px solid #ef4444; }
        .chart-container { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); margin-bottom: 20px; }
        .chart-container h2 { font-size: 16px; color: #333; margin-bottom: 15px; }
        .chart-wrapper { position: relative; height: 300px; }
        .marks-table { background: white; padding: 20px; border-radius: 10px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
        .marks-table h2 { font-size: 16px; color: #333; margin-bottom: 15px; }
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #eee; }
        th { background: #f8f9fa; color: #666; font-weight: 600; }
        .footer { text-align: center; padding: 20px; color: #999; font-size: 12px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>PerfSun 性能报告</h1>
            <div class="info">
                {% if session %}
                设备: {{ session.device_id }} | 平台: {{ session.platform }} |
                应用: {{ session.package_name }} | 时长: {{ "%.2f"|format(session.duration) }}s |
                样本数: {{ metrics_count }}
                {% endif %}
            </div>
        </div>

        <div class="summary">
            <div class="summary-card {% if avg_fps >= 55 %}good{% elif avg_fps >= 30 %}warn{% else %}bad{% endif %}">
                <h3>平均帧率</h3>
                <div class="value">{{ "%.1f"|format(avg_fps) }}</div>
                <div class="unit">fps</div>
            </div>
            <div class="summary-card {% if avg_cpu < 50 %}good{% elif avg_cpu < 80 %}warn{% else %}bad{% endif %}">
                <h3>平均CPU</h3>
                <div class="value">{{ "%.1f"|format(avg_cpu) }}</div>
                <div class="unit">%</div>
            </div>
            <div class="summary-card">
                <h3>平均内存</h3>
                <div class="value">{{ "%.1f"|format(avg_memory) }}</div>
                <div class="unit">MB</div>
            </div>
            <div class="summary-card">
                <h3>平均GPU</h3>
                <div class="value">{{ "%.1f"|format(avg_gpu) }}</div>
                <div class="unit">%</div>
            </div>
            <div class="summary-card {% if total_janks == 0 %}good{% elif total_janks < 10 %}warn{% else %}bad{% endif %}">
                <h3>卡顿总数</h3>
                <div class="value">{{ total_janks }}</div>
                <div class="unit">次</div>
            </div>
            <div class="summary-card">
                <h3>数据点</h3>
                <div class="value">{{ metrics_count }}</div>
                <div class="unit">条</div>
            </div>
        </div>

        <div class="chart-container">
            <h2>帧率趋势 (FPS)</h2>
            <div class="chart-wrapper">
                <canvas id="fpsChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <h2>帧时间趋势 (Frame Time)</h2>
            <div class="chart-wrapper">
                <canvas id="frameTimeChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <h2>CPU & 内存使用率</h2>
            <div class="chart-wrapper">
                <canvas id="cpuMemoryChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <h2>GPU & 网络流量</h2>
            <div class="chart-wrapper">
                <canvas id="gpuNetworkChart"></canvas>
            </div>
        </div>

        <div class="chart-container">
            <h2>CPU温度趋势</h2>
            <div class="chart-wrapper">
                <canvas id="temperatureChart"></canvas>
            </div>
        </div>

        {% if marks %}
        <div class="marks-table">
            <h2>标记列表</h2>
            <table>
                <thead>
                    <tr>
                        <th>时间</th>
                        <th>标记名称</th>
                        <th>类型</th>
                    </tr>
                </thead>
                <tbody>
                    {% for mark in marks %}
                    <tr>
                        <td>{{ mark.timestamp | int | timestamp_to_time }}</td>
                        <td>{{ mark.name }}</td>
                        <td>{{ mark.mark_type }}</td>
                    </tr>
                    {% endfor %}
                </tbody>
            </table>
        </div>
        {% endif %}

        <div class="footer">
            由 PerfSun 于 {{ export_time }} 生成
        </div>
    </div>

    <script>
        const timestamps = {{ timestamps|safe }};
        const fpsValues = {{ fps_values|safe }};
        const cpuValues = {{ cpu_values|safe }};
        const memoryValues = {{ memory_values|safe }};
        const gpuValues = {{ gpu_values|safe }};
        const jankValues = {{ jank_values|safe }};
        const frameTimeValues = {{ frame_time_values|safe }};
        const netUpValues = {{ net_up_values|safe }};
        const netDownValues = {{ net_down_values|safe }};
        const tempCpuValues = {{ temp_cpu_values|safe }};

        // FPS 图表
        new Chart(document.getElementById('fpsChart'), {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [{
                    label: 'FPS',
                    data: fpsValues,
                    borderColor: '#667eea',
                    backgroundColor: 'rgba(102, 126, 234, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true, max: 120 } }
            }
        });

        // 帧时间图表
        new Chart(document.getElementById('frameTimeChart'), {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [{
                    label: 'Frame Time (ms)',
                    data: frameTimeValues,
                    borderColor: '#f97316',
                    backgroundColor: 'rgba(249, 115, 22, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: true } }
            }
        });

        // CPU & 内存图表
        new Chart(document.getElementById('cpuMemoryChart'), {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [
                    { label: 'CPU %', data: cpuValues, borderColor: '#f97316', backgroundColor: 'transparent', tension: 0.4, pointRadius: 0, yAxisID: 'y' },
                    { label: 'Memory MB', data: memoryValues, borderColor: '#22c55e', backgroundColor: 'transparent', tension: 0.4, pointRadius: 0, yAxisID: 'y1' }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    y: { type: 'linear', position: 'left', min: 0, max: 100, title: { display: true, text: 'CPU %' } },
                    y1: { type: 'linear', position: 'right', min: 0, title: { display: true, text: 'Memory MB' }, grid: { drawOnChartArea: false } }
                }
            }
        });

        // GPU & 网络图表
        new Chart(document.getElementById('gpuNetworkChart'), {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [
                    { label: 'GPU %', data: gpuValues, borderColor: '#a855f7', backgroundColor: 'transparent', tension: 0.4, pointRadius: 0, yAxisID: 'y' },
                    { label: 'Net Up B/s', data: netUpValues, borderColor: '#06b6d4', backgroundColor: 'transparent', tension: 0.4, pointRadius: 0, yAxisID: 'y1' },
                    { label: 'Net Down B/s', data: netDownValues, borderColor: '#ec4899', backgroundColor: 'transparent', tension: 0.4, pointRadius: 0, yAxisID: 'y1' }
                ]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    y: { type: 'linear', position: 'left', min: 0, max: 100, title: { display: true, text: 'GPU %' } },
                    y1: { type: 'linear', position: 'right', min: 0, title: { display: true, text: 'Network B/s' }, grid: { drawOnChartArea: false } }
                }
            }
        });

        // 温度图表
        new Chart(document.getElementById('temperatureChart'), {
            type: 'line',
            data: {
                labels: timestamps,
                datasets: [{
                    label: 'CPU Temperature (°C)',
                    data: tempCpuValues,
                    borderColor: '#ef4444',
                    backgroundColor: 'rgba(239, 68, 68, 0.1)',
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true, maintainAspectRatio: false,
                plugins: { legend: { display: false } },
                scales: { y: { beginAtZero: false, title: { display: true, text: '°C' } } }
            }
        });
    </script>
</body>
</html>
"""

    def export_batch(
        self,
        session_ids: List[str],
        output_dir: str,
        format: str = ExportFormat.CSV,
    ) -> Dict[str, bool]:
        """
        批量导出多个会话

        将多个会话分别导出到指定目录下的独立文件。

        Args:
            session_ids: 会话 ID 列表
            output_dir: 输出目录
            format: 导出格式

        Returns:
            字典，key 为 session_id，value 表示是否成功
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        results = {}
        for session_id in session_ids:
            output_path = output_dir / f"{session_id}.{format}"
            results[session_id] = self.export_session(
                session_id, str(output_path), ExportOptions(format=format)
            )

        return results
