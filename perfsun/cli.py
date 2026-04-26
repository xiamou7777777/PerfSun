"""
PerfSun 命令行接口

本模块提供 PerfSun 工具的命令行界面，基于 Click + Rich 构建。
对标 PerfDog 的命令行和桌面工具功能。

功能列表：
- 设备检测和列表显示
- 实时性能数据采集（带实时仪表盘）
- 会话录制和管理
- 数据导出和 HTML 报告生成
- 自定义标记添加
- 数据库统计和系统信息
"""

import sys
import time
import logging
import uuid
from typing import Optional, List, Dict, Any
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.panel import Panel
from rich.live import Live
from rich.layout import Layout
from rich.text import Text
from rich.columns import Columns
from rich import box

from perfsun import __version__
from perfsun.core.collector_manager import CollectorManager
from perfsun.core.data_recorder import DataRecorder
from perfsun.core.data_exporter import DataExporter, ExportOptions, ExportFormat
from perfsun.core.data_point import MetricsSnapshot, Mark, SessionInfo, FPSData, CPUData, MemoryData
from perfsun.core.alert_manager import AlertManager, AlertRule, AlertCondition, AlertSeverity
from perfsun.collectors.base import CollectorConfig, CollectorError
from perfsun.collectors.android import AndroidCollector
from perfsun.collectors.ios import IOSCollector
from perfsun.collectors.windows import WindowsCollector
from perfsun.utils.adb import ADBTools
from perfsun.utils.power_estimator import PowerEstimator, DeviceType


console = Console()


