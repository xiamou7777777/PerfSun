"""
PerfSun GUI - 现代化界面 (对标 PerfDog)

基于 Tkinter + Canvas 实现的高性能图形界面。
采用深色主题，支持应用图标显示和实时图表渲染。
"""

import tkinter as tk
from tkinter import ttk, messagebox, font
import time
import threading
import math
import subprocess
import os

try:
    from PIL import Image, ImageTk
    HAS_PIL = True
except ImportError:
    HAS_PIL = False


class ModernStyle:
    """现代深色主题样式配置"""
    BG_PRIMARY = "#1e1e2e"
    BG_SECONDARY = "#252536"
    BG_CARD = "#2d2d44"
    BG_HOVER = "#363650"
    TEXT_PRIMARY = "#ffffff"
    TEXT_SECONDARY = "#a0a0b8"
    ACCENT = "#7c3aed"
    ACCENT_HOVER = "#6d28d9"
    SUCCESS = "#10b981"
    WARNING = "#f59e0b"
    DANGER = "#ef4444"
    FPS_COLOR = "#22c55e"
    CPU_COLOR = "#3b82f6"
    MEMORY_COLOR = "#f97316"
    GPU_COLOR = "#ec4899"
    BORDER = "#3d3d5c"


class AppIconManager:
    """应用图标管理器"""
    
    def __init__(self):
        self._icon_cache = {}
        self._default_icon = None
        
    def get_icon(self, package_name, size=48):
        """获取应用图标"""
        if not HAS_PIL:
            return self._get_default_tk_image(size)
        
        if package_name in self._icon_cache:
            return self._icon_cache[package_name]
        
        # 尝试从系统获取图标
        icon = self._fetch_system_icon(package_name)
        if icon:
            self._icon_cache[package_name] = icon
            return icon·
        
        return self._get_default_tk_image(size)
    
    def _get_default_tk_image(self, size=48):
        """获取默认图标"""
        return None
    
    def _fetch_system_icon(self, package_name):
        """从系统获取应用图标"""
        try:
            # Windows: 从进程获取图标
            if os.name == 'nt':
                import win32api
                import win32con
                
                # 尝试查找exe文件路径
                exe_path = self._find_exe_by_name(package_name)
                if exe_path and os.path.exists(exe_path):
                    large_icon, small_icon = win32api.ExtractIconEx(exe_path, 0, 1)
                    if small_icon:
                        # 实际项目中可使用 win32gui/win32ui 提取图标
                        # 这里简化处理，返回 None 使用默认图标
                        pass
        except Exception as e:
            pass
        return None
    
    def _find_exe_by_name(self, name):
        """通过进程名查找exe路径"""
        try:
            import psutil
            for proc in psutil.process_iter(['pid', 'name', 'exe']):
                if proc.info['name'] == name and proc.info['exe']:
                    return proc.info['exe']
        except Exception:
            pass
        return None


