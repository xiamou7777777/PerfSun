"""
PerfSun 主窗口 — 对标 PerfDog 的专业性能监控界面

采用深色主题、窄侧边栏 + 图表主体的布局。
Phase 1: 视觉重构，使用模拟数据
Phase 2: 接入真实采集后端
"""

import time
import random
import queue
import threading
import tkinter as tk
from tkinter import ttk, messagebox

from perfsun.gui.theme import AppTheme
from perfsun.gui.components import MetricCard, Sidebar, StatusBar
from perfsun.gui.charts import TimeSeriesChart


class PerfSunApp:
    """
    PerfSun 主应用窗口

    PerfDog 风格布局:
    顶部: 标题 + 设备/应用选择
    侧边栏: 控制按钮 (开始/停止/标记/导出/设置)
    主体: 指标卡片行 + 图表区域 (主视觉焦点)
    底部: 状态栏
    """

    def __init__(self):
        """初始化主窗口"""
        self.root = tk.Tk()
        self.root.title("PerfSun - Performance Profiler")
        self.root.geometry("1400x850")
        self.root.minsize(1100, 650)
        self.root.configure(bg=AppTheme.BG_PRIMARY)

        # ── 状态变量 ──
        self._is_recording = False
        self._session_id = None
        self._start_time = None
        self._sample_count = 0

        # 设备/应用选择
        self._devices = []
        self._apps = []
        self._selected_device = None
        self._selected_app = None

        # 数据队列 (Phase 2: 采集线程 → Queue → 主线程)
        self._data_queue = queue.Queue()

        # 图表引用
        self._charts = {}
        self._cards = {}

        # ── 构建界面 ──
        self._build_ui()
        self._init_charts()

        # ── 启动主循环 ──
        self.root.after(500, self._update_loop)

        # 自动检测设备
        self.root.after(1000, self._detect_devices)

    # ── UI 构建 ─────────────────────────────────

    def _build_ui(self):
        """构建完整界面布局"""
        main_container = tk.Frame(self.root, bg=AppTheme.BG_PRIMARY)
        main_container.pack(fill=tk.BOTH, expand=True)

        # ========== 顶部标题栏 ==========
        self._build_header(main_container)

        # ========== 主体区域 ==========
        body = tk.Frame(main_container, bg=AppTheme.BG_PRIMARY)
        body.pack(fill=tk.BOTH, expand=True)

        # 侧边栏 (左)
        self._build_sidebar(body)

        # 右侧内容区
        right_area = tk.Frame(body, bg=AppTheme.BG_PRIMARY)
        right_area.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)

        # 指标卡片行 (顶部)
        self._build_metric_cards(right_area)

        # 图表区域 (主体)
        self._build_chart_area(right_area)

        # ========== 底部状态栏 ==========
        self._build_status_bar(main_container)

    def _build_header(self, parent):
        """构建顶部标题栏"""
        header = tk.Frame(parent, bg=AppTheme.BG_SECONDARY,
                          height=AppTheme.HEADER_HEIGHT)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        # 左侧: 标题
        title_frame = tk.Frame(header, bg=AppTheme.BG_SECONDARY)
        title_frame.pack(side=tk.LEFT, padx=15, pady=10)

        tk.Label(
            title_frame, text="PerfSun",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.BG_SECONDARY, fg=AppTheme.TEXT_PRIMARY
        ).pack(side=tk.LEFT)

        tk.Label(
            title_frame, text="  v1.0.0",
            font=AppTheme.FONT_NORMAL,
            bg=AppTheme.BG_SECONDARY, fg=AppTheme.TEXT_SECONDARY
        ).pack(side=tk.LEFT)

        # 右侧: 设备 + 应用选择
        selector_frame = tk.Frame(header, bg=AppTheme.BG_SECONDARY)
        selector_frame.pack(side=tk.RIGHT, padx=15, pady=10)

        # 设备下拉
        tk.Label(
            selector_frame, text="Device:",
            font=AppTheme.FONT_NORMAL,
            bg=AppTheme.BG_SECONDARY, fg=AppTheme.TEXT_SECONDARY
        ).pack(side=tk.LEFT, padx=(0, 5))

        self._device_var = tk.StringVar()
        self._device_combo = ttk.Combobox(
            selector_frame, textvariable=self._device_var,
            state="readonly", width=25,
            font=AppTheme.FONT_NORMAL
        )
        self._device_combo.pack(side=tk.LEFT, padx=(0, 15))
        self._device_combo.bind("<<ComboboxSelected>>", self._on_device_changed)

        # 应用下拉
        tk.Label(
            selector_frame, text="App:",
            font=AppTheme.FONT_NORMAL,
            bg=AppTheme.BG_SECONDARY, fg=AppTheme.TEXT_SECONDARY
        ).pack(side=tk.LEFT, padx=(0, 5))

        self._app_var = tk.StringVar()
        self._app_combo = ttk.Combobox(
            selector_frame, textvariable=self._app_var,
            state="readonly", width=25,
            font=AppTheme.FONT_NORMAL
        )
        self._app_combo.pack(side=tk.LEFT)
        self._app_combo.bind("<<ComboboxSelected>>", self._on_app_changed)

        # 选择器样式
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(
            "TCombobox",
            fieldbackground=AppTheme.BG_INPUT,
            background=AppTheme.BG_TERTIARY,
            foreground=AppTheme.TEXT_PRIMARY,
            arrowcolor=AppTheme.TEXT_SECONDARY,
            selectbackground=AppTheme.BG_TERTIARY,
            selectforeground=AppTheme.TEXT_PRIMARY,
        )
        style.map(
            "TCombobox",
            fieldbackground=[("readonly", AppTheme.BG_INPUT)]
        )

    def _build_sidebar(self, parent):
        """构建侧边栏"""
        self._sidebar = Sidebar(parent, callbacks={
            "on_start": self._on_start_recording,
            "on_stop": self._on_stop_recording,
            "on_mark": self._on_add_mark,
            "on_export": self._on_export,
            "on_settings": self._on_settings,
        })
        self._sidebar.pack(side=tk.LEFT, fill=tk.Y)

        # 分隔线
        separator = tk.Frame(parent, width=1, bg=AppTheme.BORDER)
        separator.pack(side=tk.LEFT, fill=tk.Y)

    def _build_metric_cards(self, parent):
        """构建指标卡片行"""
        cards_frame = tk.Frame(parent, bg=AppTheme.BG_PRIMARY)
        cards_frame.pack(fill=tk.X, padx=15, pady=(15, 10))

        metrics_config = [
            ("FPS", AppTheme.FPS, ""),
            ("CPU", AppTheme.CPU, "%"),
            ("Memory", AppTheme.MEMORY, "MB"),
            ("GPU", AppTheme.GPU, "%"),
            ("Network", AppTheme.NETWORK, "KB/s"),
            ("Temp", AppTheme.TEMPERATURE, "°C"),
            ("Power", AppTheme.POWER, "W"),
        ]

        for key, color, unit in metrics_config:
            card = MetricCard(cards_frame, key, color, unit)
            card.pack(side=tk.LEFT, padx=(0, 8))
            self._cards[key.lower()] = card

    def _build_chart_area(self, parent):
        """构建图表区域"""
        chart_container = tk.Frame(parent, bg=AppTheme.BG_PRIMARY)
        chart_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=(0, 15))

        # 图表标签栏
        tab_bar = tk.Frame(chart_container, bg=AppTheme.BG_PRIMARY)
        tab_bar.pack(fill=tk.X, pady=(0, 5))

        self._chart_tabs = ["FPS", "CPU", "Memory", "GPU", "Network", "Temperature"]
        self._active_tab = tk.StringVar(value="FPS")

        for tab_name in self._chart_tabs:
            bg = AppTheme.BG_TERTIARY if tab_name == "FPS" else AppTheme.BG_PRIMARY
            btn = tk.Label(
                tab_bar, text=tab_name,
                font=AppTheme.FONT_HEADER,
                bg=bg, fg=AppTheme.TEXT_PRIMARY,
                padx=14, pady=4, cursor="hand2"
            )
            btn.pack(side=tk.LEFT, padx=(0, 2))
            btn.bind("<Button-1>", lambda e, t=tab_name: self._switch_chart(t))

        # Canvas 图表容器 (2x2 网格)
        self._chart_grid = tk.Frame(chart_container, bg=AppTheme.BG_PRIMARY)
        self._chart_grid.pack(fill=tk.BOTH, expand=True)

    def _build_status_bar(self, parent):
        """构建底部状态栏"""
        self._status_bar = StatusBar(parent)
        self._status_bar.pack(fill=tk.X, side=tk.BOTTOM)

    # ── 图表初始化 ───────────────────────────────

    def _init_charts(self):
        """初始化图表 (延迟到布局稳定后)"""
        self.root.after(200, self._create_charts)

    def _create_charts(self):
        """创建图表实例"""
        grid = self._chart_grid
        for child in grid.winfo_children():
            child.destroy()

        # 清空引用
        self._charts.clear()

        # 2 行 2 列 (或根据屏幕调整)
        row1 = tk.Frame(grid, bg=AppTheme.BG_PRIMARY)
        row1.pack(fill=tk.BOTH, expand=True)

        row2 = tk.Frame(grid, bg=AppTheme.BG_PRIMARY)
        row2.pack(fill=tk.BOTH, expand=True)

        chart_configs = [
            ("fps", "FPS", AppTheme.FPS, 0, 120, "fps"),
            ("cpu", "CPU", AppTheme.CPU, 0, 100, "%"),
            ("memory", "Memory", AppTheme.MEMORY, 0, None, "MB"),
            ("gpu", "GPU", AppTheme.GPU, 0, 100, "%"),
            ("network", "Network", AppTheme.NETWORK, 0, None, "KB/s"),
            ("temperature", "Temperature", AppTheme.TEMPERATURE, 0, 100, "°C"),
        ]

        # 只显示前 4 个 (2x2 网格), 其余通过 tab 切换
        for key, label, color, y_min, y_max, unit in chart_configs[:4]:
            parent = row1 if len(self._charts) < 2 else row2
            side = tk.LEFT if len(self._charts) % 2 == 0 else tk.RIGHT

            chart = TimeSeriesChart(
                parent, key, label, color,
                y_min=y_min, y_max=y_max, unit=unit,
                height=200
            )
            chart.pack(side=side, fill=tk.BOTH, expand=True, padx=4, pady=4)
            self._charts[key] = chart

        # 如果尚未在 tab 中显示的图表也创建 (隐藏)
        for key, label, color, y_min, y_max, unit in chart_configs[4:]:
            chart = TimeSeriesChart(
                grid, key, label, color,
                y_min=y_min, y_max=y_max, unit=unit,
                height=200
            )
            self._charts[key] = chart

    def _switch_chart(self, tab_name):
        """切换图表 Tab"""
        self._active_tab.set(tab_name)

        # 更新 Tab 按钮样式
        for child in self._chart_grid.master.winfo_children():
            if isinstance(child, tk.Frame) and child != self._chart_grid:
                for btn in child.winfo_children():
                    if isinstance(btn, tk.Label):
                        if btn.cget("text") == tab_name:
                            btn.config(bg=AppTheme.BG_TERTIARY)
                        else:
                            btn.config(bg=AppTheme.BG_PRIMARY)

        # TODO: Phase 2 实现图表切换显示
        # 目前 2x2 网格固定显示前 4 个

    # ── 设备/应用管理 ───────────────────────────

    def _detect_devices(self):
        """检测设备 (Phase 1: 模拟)"""
        self._devices = [
            {"id": "localhost", "platform": "windows",
             "model": "Local Machine", "state": "online"},
            {"id": "emulator-5554", "platform": "android",
             "model": "Pixel 7 API 33", "state": "online"},
        ]

        names = [f"{d['platform'].upper()}: {d['id']} ({d['model']})"
                 for d in self._devices]
        self._device_combo["values"] = names
        if names:
            self._device_combo.current(0)
            self._selected_device = self._devices[0]
            self._detect_apps()

    def _detect_apps(self):
        """检测应用 (Phase 1: 模拟)"""
        self._apps = [
            {"name": "Chrome", "package": "chrome.exe", "platform": "windows"},
            {"name": "Notepad", "package": "notepad.exe", "platform": "windows"},
            {"name": "Code", "package": "Code.exe", "platform": "windows"},
            {"name": "Spotify", "package": "Spotify.exe", "platform": "windows"},
            {"name": "Explorer", "package": "explorer.exe", "platform": "windows"},
        ]

        names = [a["name"] for a in self._apps]
        self._app_combo["values"] = names
        if names:
            self._app_combo.current(0)
            self._selected_app = self._apps[0]

    def _on_device_changed(self, event=None):
        """设备选择变化"""
        selection = self._device_combo.get()
        for dev in self._devices:
            name = f"{dev['platform'].upper()}: {dev['id']} ({dev['model']})"
            if name == selection:
                self._selected_device = dev
                break

    def _on_app_changed(self, event=None):
        """应用选择变化"""
        selection = self._app_combo.get()
        for app in self._apps:
            if app["name"] == selection:
                self._selected_app = app
                break

    # ── 录制控制 ─────────────────────────────────

    def _on_start_recording(self):
        """开始录制"""
        if not self._selected_device:
            messagebox.showwarning("Warning", "Please select a device first")
            return
        if not self._selected_app:
            messagebox.showwarning("Warning", "Please select an application first")
            return

        self._is_recording = True
        self._start_time = time.time()
        self._sample_count = 0

        # 更新 UI 状态
        self._sidebar.set_recording_state(True)
        self._status_bar.update_recording(True)

        # 清空图表数据
        for chart in self._charts.values():
            chart.clear()

        # 清空数据队列
        while not self._data_queue.empty():
            try:
                self._data_queue.get_nowait()
            except queue.Empty:
                break

        self._status_bar.update_samples(0)
        self._status_bar.update_elapsed(0)

    def _on_stop_recording(self):
        """停止录制"""
        self._is_recording = False

        duration = time.time() - self._start_time if self._start_time else 0
        self._sidebar.set_recording_state(False)
        self._status_bar.update_recording(False)

        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        secs = int(duration % 60)
        self._status_bar.time_label.config(
            text=f"{hours:02d}:{minutes:02d}:{secs:02d}"
        )

    def _on_add_mark(self):
        """添加标记"""
        if not self._is_recording:
            messagebox.showinfo("Info", "Start recording first to add marks.")
            return

        # Phase 2: 打开标记对话框
        messagebox.showinfo("Mark", f"Mark added at {time.strftime('%H:%M:%S')}")

    def _on_export(self):
        """导出数据"""
        if not self._is_recording and self._sample_count == 0:
            messagebox.showinfo("Info", "No data to export. Record some data first.")
            return

        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV File", "*.csv"),
                ("JSON File", "*.json"),
                ("HTML Report", "*.html"),
                ("Excel File", "*.xlsx"),
            ],
            title="Export Performance Data"
        )
        if path:
            # Phase 2: 实际调用 DataExporter
            messagebox.showinfo("Export", f"Data exported to:\n{path}")

    def _on_settings(self):
        """打开设置"""
        messagebox.showinfo("Settings", "Settings dialog (coming in Phase 2)")

    # ── 主更新循环 ───────────────────────────────

    def _update_loop(self):
        """主更新循环 (50ms 间隔)"""
        # 处理数据队列 (Phase 2: 从采集线程接收数据)
        try:
            while True:
                snapshot = self._data_queue.get_nowait()
                self._update_ui(snapshot)
        except queue.Empty:
            pass

        # 录制中生成模拟数据 (Phase 1)
        if self._is_recording:
            self._generate_mock_data()

            # 更新计时
            elapsed = time.time() - self._start_time
            self._status_bar.update_elapsed(elapsed)

        # 调度下一次更新
        self.root.after(200, self._update_loop)

    def _generate_mock_data(self):
        """生成模拟数据 (Phase 1 临时)"""
        fps = random.uniform(55, 62)
        cpu = random.uniform(15, 55)
        memory = random.uniform(200, 800)
        gpu = random.uniform(20, 60)
        network = random.uniform(100, 2000)
        temp = random.uniform(38, 55)
        power = random.uniform(2.0, 6.0)

        now = time.time()
        self._sample_count += 1

        # 更新指标卡片
        self._cards["fps"].update(fps, avg=58.5, max_v=62.0)
        self._cards["cpu"].update(cpu, avg=32.0, max_v=55.0)
        self._cards["memory"].update(memory, avg=450.0, max_v=800.0)
        self._cards["gpu"].update(gpu, avg=35.0, max_v=60.0)
        self._cards["network"].update(network, avg=800.0, max_v=2000.0)
        self._cards["temp"].update(temp, avg=42.0, max_v=55.0)
        self._cards["power"].update(power, avg=3.5, max_v=6.0)

        # 更新图表
        if "fps" in self._charts:
            self._charts["fps"].add_point(now, fps)
        if "cpu" in self._charts:
            self._charts["cpu"].add_point(now, cpu)
        if "memory" in self._charts:
            self._charts["memory"].add_point(now, memory)
        if "gpu" in self._charts:
            self._charts["gpu"].add_point(now, gpu)
        if "network" in self._charts:
            self._charts["network"].add_point(now, network)
        if "temperature" in self._charts:
            self._charts["temperature"].add_point(now, temp)

        # 更新样本数
        self._status_bar.update_samples(self._sample_count)

    def _update_ui(self, snapshot):
        """
        从真实 MetricsSnapshot 更新 UI (Phase 2)

        Args:
            snapshot: MetricsSnapshot 对象
        """
        # Phase 2 实现
        pass

    # ── 窗口控制 ─────────────────────────────────

    def run(self):
        """启动主窗口"""
        self.root.mainloop()


def run_gui():
    """启动 PerfSun GUI 应用"""
    app = PerfSunApp()
    app.run()