def setup_logging(verbose: bool = False) -> None:
    """
    配置日志输出

    Args:
        verbose: 是否输出 DEBUG 级别的详细日志
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[logging.StreamHandler(sys.stdout)]
    )


def detect_android_devices() -> List[Dict[str, Any]]:
    """
    检测已连接的 Android 设备

    Returns:
        设备信息列表，每个设备包含 id、platform、model、state
    """
    try:
        adb = ADBTools()
        devices = adb.get_devices()
        android_devices = []

        for dev in devices:
            if dev.get('state') == 'device':
                device_info = {
                    'id': dev['id'],
                    'platform': 'android',
                    'model': adb.get_prop(dev['id'], 'ro.product.model') or 'Unknown',
                    'state': 'online',
                }
                android_devices.append(device_info)

        return android_devices

    except Exception as e:
        console.print(f"[red]检测 Android 设备失败: {e}[/red]")
        return []


def create_collector(platform: str, device_id: str, package_name: str, interval: float = 1.0):
    """
    创建指定平台的采集器

    Args:
        platform: 平台类型 (android/ios/windows)
        device_id: 设备 ID
        package_name: 目标包名
        interval: 采样间隔（秒）

    Returns:
        采集器实例

    Raises:
        ValueError: 不支持的平台
    """
    config = CollectorConfig(
        platform=platform,
        device_id=device_id,
        package_name=package_name,
        interval=interval,
    )

    if platform == 'android':
        return AndroidCollector(config)
    elif platform == 'ios':
        return IOSCollector(config)
    elif platform == 'windows':
        return WindowsCollector(config)
    else:
        raise ValueError(f"不支持的平台: {platform}")


def get_metric_color(value: float, metric_type: str) -> str:
    """
    根据指标值返回对应的 Rich 颜色

    用于实时仪表盘的颜色标记。

    Args:
        value: 指标值
        metric_type: 指标类型

    Returns:
        Rich 颜色字符串
    """
    if metric_type == 'fps':
        if value >= 55:
            return 'green'
        elif value >= 30:
            return 'yellow'
        else:
            return 'red'
    elif metric_type in ('cpu', 'gpu'):
        if value < 50:
            return 'green'
        elif value < 80:
            return 'yellow'
        else:
            return 'red'
    elif metric_type == 'memory':
        if value < 512:
            return 'green'
        elif value < 1024:
            return 'yellow'
        else:
            return 'red'
    elif metric_type == 'jank':
        return 'red' if value > 0 else 'green'
    return 'white'


def create_realtime_dashboard() -> Layout:
    """
    创建实时监控仪表盘布局

    构建一个分栏布局的实时数据展示界面，
    对标 PerfDog 的 HUD 实时显示。

    Returns:
        Rich Layout 对象
    """
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
    )
    layout["body"].split_row(
        Layout(name="metrics"),
        Layout(name="alerts", size=40),
    )

    return layout


@click.group()
@click.version_option(version=__version__)
@click.option('-v', '--verbose', is_flag=True, help='启用详细日志输出')
@click.pass_context
def cli(ctx, verbose):
    """
    PerfSun - 跨平台性能采集工具

    无需 ROOT/越狱即可采集设备性能数据，包括 FPS、CPU、内存、GPU 等指标。
    对标行业标杆 PerfDog。
    """
    ctx.ensure_object(dict)
    ctx.obj['verbose'] = verbose
    setup_logging(verbose)


@cli.command()
@click.pass_context
def devices(ctx):
    """
    列出所有已连接的设备

    检测并显示 Android、Windows 等平台的可用设备列表。
    """
    console.print("\n[bold cyan]PerfSun 设备检测[/bold cyan]\n")

    all_devices = []

    # 检测 Android 设备
    android_devices = detect_android_devices()
    all_devices.extend(android_devices)

    # Windows 本地设备
    if sys.platform == 'win32':
        all_devices.append({
            'id': 'localhost',
            'platform': 'windows',
            'model': '本地 Windows',
            'state': 'online',
        })

    if not all_devices:
        console.print("[yellow]未检测到任何设备[/yellow]")
        console.print("\n提示:")
        console.print("  - Android 设备需通过 USB 连接并启用 ADB 调试")
        console.print("  - iOS 设备需安装 pymobiledevice3 并连接 Mac")
        console.print("  - Windows 性能采集仅支持本地机器\n")
        return

    # 显示设备表格
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    table.add_column("平台", style="cyan", width=10)
    table.add_column("设备 ID", style="green")
    table.add_column("状态", width=10)
    table.add_column("型号", style="yellow")

    for device in all_devices:
        state_color = "[green]online[/green]" if device.get('state') == 'online' else "[red]offline[/red]"
        table.add_row(
            device.get('platform', 'unknown'),
            device.get('id', ''),
            state_color,
            device.get('model', 'Unknown'),
        )

    console.print(table)
    console.print(f"\n共检测到 [bold]{len(all_devices)}[/bold] 个设备\n")


@cli.command()
@click.option('-p', '--package', required=True, help='目标包名/BundleID/进程名')
@click.option('-d', '--device', default='', help='设备 ID（留空则自动选择）')
@click.option('--platform', type=click.Choice(['android', 'ios', 'windows', 'auto']), default='auto', help='平台类型')
@click.option('-i', '--interval', default=1.0, type=float, help='采样间隔（秒），默认 1.0')
@click.option('-o', '--output', help='输出文件路径')
@click.option('--format', 'export_format', type=click.Choice(['csv', 'json', 'excel', 'html']), default='csv', help='导出格式')
@click.option('--mark', 'marks', multiple=True, help='自定义标记，可多次使用')
@click.option('--duration', type=float, default=0, help='采集时长（秒），0 表示无限')
@click.option('--fps-only', is_flag=True, help='仅采集 FPS 数据')
@click.option('--cpu-only', is_flag=True, help='仅采集 CPU 数据')
@click.option('--memory-only', is_flag=True, help='仅采集内存数据')
@click.option('--dashboard/--no-dashboard', default=True, help='是否显示实时仪表盘')
@click.pass_context
def run(ctx, package, device, platform, interval, output, export_format, marks, duration,
        fps_only, cpu_only, memory_only, dashboard):
    """
    启动实时性能数据采集

    连接设备并开始采集性能数据，支持实时仪表盘显示。

    示例：
      perfsun run -p com.example.game
      perfsun run -p com.example.game -i 0.5 --duration 60
      perfsun run -p com.example.game -o data.csv --format csv
      perfsun run -p com.example.game -d 8ABC123456 --dashboard
    """
    console.print("\n[bold cyan]PerfSun 实时采集[/bold cyan]\n")

    verbose = ctx.obj.get('verbose', False)

    # 自动检测平台
    if platform == 'auto':
        if device and device != 'localhost':
            android_devices = detect_android_devices()
            if any(d['id'] == device for d in android_devices):
                platform = 'android'
            else:
                platform = 'android'
        elif sys.platform == 'win32':
            platform = 'windows'
        else:
            platform = 'android'

    # 自动选择设备
    if not device:
        if platform == 'android':
            android_devices = detect_android_devices()
            if android_devices:
                device = android_devices[0]['id']
            else:
                console.print("[red]错误: 未检测到 Android 设备[/red]")
                return
        elif platform == 'windows':
            device = 'localhost'
        else:
            console.print("[red]错误: iOS 设备需要指定 device ID[/red]")
            return

    # 创建采集配置
    config = CollectorConfig(
        platform=platform,
        device_id=device,
        package_name=package,
        interval=interval,
    )

    # 根据参数控制采集的指标
    if fps_only:
        config.enable_cpu = False
        config.enable_memory = False
        config.enable_gpu = False
        config.enable_network = False
        config.enable_temperature = False
    elif cpu_only:
        config.enable_fps = False
        config.enable_memory = False
        config.enable_gpu = False
        config.enable_network = False
        config.enable_temperature = False
    elif memory_only:
        config.enable_fps = False
        config.enable_cpu = False
        config.enable_gpu = False
        config.enable_network = False
        config.enable_temperature = False

    try:
        # 初始化采集器
        console.print(f"[green]创建 {platform} 采集器...[/green]")
        collector = create_collector(platform, device, package, interval)

        # 初始化数据记录器和导出器
        recorder = DataRecorder()
        exporter = DataExporter(recorder)

        # 初始化告警管理器
        alert_manager = AlertManager()

        # 初始化功耗估算器
        power_estimator = PowerEstimator(
            device_type=DeviceType.PHONE,
            cpu_cores=8,
            battery_capacity=4000,
        )

        # 创建会话
        session_id = str(uuid.uuid4())
        session = SessionInfo(
            id=session_id,
            device_id=device,
            platform=platform,
            package_name=package,
            start_time=time.time(),
            status='recording',
        )
        recorder.create_session(session)

        # 设置采集回调
        collector.on_sample = lambda snapshot: handle_sample(
            snapshot, recorder, session_id, alert_manager, power_estimator, dashboard
        )
        collector.start()

        console.print(f"[green]采集已启动![/green]")
        console.print(f"  平台: {platform}")
        console.print(f"  设备: {device}")
        console.print(f"  应用: {package}")
        console.print(f"  间隔: {interval}s")
        console.print(f"  会话 ID: {session_id}")
        console.print("\n按 Ctrl+C 停止采集...\n")

        # 添加初始标记
        for mark_name in marks:
            mark = Mark(
                timestamp=time.time(),
                name=mark_name,
                mark_type='user',
                session_id=session_id,
            )
            recorder.add_mark(mark)
            console.print(f"[yellow]已添加标记: {mark_name}[/yellow]")

        # 实时仪表盘变量
        latest_snapshot: Optional[MetricsSnapshot] = None
        start_time = time.time()
        sample_count = [0]

        # 实时仪表盘显示
        if dashboard:
            from rich.live import Live
            from rich.table import Table as RichTable

            def generate_dashboard() -> Panel:
                """生成实时仪表盘面板"""
                nonlocal latest_snapshot

                if latest_snapshot is None:
                    elapsed = time.time() - start_time
                    return Panel(
                        f"[yellow]等待数据中... ({elapsed:.0f}s)[/yellow]",
                        title="[bold cyan]PerfSun 实时仪表盘",
                        border_style="cyan"
                    )

                s = latest_snapshot
                elapsed = time.time() - start_time

                # 指标网格
                metrics_grid = RichTable.grid(padding=(0, 2))
                metrics_grid.add_row()

                # FPS 显示
                fps_color = get_metric_color(s.fps.fps, 'fps')
                metrics_table = RichTable(box=box.SIMPLE, show_header=False)
                metrics_table.add_column("指标", style="bold", width=12)
                metrics_table.add_column("数值", width=10)
                metrics_table.add_column("详情", width=20)
                metrics_table.add_row("FPS", f"[{fps_color}]{s.fps.fps:.1f}[/{fps_color}]",
                                      f"Min: {s.fps.fps_min:.1f} Max: {s.fps.fps_max:.1f}")
                metrics_table.add_row("帧时间", f"{s.fps.frame_time_avg:.1f}ms", "")
                metrics_table.add_row("Jank", f"[{'red' if s.jank_stats.jank_count > 0 else 'green'}]{s.jank_stats.jank_count}[/]",
                                      f"BigJank: {s.jank_stats.big_jank_count} 率: {s.jank_stats.jank_rate:.1f}%")

                # CPU 显示
                cpu_color = get_metric_color(s.cpu.total, 'cpu')
                metrics_table.add_row("CPU 总", f"[{cpu_color}]{s.cpu.total:.1f}%[/{cpu_color}]", "")
                metrics_table.add_row("CPU 进程", f"{s.cpu.process:.1f}%", "")

                # 内存显示
                mem_color = get_metric_color(s.memory.pss, 'memory')
                metrics_table.add_row("内存 PSS", f"[{mem_color}]{s.memory.pss:.1f}MB[/{mem_color}]",
                                      f"RSS: {s.memory.rss:.1f}MB")

                # GPU 显示
                gpu_color = get_metric_color(s.gpu.usage, 'gpu')
                metrics_table.add_row("GPU", f"[{gpu_color}]{s.gpu.usage:.1f}%[/{gpu_color}]", "")

                # 网络显示
                metrics_table.add_row("网络上行", f"{s.network.upload:.0f} B/s", "")
                metrics_table.add_row("网络下行", f"{s.network.download:.0f} B/s", "")

                # 温度显示
                metrics_table.add_row("CPU 温度", f"{s.temperature.cpu:.1f}°C", "")
                metrics_table.add_row("电池温度", f"{s.temperature.battery:.1f}°C", "")

                # 电池
                if s.battery_level >= 0:
                    metrics_table.add_row("电池电量", f"{s.battery_level:.0f}%", "")

                # 功耗估算
                power_est = power_estimator.estimate_from_snapshot(s)
                metrics_table.add_row("功耗", f"{power_est.total_power:.2f}W",
                                      f"放电: {power_est.battery_drain_rate:.1f}%/h")

                # 会话统计
                metrics_table.add_row("样本数", f"{sample_count[0]}", "")
                metrics_table.add_row("已采集", f"{elapsed:.0f}s", "")

                return Panel(
                    metrics_table,
                    title=f"[bold cyan]PerfSun 实时仪表盘 - {package}[/bold cyan]",
                    border_style="cyan",
                )

            # 使用 Live 显示实时仪表盘
            try:
                with Live(generate_dashboard(), refresh_per_second=4, console=console) as live:
                    while True:
                        time.sleep(interval)
                        elapsed = time.time() - start_time

                        if duration > 0 and elapsed >= duration:
                            break

                        live.update(generate_dashboard())

            except KeyboardInterrupt:
                pass
        else:
            # 非仪表盘模式：简单进度显示
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(),
                TextColumn("[progress.percentage]{task.percentage}%"),
                console=console,
            ) as progress:
                task = progress.add_task("[cyan]采集数据中...", total=None)

                while True:
                    time.sleep(1)
                    elapsed = time.time() - start_time

                    if duration > 0 and elapsed >= duration:
                        break

                    progress.update(
                        task,
                        description=f"[cyan]已采集 {elapsed:.0f}s, 样本数: {sample_count[0]}"
                    )

        # 停止采集
        collector.stop()

        # 更新会话信息
        session.end_time = time.time()
        session.update_duration()
        session.sample_count = sample_count[0]
        recorder.update_session(session)

        console.print("\n[green]采集已完成![/green]")
        console.print(f"  采集时长: {session.duration:.2f}s")
        console.print(f"  样本数量: {session.sample_count}")

        # 显示告警统计
        alert_stats = alert_manager.get_stats()
        if alert_stats['total_alerts'] > 0:
            console.print(f"  告警次数: [yellow]{alert_stats['total_alerts']}[/yellow]")

        # 导出数据
        if output:
            console.print(f"\n[cyan]导出数据到 {output}...[/cyan]")
            options = ExportOptions(format=export_format)
            if exporter.export_session(session_id, output, options):
                console.print(f"[green]导出成功: {output}[/green]")
            else:
                console.print(f"[red]导出失败[/red]")

    except CollectorError as e:
        console.print(f"\n[red]采集器错误: {e}[/red]")
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        if verbose:
            import traceback
            console.print(traceback.format_exc())


def handle_sample(snapshot: MetricsSnapshot, recorder: DataRecorder,
                  session_id: str, alert_manager: AlertManager,
                  power_estimator: Any, show_dashboard: bool) -> None:
    """
    处理采集到的数据样本

    负责将样本持久化到数据库、检查告警、估算功耗。

    Args:
        snapshot: 指标快照
        recorder: 数据记录器
        session_id: 会话 ID
        alert_manager: 告警管理器
        power_estimator: 功耗估算器
        show_dashboard: 是否显示仪表盘
    """
    try:
        # 记录到数据库
        recorder.record_metric(snapshot, session_id)

        # 检查告警
        alerts = alert_manager.check_snapshot(snapshot)
        if alerts and not show_dashboard:
            for alert in alerts:
                console.print(f"[yellow][!] {alert.message}[/yellow]")

    except Exception as e:
        logging.error(f"处理样本失败: {e}")


@cli.command()
@click.option('--session', help='会话 ID')
@click.option('--duration', type=float, default=60, help='录制时长（秒）')
@click.option('--export', 'export_format', type=click.Choice(['csv', 'json', 'excel', 'html']), help='导出格式')
@click.option('--output', help='输出路径')
@click.pass_context
def record(ctx, session, duration, export_format, output):
    """
    录制性能会话

    查看和导出录制会话的数据。

    示例：
      perfsun record --session SESSION_ID
      perfsun record --duration 60 --export csv --output data.csv
    """
    console.print("\n[bold cyan]PerfSun 会话录制[/bold cyan]\n")

    if not session:
        console.print("[yellow]未指定会话 ID，请先使用 'perfsun run' 开始采集[/yellow]")
        return

    recorder = DataRecorder()
    session_info = recorder.get_session(session)

    if not session_info:
        console.print(f"[red]会话不存在: {session}[/red]")
        return

    # 显示会话信息
    console.print(f"[green]会话信息:[/green]")
    console.print(f"  ID: {session_info.id}")
    console.print(f"  设备: {session_info.device_id}")
    console.print(f"  平台: {session_info.platform}")
    console.print(f"  应用: {session_info.package_name}")
    console.print(f"  状态: {session_info.status}")
    console.print(f"  样本数: {session_info.sample_count}")

    if session_info.status == 'recording':
        console.print("\n[yellow]该会话正在录制中，请先停止采集[/yellow]")
        return

    # 导出数据
    if export_format and output:
        exporter = DataExporter(recorder)
        options = ExportOptions(format=export_format)

        console.print(f"\n[cyan]导出数据到 {output}...[/cyan]")
        if exporter.export_session(session, output, options):
            console.print(f"[green]导出成功: {output}[/green]")
        else:
            console.print("[red]导出失败[/red]")

    console.print()


@cli.command()
@click.argument('mark_name')
@click.option('--session', help='会话 ID')
@click.pass_context
def mark(ctx, mark_name, session):
    """
    添加自定义标记

    用于在性能时间线上标记特定事件或场景。
    对标 PerfDog 的打点功能。

    示例：
      perfsun mark "scene_2_loaded"
      perfsun mark "button_clicked" --session SESSION_ID
    """
    console.print(f"\n[cyan]添加标记: {mark_name}[/cyan]\n")

    if not session:
        console.print("[yellow]未指定会话 ID，将创建新标记[/yellow]")
        return

    recorder = DataRecorder()

    mark = Mark(
        timestamp=time.time(),
        name=mark_name,
        mark_type='user',
        session_id=session,
    )

    recorder.add_mark(mark)
    console.print(f"[green]标记已添加: {mark_name}[/green]\n")


@cli.command()
@click.option('--session', required=True, help='会话 ID')
@click.option('--format', 'export_format', type=click.Choice(['csv', 'json', 'excel', 'html']), default='csv', help='导出格式')
@click.option('--output', required=True, help='输出文件路径')
@click.pass_context
def export(ctx, session, export_format, output):
    """
    导出会话数据

    将采集的数据导出为 CSV/JSON/Excel/HTML 格式。
    HTML 格式会生成包含交互式图表的可视化报告。

    示例：
      perfsun export --session SESSION_ID --format csv --output data.csv
      perfsun export --session SESSION_ID --format html --output report.html
    """
    console.print(f"\n[bold cyan]PerfSun 数据导出[/bold cyan]\n")

    recorder = DataRecorder()
    exporter = DataExporter(recorder)

    console.print(f"[cyan]导出会话 {session} 到 {output}...[/cyan]")

    options = ExportOptions(format=export_format)
    if exporter.export_session(session, output, options):
        console.print(f"[green]导出成功: {output}[/green]")
    else:
        console.print("[red]导出失败[/red]")


@cli.command()
@click.pass_context
def sessions(ctx):
    """
    列出所有录制会话

    显示所有已完成的录制会话列表和基本信息。
    """
    console.print("\n[bold cyan]PerfSun 会话列表[/bold cyan]\n")

    recorder = DataRecorder()
    all_sessions = recorder.list_sessions()

    if not all_sessions:
        console.print("[yellow]暂无录制会话[/yellow]")
        return

    # 会话表格
    table = Table(show_header=True, header_style="bold magenta", box=box.ROUNDED)
    table.add_column("会话ID", style="green", width=36)
    table.add_column("平台", style="cyan", width=10)
    table.add_column("设备", style="yellow")
    table.add_column("应用", style="blue")
    table.add_column("状态", width=10)
    table.add_column("时长(s)", width=10)
    table.add_column("样本数", width=10)

    for session in all_sessions:
        status_color = {
            'completed': '[green]完成[/green]',
            'recording': '[yellow]录制中[/yellow]',
            'paused': '[yellow]已暂停[/yellow]',
        }.get(session.status, session.status)
        table.add_row(
            session.id[:8] + "...",
            session.platform,
            session.device_id[:15],
            session.package_name[:15],
            status_color,
            f"{session.duration:.1f}",
            str(session.sample_count),
        )

    console.print(table)
    console.print()


@cli.command()
@click.option('--session', required=True, help='会话 ID')
@click.pass_context
def delete(ctx, session):
    """
    删除指定会话

    删除会话及其所有关联的指标数据和标记。

    示例：
      perfsun delete --session SESSION_ID
    """
    console.print(f"\n[bold cyan]删除会话: {session}[/bold cyan]\n")

    if not click.confirm("确认删除此会话？此操作不可恢复"):
        console.print("[yellow]已取消[/yellow]")
        return

    recorder = DataRecorder()
    if recorder.delete_session(session):
        console.print(f"[green]会话已删除: {session}[/green]")
    else:
        console.print(f"[red]删除失败[/red]")


@cli.command()
@click.pass_context
def stats(ctx):
    """
    显示数据库统计信息

    显示所有会话、指标数据和标记的总量统计。
    """
    console.print("\n[bold cyan]PerfSun 统计信息[/bold cyan]\n")

    recorder = DataRecorder()
    stats_info = recorder.get_stats()

    if not stats_info:
        console.print("[red]获取统计信息失败[/red]")
        return

    console.print(f"  会话数量: [green]{stats_info.get('session_count', 0)}[/green]")
    console.print(f"  指标数量: [green]{stats_info.get('metric_count', 0)}[/green]")
    console.print(f"  标记数量: [green]{stats_info.get('mark_count', 0)}[/green]")
    console.print(f"  数据库: [blue]{stats_info.get('db_path', 'unknown')}[/blue]\n")


@cli.command()
@click.pass_context
def info(ctx):
    """
    显示 PerfSun 版本和系统信息
    """
    console.print("\n[bold cyan]PerfSun 信息[/bold cyan]\n")
    console.print(f"  版本: [green]{__version__}[/green]")
    console.print(f"  Python: [blue]{sys.version.split()[0]}[/blue]")
    console.print(f"  平台: [blue]{sys.platform}[/blue]")

    # 检查关键依赖
    console.print("\n[bold]依赖检查:[/bold]")
    deps = {
        "click": None,
        "rich": None,
        "pandas": None,
        "numpy": None,
        "psutil": None,
        "jinja2": None,
    }
    for dep_name in deps:
        try:
            __import__(dep_name)
            console.print(f"  [green][OK][/green] {dep_name}")
        except ImportError:
            console.print(f"  [red][FAIL][/red] {dep_name}")

    console.print()


@cli.command()
@click.option('--session', help='会话 ID（可选）')
@click.pass_context
def alerts(ctx, session):
    """
    查看告警历史

    显示采集过程中的告警事件记录。

    示例：
      perfsun alerts                    # 查看所有告警
      perfsun alerts --session SID      # 查看指定会话的告警
    """
    console.print("\n[bold cyan]PerfSun 告警历史[/bold cyan]\n")

    # 从数据库读取告警（目前从内存告警管理器获取）
    console.print("[yellow]告警数据在采集过程中实时记录[/yellow]")
    console.print("请使用实时采集模式（run）查看告警\n")


@cli.command()
@click.pass_context
def gui(ctx):
    """
    启动图形界面

    启动 PerfSun 的桌面图形界面（需安装 PyQt6）。
    """
    console.print("\n[bold cyan]启动 PerfSun GUI...[/bold cyan]\n")
    try:
        from perfsun.gui import run_gui
        run_gui()
    except Exception as e:
        console.print(f"[red]GUI 模块导入失败: {e}[/red]")
        console.print("[yellow]请确保已安装依赖: pip install pillow[/yellow]")


def main():
    """
    PerfSun 主入口函数

    处理命令行参数并分派到对应的子命令。
    """
    try:
        cli(obj={})
    except KeyboardInterrupt:
        console.print("\n\n[yellow]已取消[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"\n[red]错误: {e}[/red]")
        sys.exit(1)


if __name__ == '__main__':
    main()