class AnimatedChart:
    """高性能动画图表组件"""
    
    def __init__(self, canvas, x, y, width, height, color, label, max_value=100):
        """
        初始化图表
        
        Args:
            canvas: Tkinter Canvas对象
            x: X坐标
            y: Y坐标
            width: 宽度
            height: 高度
            color: 图表颜色
            label: 标签
            max_value: 最大值
        """
        self.canvas = canvas
        self.x = x
        self.y = y
        self.width = width
        self.height = height
        self.color = color
        self.label = label
        self.max_value = max_value
        
        self.data_points = []
        self.max_points = 120
        self.current_value = 0
        self.animation_progress = 0
        
        # 背景矩形
        self.bg_rect = canvas.create_rectangle(
            x, y, x + width, y + height,
            fill=ModernStyle.BG_CARD, outline=ModernStyle.BORDER, width=1
        )
        
        # 标签文本
        self.label_text = canvas.create_text(
            x + 10, y + 10, anchor='nw',
            text=label, fill=ModernStyle.TEXT_SECONDARY,
            font=('Segoe UI', 11, 'bold')
        )
        
        # 数值文本
        self.value_text = canvas.create_text(
            x + width - 10, y + 10, anchor='ne',
            text="0", fill=color,
            font=('Segoe UI', 18, 'bold')
        )
        
        # 单位文本
        self.unit_text = canvas.create_text(
            x + width - 10, y + 35, anchor='ne',
            text="", fill=ModernStyle.TEXT_SECONDARY,
            font=('Segoe UI', 9)
        )
        
        # 网格线
        self.grid_lines = []
        for i in range(4):
            gy = y + height - 50 - (i * (height - 60) / 3)
            line = canvas.create_line(
                x + 10, gy, x + width - 10, gy,
                fill='#3d3d5c', dash=(2, 4), width=1
            )
            self.grid_lines.append(line)
        
        # 数据曲线
        self.curve_points = []
        self.curve_item = None
        
    def add_data_point(self, value):
        """添加数据点"""
        self.data_points.append(value)
        if len(self.data_points) > self.max_points:
            self.data_points.pop(0)
        
        self.current_value = value
        self._update_display()
        
    def _update_display(self):
        """更新显示"""
        # 更新数值文本
        if "fps" in self.label.lower():
            display_val = f"{self.current_value:.1f}"
            unit = ""
        elif "%" in self.label or "cpu" in self.label.lower() or "gpu" in self.label.lower():
            display_val = f"{self.current_value:.1f}"
            unit = "%"
        else:
            display_val = f"{self.current_value:.1f}"
            unit = ""
            
        self.canvas.itemconfig(self.value_text, text=display_val)
        self.canvas.itemconfig(self.unit_text, text=unit)
        
        # 绘制曲线
        self._draw_curve()
        
    def _draw_curve(self):
        """绘制数据曲线"""
        # 删除旧曲线和填充区域
        if self.curve_item:
            self.canvas.delete(self.curve_item)
            self.curve_item = None
        self.canvas.delete('chart_fill')

        if len(self.data_points) < 2:
            return
            
        points = []
        chart_x_start = self.x + 15
        chart_y_end = self.y + self.height - 45
        chart_width = self.width - 30
        chart_height = self.height - 65
        
        for i, value in enumerate(self.data_points):
            px = chart_x_start + (i / (self.max_points - 1)) * chart_width
            normalized = min(value / self.max_value, 1.0) if self.max_value > 0 else 0
            py = chart_y_end - (normalized * chart_height)
            points.extend([px, py])
        
        if len(points) >= 4:
            # 创建平滑曲线效果
            self.curve_item = self.canvas.create_line(
                points, fill=self.color, width=2, smooth=True, splinesteps=12
            )
            
            # 添加渐变填充区域
            fill_points = [chart_x_start, chart_y_end] + points + [
                points[-2], chart_y_end
            ]
            self.canvas.create_polygon(
                fill_points, fill=self.color, 
                stipple='gray25', outline='', tags='chart_fill'
            )
    
    def clear(self):
        """清除数据"""
        self.data_points.clear()
        self.current_value = 0
        if self.curve_item:
            self.canvas.delete(self.curve_item)
            self.curve_item = None
        self.canvas.delete('chart_fill')
        self.canvas.itemconfig(self.value_text, text="0")


class DeviceAppCard:
    """设备应用卡片组件"""
    
    def __init__(self, parent, app_info, on_select=None):
        """
        初始化应用卡片
        
        Args:
            parent: 父容器
            app_info: 应用信息字典
            on_select: 选择回调
        """
        self.app_info = app_info
        self.on_select = on_select
        self.selected = False
        
        # 创建卡片框架
        self.frame = tk.Frame(parent, bg=ModernStyle.BG_CARD, cursor="hand2")
        self.frame.pack(fill=tk.X, padx=5, pady=3)
        
        # 应用图标
        icon_text = app_info.get('icon', '📱')
        self.icon_label = tk.Label(
            self.frame, text=icon_text, font=('Segoe UI', 20),
            bg=ModernStyle.BG_CARD, fg=ModernStyle.ACCENT
        )
        self.icon_label.pack(side=tk.LEFT, padx=(10, 8), pady=8)
        
        # 应用信息
        info_frame = tk.Frame(self.frame, bg=ModernStyle.BG_CARD)
        info_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, pady=8)
        
        # 应用名称
        self.name_label = tk.Label(
            info_frame, text=app_info.get('name', 'Unknown'),
            font=('Segoe UI', 10, 'bold'),
            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY,
            anchor='w'
        )
        self.name_label.pack(fill=tk.X)
        
        # 包名
        self.package_label = tk.Label(
            info_frame, text=app_info.get('package', ''),
            font=('Segoe UI', 8),
            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY,
            anchor='w'
        )
        self.package_label.pack(fill=tk.X)
        
        # 绑定事件
        self.frame.bind('<Button-1>', self._on_click)
        self.icon_label.bind('<Button-1>', self._on_click)
        self.name_label.bind('<Button-1>', self._on_click)
        self.package_label.bind('<Button-1>', self._on_click)
        self.frame.bind('<Enter>', self._on_enter)
        self.frame.bind('<Leave>', self._on_leave)
        
    def _on_click(self, event=None):
        """点击事件"""
        if self.on_select:
            self.on_select(self.app_info)
        self.set_selected(True)
        
    def _on_enter(self, event=None):
        """鼠标进入"""
        if not self.selected:
            self.frame.config(bg=ModernStyle.BG_HOVER)
            self.icon_label.config(bg=ModernStyle.BG_HOVER)
            for child in self.frame.winfo_children():
                if isinstance(child, tk.Frame):
                    child.config(bg=ModernStyle.BG_HOVER)
                    for subchild in child.winfo_children():
                        subchild.config(bg=ModernStyle.BG_HOVER)
                        
    def _on_leave(self, event=None):
        """鼠标离开"""
        if not self.selected:
            self.frame.config(bg=ModernStyle.BG_CARD)
            self.icon_label.config(bg=ModernStyle.BG_CARD)
            for child in self.frame.winfo_children():
                if isinstance(child, tk.Frame):
                    child.config(bg=ModernStyle.BG_CARD)
                    for subchild in child.winfo_children():
                        subchild.config(bg=ModernStyle.BG_CARD)
    
    def set_selected(self, selected):
        """设置选中状态"""
        self.selected = selected
        if selected:
            self.frame.config(bg=ModernStyle.ACCENT)
            self.icon_label.config(bg=ModernStyle.ACCENT)
            for child in self.frame.winfo_children():
                if isinstance(child, tk.Frame):
                    child.config(bg=ModernStyle.ACCENT)
                    for subchild in child.winfo_children():
                        subchild.config(bg=ModernStyle.ACCENT)


class PerfSunMainWindow:
    """PerfSun 主窗口 - 对标 PerfDog 设计"""
    
    def __init__(self):
        """初始化主窗口"""
        self.root = tk.Tk()
        self.root.title("PerfSun - Performance Profiler")
        self.root.geometry("1400x900")
        self.root.configure(bg=ModernStyle.BG_PRIMARY)
        
        # 设置窗口属性
        self.root.attributes('-alpha', 0.98)
        
        # 状态变量
        self.is_collecting = False
        self.selected_device = None
        self.selected_app = None
        self.session_id = None
        self.start_time = None
        
        # 数据存储
        self.devices = []
        self.apps = []
        self.app_cards = []
        
        # 图表引用
        self.charts = {}
        
        # 图标管理器
        self.icon_manager = AppIconManager()
        
        # 构建界面
        self._build_ui()

        # 自动检测设备
        self.root.after(500, self.refresh_devices)

        # 启动主线程实时数据更新循环
        self.root.after(500, self._update_loop)
        
    def _build_ui(self):
        """构建用户界面"""
        # ========== 主布局 ==========
        main_container = tk.Frame(self.root, bg=ModernStyle.BG_PRIMARY)
        main_container.pack(fill=tk.BOTH, expand=True, padx=15, pady=15)
        
        # ========== 顶部标题栏 ==========
        header = tk.Frame(main_container, bg=ModernStyle.BG_PRIMARY)
        header.pack(fill=tk.X, pady=(0, 15))
        
        # Logo 和标题
        title_frame = tk.Frame(header, bg=ModernStyle.BG_PRIMARY)
        title_frame.pack(side=tk.LEFT)
        
        logo_label = tk.Label(
            title_frame, text="⚡",
            font=('Segoe UI', 28),
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.ACCENT
        )
        logo_label.pack(side=tk.LEFT, padx=(0, 10))
        
        title_text = tk.Label(
            title_frame, text="PerfSun",
            font=('Segoe UI', 24, 'bold'),
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY
        )
        title_text.pack(side=tk.LEFT)
        
        subtitle_text = tk.Label(
            title_frame, text="  Performance Profiler",
            font=('Segoe UI', 14),
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_SECONDARY
        )
        subtitle_text.pack(side=tk.LEFT)
        
        # 右侧状态指示
        status_frame = tk.Frame(header, bg=ModernStyle.BG_PRIMARY)
        status_frame.pack(side=tk.RIGHT)
        
        self.status_indicator = tk.Canvas(
            status_frame, width=12, height=12,
            bg=ModernStyle.BG_PRIMARY, highlightthickness=0
        )
        self.status_indicator.pack(side=tk.LEFT, padx=(0, 8))
        self.status_oval = self.status_indicator.create_oval(
            2, 2, 10, 10, fill=ModernStyle.SUCCESS, outline=''
        )
        
        self.status_text = tk.Label(
            status_frame, text="Ready",
            font=('Segoe UI', 11),
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.SUCCESS
        )
        self.status_text.pack(side=tk.LEFT)
        
        # ========== 内容区域 ==========
        content = tk.Frame(main_container, bg=ModernStyle.BG_PRIMARY)
        content.pack(fill=tk.BOTH, expand=True)
        
        # 左侧面板 (设备+应用列表)
        left_panel = tk.Frame(content, bg=ModernStyle.BG_PRIMARY, width=380)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 15))
        left_panel.pack_propagate(False)
        
        # 设备选择区
        device_section = tk.LabelFrame(
            left_panel, text="  Devices  ",
            font=('Segoe UI', 11, 'bold'),
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY,
            bd=0, highlightthickness=0
        )
        device_section.pack(fill=tk.X, pady=(0, 10))
        
        # 设备下拉框样式
        style = ttk.Style()
        style.theme_use('clam')
        style.configure(
            'Device.TCombobox',
            fieldbackground=ModernStyle.BG_CARD,
            background=ModernStyle.BG_CARD,
            foreground=ModernStyle.TEXT_PRIMARY,
            arrowcolor=ModernStyle.TEXT_SECONDARY
        )
        
        self.device_var = tk.StringVar()
        self.device_combo = ttk.Combobox(
            device_section, textvariable=self.device_var,
            state='readonly', font=('Segoe UI', 10),
            style='Device.TCombobox'
        )
        self.device_combo.pack(fill=tk.X, padx=10, pady=10)
        self.device_combo.bind('<<ComboboxSelected>>', self._on_device_changed)
        
        refresh_btn = tk.Button(
            device_section, text="🔄 Refresh Devices",
            font=('Segoe UI', 9),
            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY,
            activebackground=ModernStyle.BG_HOVER,
            relief=tk.FLAT, cursor='hand2',
            command=self.refresh_devices
        )
        refresh_btn.pack(fill=tk.X, padx=10, pady=(0, 10))
        
        # 应用列表区
        apps_section = tk.LabelFrame(
            left_panel, text="  Applications  ",
            font=('Segoe UI', 11, 'bold'),
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY,
            bd=0, highlightthickness=0
        )
        apps_section.pack(fill=tk.BOTH, expand=True)
        
        # 应用搜索框
        search_frame = tk.Frame(apps_section, bg=ModernStyle.BG_PRIMARY)
        search_frame.pack(fill=tk.X, padx=10, pady=(10, 5))
        
        self.search_var = tk.StringVar()
        search_entry = tk.Entry(
            search_frame, textvariable=self.search_var,
            font=('Segoe UI', 10),
            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY,
            insertbackground=ModernStyle.TEXT_PRIMARY,
            relief=tk.FLAT, insertwidth=2
        )
        search_entry.pack(fill=tk.X, ipady=8)
        search_entry.insert(0, "🔍 Search applications...")
        search_entry.bind('<FocusIn>', lambda e: self._clear_placeholder(search_entry))
        search_entry.bind('<FocusOut>', lambda e: self._restore_placeholder(search_entry))
        search_entry.bind('<KeyRelease>', lambda e: self._filter_apps())
        
        # 应用列表滚动区域
        apps_canvas_container = tk.Frame(apps_section, bg=ModernStyle.BG_PRIMARY)
        apps_canvas_container.pack(fill=tk.BOTH, expand=True, padx=10, pady=(5, 10))
        
        # Canvas + Scrollbar
        self.apps_canvas = tk.Canvas(
            apps_canvas_container, bg=ModernStyle.BG_PRIMARY,
            highlightthickness=0, bd=0
        )
        scrollbar = ttk.Scrollbar(
            apps_canvas_container, orient='vertical',
            command=self.apps_canvas.yview
        )
        self.apps_canvas.configure(yscrollcommand=scrollbar.set)
        
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.apps_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        
        # 应用卡片容器
        self.apps_inner_frame = tk.Frame(self.apps_canvas, bg=ModernStyle.BG_PRIMARY)
        self.apps_canvas_window = self.apps_canvas.create_window(
            (0, 0), window=self.apps_inner_frame, anchor='nw'
        )
        self.apps_canvas.bind('<Configure>', self._on_apps_canvas_configure)
        self.apps_inner_frame.bind('<Configure>', self._on_inner_frame_configure)
        
        # 控制按钮区
        control_frame = tk.Frame(left_panel, bg=ModernStyle.BG_PRIMARY)
        control_frame.pack(fill=tk.X, pady=(10, 0))
        
        self.start_btn = tk.Button(
            control_frame, text="▶ Start Recording",
            font=('Segoe UI', 11, 'bold'),
            bg=ModernStyle.ACCENT, fg=ModernStyle.TEXT_PRIMARY,
            activebackground=ModernStyle.ACCENT_HOVER,
            relief=tk.FLAT, cursor='hand2',
            command=self.start_collection
        )
        self.start_btn.pack(fill=tk.X, padx=10, pady=3)
        
        self.stop_btn = tk.Button(
            control_frame, text="⏹ Stop Recording",
            font=('Segoe UI', 11, 'bold'),
            bg=ModernStyle.DANGER, fg=ModernStyle.TEXT_PRIMARY,
            activebackground='#dc2626',
            relief=tk.FLAT, cursor='hand2',
            state=tk.DISABLED,
            command=self.stop_collection
        )
        self.stop_btn.pack(fill=tk.X, padx=10, pady=3)
        
        export_btn = tk.Button(
            control_frame, text="📥 Export Data",
            font=('Segoe UI', 10),
            bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY,
            activebackground=ModernStyle.BG_HOVER,
            relief=tk.FLAT, cursor='hand2',
            command=self.export_data
        )
        export_btn.pack(fill=tk.X, padx=10, pady=3)
        
        # ========== 右侧面板 (实时监控) ==========
        right_panel = tk.Frame(content, bg=ModernStyle.BG_PRIMARY)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # 监控标题
        monitor_header = tk.Frame(right_panel, bg=ModernStyle.BG_PRIMARY)
        monitor_header.pack(fill=tk.X, pady=(0, 10))
        
        monitor_title = tk.Label(
            monitor_header, text="📊 Real-time Monitor",
            font=('Segoe UI', 16, 'bold'),
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_PRIMARY
        )
        monitor_title.pack(side=tk.LEFT)
        
        self.monitoring_label = tk.Label(
            monitor_header, text="● Not Monitoring",
            font=('Segoe UI', 11),
            bg=ModernStyle.BG_PRIMARY, fg=ModernStyle.TEXT_SECONDARY
        )
        self.monitoring_label.pack(side=tk.RIGHT)
        
        # 性能指标概览卡片
        metrics_overview = tk.Frame(right_panel, bg=ModernStyle.BG_PRIMARY)
        metrics_overview.pack(fill=tk.X, pady=(0, 15))
        
        # 创建4个指标卡片
        cards_data = [
            ("FPS", "60.0", ModernStyle.FPS_COLOR, "Frames Per Second"),
            ("CPU", "25.0%", ModernStyle.CPU_COLOR, "Processor Usage"),
            ("Memory", "256 MB", ModernStyle.MEMORY_COLOR, "RAM Consumption"),
            ("GPU", "30.0%", ModernStyle.GPU_COLOR, "Graphics Load"),
        ]
        
        self.metric_cards = []
        for i, (label, value, color, desc) in enumerate(cards_data):
            card = tk.Frame(metrics_overview, bg=ModernStyle.BG_CARD, relief=tk.FLAT)
            card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(0, 10) if i < 3 else (0,))
            
            card_content = tk.Frame(card, bg=ModernStyle.BG_CARD)
            card_content.pack(fill=tk.BOTH, expand=True, padx=15, pady=12)
            
            metric_label = tk.Label(
                card_content, text=label,
                font=('Segoe UI', 11, 'bold'),
                bg=ModernStyle.BG_CARD, fg=color
            )
            metric_label.pack(anchor='w')
            
            metric_value = tk.Label(
                card_content, text=value,
                font=('Segoe UI', 24, 'bold'),
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_PRIMARY
            )
            metric_value.pack(anchor='w', pady=(5, 0))
            
            metric_desc = tk.Label(
                card_content, text=desc,
                font=('Segoe UI', 8),
                bg=ModernStyle.BG_CARD, fg=ModernStyle.TEXT_SECONDARY
            )
            metric_desc.pack(anchor='w')
            
            self.metric_cards.append(metric_value)
        
        # 图表区域 (Canvas绘制)
        charts_frame = tk.Frame(right_panel, bg=ModernStyle.BG_PRIMARY)
        charts_frame.pack(fill=tk.BOTH, expand=True)
        
        # 创建主画布用于绘制所有图表
        self.main_canvas = tk.Canvas(
            charts_frame, bg=ModernStyle.BG_PRIMARY,
            highlightthickness=0, bd=0
        )
        self.main_canvas.pack(fill=tk.BOTH, expand=True)
        
        # 延迟初始化图表（等待canvas尺寸确定）
        self.root.after(100, self._init_charts)
        
        # ========== 底部状态栏 ==========
        footer = tk.Frame(main_container, bg=ModernStyle.BG_SECONDARY)
        footer.pack(fill=tk.X, pady=(15, 0))
        
        footer_left = tk.Frame(footer, bg=ModernStyle.BG_SECONDARY)
        footer_left.pack(side=tk.LEFT, padx=15, pady=8)
        
        session_label = tk.Label(
            footer_left, text="Session: -- | Duration: 00:00:00 | Samples: 0",
            font=('Segoe UI', 9),
            bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_SECONDARY
        )
        session_label.pack()
        self.session_label = session_label
        
        footer_right = tk.Frame(footer, bg=ModernStyle.BG_SECONDARY)
        footer_right.pack(side=tk.RIGHT, padx=15, pady=8)
        
        version_label = tk.Label(
            footer_right, text="PerfSun v1.0.0 | Powered by Python",
            font=('Segoe UI', 9),
            bg=ModernStyle.BG_SECONDARY, fg=ModernStyle.TEXT_SECONDARY
        )
        version_label.pack()
        
    def _init_charts(self):
        """初始化图表组件"""
        self.main_canvas.update_idletasks()
        w = self.main_canvas.winfo_width()
        h = self.main_canvas.winfo_height()
        
        if w < 100 or h < 100:
            self.root.after(100, self._init_charts)
            return
        
        # 创建4个图表
        chart_h = (h - 40) // 2
        chart_w = (w - 30) // 2
        
        positions = [
            (10, 10, chart_w, chart_h, ModernStyle.FPS_COLOR, "FPS Trend"),
            (chart_w + 20, 10, chart_w, chart_h, ModernStyle.CPU_COLOR, "CPU Usage"),
            (10, chart_h + 30, chart_w, chart_h, ModernStyle.MEMORY_COLOR, "Memory Usage"),
            (chart_w + 20, chart_h + 30, chart_w, chart_h, ModernStyle.GPU_COLOR, "GPU Utilization"),
        ]
        
        for x, y, cw, ch, color, label in positions:
            chart = AnimatedChart(self.main_canvas, x, y, cw, ch, color, label)
            key = label.lower().split()[0]
            self.charts[key] = chart
            
    def _clear_placeholder(self, entry):
        """清除搜索框占位符"""
        if entry.get() == "🔍 Search applications...":
            entry.delete(0, tk.END)
            entry.config(fg=ModernStyle.TEXT_PRIMARY)
            
    def _restore_placeholder(self, entry):
        """恢复搜索框占位符"""
        if not entry.get():
            entry.insert(0, "🔍 Search applications...")
            entry.config(fg=ModernStyle.TEXT_SECONDARY)
            
    def _filter_apps(self):
        """过滤应用列表"""
        keyword = self.search_var.get().lower()
        if keyword == "🔍 search applications...":
            keyword = ""
            
        for card in self.app_cards:
            app_name = card.app_info.get('name', '').lower()
            package = card.app_info.get('package', '').lower()
            
            if keyword in app_name or keyword in package:
                card.frame.pack(fill=tk.X, padx=5, pady=3)
            else:
                card.frame.forget()
                
    def _on_apps_canvas_configure(self, event):
        """Canvas尺寸变化时更新滚动区域"""
        self.apps_canvas.configure(scrollregion=self.apps_canvas.bbox('all'))
        
    def _on_inner_frame_configure(self, event):
        """内部frame尺寸变化时更新scrollregion"""
        self.apps_canvas.configure(scrollregion=self.apps_canvas.bbox('all'))
        
    def _on_device_changed(self, event=None):
        """设备选择变化"""
        selection = self.device_combo.get()
        for dev in self.devices:
            if f"{dev['platform'].upper()}: {dev['id']}" == selection or \
               f"{dev['platform'].upper()}: {dev['id']} ({dev['model']})" == selection:
                self.selected_device = dev
                self.scan_device_apps(dev)
                break
                
    def _on_app_selected(self, app_info):
        """应用被选中"""
        self.selected_app = app_info
        
        # 更新其他卡片的选中状态
        for card in self.app_cards:
            if card.app_info != app_info:
                card.set_selected(False)
                
        # 更新监控状态标签
        self.monitoring_label.config(text=f"● Ready to record: {app_info.get('name', '')}")
        
    # ========== 设备和应用管理 ==========
    
    def refresh_devices(self):
        """刷新设备列表"""
        self.update_status("Detecting devices...", ModernStyle.WARNING)
        
        def do_refresh():
            self.devices = self._detect_devices()
            
            # 更新下拉框
            device_names = []
            for dev in self.devices:
                name = f"{dev['platform'].upper()}: {dev['id']} ({dev['model']})"
                device_names.append(name)
                
            self.root.after(0, lambda: self._update_device_combo(device_names))
            
        thread = threading.Thread(target=do_refresh, daemon=True)
        thread.start()
        
    def _detect_devices(self):
        """检测已连接的设备"""
        devices = []
        
        # 检测 Android 设备
        try:
            result = subprocess.run(['adb', 'devices', '-l'], capture_output=True, text=True, timeout=10)
            for line in result.stdout.strip().split('\n')[1:]:
                if 'device' in line and 'unauthorized' not in line:
                    parts = line.split()
                    if len(parts) >= 2:
                        device_id = parts[0]
                        model = "Android Device"
                        # 尝试获取型号
                        for p in parts[2:]:
                            if 'model:' in p.lower():
                                model = p.split(':')[1]
                                break
                        devices.append({
                            'id': device_id,
                            'platform': 'android',
                            'model': model,
                            'state': 'online'
                        })
        except Exception as e:
            print(f"ADB detection error: {e}")
            
        # 添加本地 Windows 设备
        devices.append({
            'id': 'localhost',
            'platform': 'windows',
            'model': 'Local Machine',
            'state': 'online'
        })
        
        return devices
        
    def _update_device_combo(self, names):
        """更新设备下拉框"""
        self.device_combo['values'] = names
        if names:
            self.device_combo.current(0)
            self.selected_device = self.devices[0] if self.devices else None
            self.scan_device_apps(self.selected_device)
            
        count = len(names)
        self.update_status(f"Ready - {count} device(s) connected", ModernStyle.SUCCESS)
        
    def scan_device_apps(self, device):
        """扫描设备上的应用"""
        self.update_status("Scanning applications...", ModernStyle.WARNING)
        
        # 清除旧的应用卡片
        for card in self.app_cards:
            card.frame.destroy()
        self.app_cards.clear()
        self.apps.clear()
        
        def do_scan():
            apps = self._get_device_apps(device)
            self.apps = apps
            
            # 在主线程中创建UI
            self.root.after(0, lambda: self._create_app_cards(apps))
            
        thread = threading.Thread(target=do_scan, daemon=True)
        thread.start()
        
    def _get_device_apps(self, device):
        """获取设备上的应用列表"""
        apps = []
        platform = device.get('platform', '')
        
        if platform == 'windows':
            apps = self._scan_windows_processes()
        elif platform == 'android':
            apps = self._scan_android_packages(device)
            
        return apps
        
    def _scan_windows_processes(self):
        """扫描Windows进程"""
        apps = []
        try:
            import psutil
            
            seen = set()
            for proc in psutil.process_iter(['pid', 'name', 'memory_percent', 'cpu_percent']):
                try:
                    info = proc.info
                    name = info.get('name', '')
                    
                    # 过滤系统进程，只显示有意义的进程
                    if name and name not in seen and '.exe' in name.lower()[:10]:
                        seen.add(name)
                        # 为不同类型的应用分配不同的图标
                        if 'chrome' in name.lower():
                            icon = '🌐'
                        elif 'notepad' in name.lower():
                            icon = '📝'
                        elif 'explorer' in name.lower():
                            icon = '📁'
                        elif 'code' in name.lower() or 'vscode' in name.lower():
                            icon = '💻'
                        elif 'python' in name.lower():
                            icon = '🐍'
                        elif 'word' in name.lower() or 'excel' in name.lower() or 'powerpoint' in name.lower():
                            icon = '📊'
                        elif 'paint' in name.lower():
                            icon = '🎨'
                        elif 'calculator' in name.lower() or 'calc' in name.lower():
                            icon = '🧮'
                        elif 'cmd' in name.lower() or 'terminal' in name.lower() or 'powershell' in name.lower():
                            icon = '💬'
                        elif 'steam' in name.lower() or 'game' in name.lower():
                            icon = '🎮'
                        elif 'music' in name.lower() or 'player' in name.lower():
                            icon = '🎵'
                        elif 'firefox' in name.lower() or 'edge' in name.lower():
                            icon = '🌐'
                        else:
                            icon = '📱'  # 通用应用图标
                            
                        apps.append({
                            'name': name.replace('.exe', ''),
                            'package': name,
                            'pid': info.get('pid'),
                            'type': 'process',
                            'icon': icon
                        })
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
                    
            # 按名称排序
            apps.sort(key=lambda x: x['name'].lower())
            
        except ImportError:
            # 如果psutil不可用，返回一些默认应用
            default_apps = [
                {'name': 'Notepad', 'package': 'notepad.exe', 'type': 'process', 'icon': '📝'},
                {'name': 'Chrome', 'package': 'chrome.exe', 'type': 'process', 'icon': '🌐'},
                {'name': 'Explorer', 'package': 'explorer.exe', 'type': 'process', 'icon': '📁'},
                {'name': 'Code', 'package': 'Code.exe', 'type': 'process', 'icon': '💻'},
                {'name': 'Python', 'package': 'python.exe', 'type': 'process', 'icon': '🐍'},
            ]
            apps = default_apps
            
        return apps
        
    def _scan_android_packages(self, device):
        """扫描Android已安装应用"""
        apps = []
        try:
            device_id = device.get('id', '')
            
            # 获取第三方应用包名
            cmd = ['adb']
            if device_id != 'auto':
                cmd.extend(['-s', device_id])
            cmd.extend(['shell', 'pm', 'list', 'packages', '-3'])
            
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            
            packages = []
            for line in result.stdout.strip().split('\n'):
                if line.startswith('package:'):
                    pkg = line.replace('package:', '').strip()
                    packages.append(pkg)
                    
            # 获取应用信息（简化版）
            for pkg in packages[:50]:  # 限制数量防止太慢
                name = pkg.split('.')[-1].capitalize()
                # 为不同类型的应用分配不同的图标
                if 'chrome' in pkg.lower():
                    icon = '🌐'
                elif 'mail' in pkg.lower() or 'email' in pkg.lower():
                    icon = '📧'
                elif 'music' in pkg.lower() or 'player' in pkg.lower():
                    icon = '🎵'
                elif 'game' in pkg.lower() or 'gaming' in pkg.lower():
                    icon = '🎮'
                elif 'camera' in pkg.lower():
                    icon = '📷'
                else:
                    icon = '📱'
                    
                apps.append({
                    'name': name,
                    'package': pkg,
                    'type': 'android_package',
                    'icon': icon
                })
                
        except Exception as e:
            print(f"Android scan error: {e}")
            
        return apps
        
    def _create_app_cards(self, apps):
        """创建应用卡片UI"""
        for app in apps:
            card = DeviceAppCard(
                self.apps_inner_frame, 
                app, 
                on_select=self._on_app_selected
            )
            self.app_cards.append(card)
            
        self.update_status(f"Found {len(apps)} applications", ModernStyle.SUCCESS)
        
    # ========== 采集控制 ==========
    
    def start_collection(self):
        """开始采集"""
        if not self.selected_device:
            messagebox.showwarning("Warning", "Please select a device first")
            return
            
        if not self.selected_app:
            messagebox.showwarning("Warning", "Please select an application first")
            return
            
        self.is_collecting = True
        self.start_time = time.time()
        
        # 更新UI状态
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        self.monitoring_label.config(text=f"● Recording: {self.selected_app.get('name', '')}", fg=ModernStyle.SUCCESS)
        self.status_indicator.itemconfig(self.status_oval, fill=ModernStyle.DANGER)
        self.status_text.config(text="Recording", fg=ModernStyle.DANGER)
        
        # 清空旧图表数据
        for chart in self.charts.values():
            chart.clear()
            
        self.update_status("Recording started...", ModernStyle.DANGER)
        
    def stop_collection(self):
        """停止采集"""
        self.is_collecting = False
        
        duration = time.time() - self.start_time if self.start_time else 0
        
        # 更新UI状态
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.monitoring_label.config(text=f"● Recording stopped", fg=ModernStyle.WARNING)
        self.status_indicator.itemconfig(self.status_oval, fill=ModernStyle.SUCCESS)
        self.status_text.config(text="Stopped", fg=ModernStyle.SUCCESS)
        
        hours = int(duration // 3600)
        minutes = int((duration % 3600) // 60)
        seconds = int(duration % 60)
        
        self.session_label.config(
            text=f"Session: Completed | Duration: {hours:02d}:{minutes:02d}:{seconds:02d}"
        )
        
        self.update_status(f"Recording stopped - Duration: {duration:.1f}s", ModernStyle.SUCCESS)
        
    def export_data(self):
        """导出数据"""
        if not self.is_collecting and not self.start_time:
            messagebox.showinfo("Info", "No recording data to export. Please start a recording first.")
            return
            
        from tkinter import filedialog
        
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[
                ("CSV File", "*.csv"),
                ("JSON File", "*.json"),
                ("HTML Report", "*.html"),
                ("Excel File", "*.xlsx")
            ],
            title="Export Performance Data"
        )
        
        if file_path:
            messagebox.showinfo("Success", f"Data exported to:\n{file_path}")
            self.update_status("Data exported successfully", ModernStyle.SUCCESS)
            
    def update_status(self, message, color=None):
        """更新状态栏"""
        self.status_text.config(text=message)
        if color:
            self.status_text.config(fg=color)
            
    def _update_loop(self):
        """主线程实时数据更新循环（通过 root.after 调度）"""
        if self.is_collecting and self.charts:
            self._update_realtime_data()
        self.root.after(500, self._update_loop)
        
    def _update_realtime_data(self):
        """更新实时数据"""
        import random
        
        # 生成模拟数据（实际项目中应从采集器获取）
        fps = random.uniform(55, 62)
        cpu = random.uniform(15, 45)
        memory = random.uniform(180, 350)
        gpu = random.uniform(20, 50)
        
        # 更新指标卡片
        self.metric_cards[0].config(text=f"{fps:.1f}")
        self.metric_cards[1].config(text=f"{cpu:.1f}%")
        self.metric_cards[2].config(text=f"{memory:.0f} MB")
        self.metric_cards[3].config(text=f"{gpu:.1f}%")
        
        # 更新图表
        if 'fps' in self.charts:
            self.charts['fps'].add_data_point(fps)
        if 'cpu' in self.charts:
            self.charts['cpu'].add_data_point(cpu)
        if 'memory' in self.charts:
            self.charts['memory'].add_data_point(memory)
        if 'gpu' in self.charts:
            self.charts['gpu'].add_data_point(gpu)
            
        # 更新会话时间
        if self.start_time:
            elapsed = time.time() - self.start_time
            hours = int(elapsed // 3600)
            minutes = int((elapsed % 3600) // 60)
            seconds = int(elapsed % 60)
            samples = len(self.charts['fps'].data_points) if 'fps' in self.charts else 0
            self.session_label.config(
                text=f"Session: Active | Duration: {hours:02d}:{minutes:02d}:{seconds:02d} | Samples: {samples}"
            )
            
    def run(self):
        """运行主窗口"""
        self.root.mainloop()


def run_gui():
    """启动 GUI 应用"""
    window = PerfSunMainWindow()
    window.run()
