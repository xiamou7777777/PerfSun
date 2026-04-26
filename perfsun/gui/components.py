"""
PerfSun GUI 可复用组件 (对标 PerfDog)

提供专业风格的 UI 组件:
- MetricCard: 紧凑指标卡片 (标签 + 大数字 + 迷你趋势)
- Sidebar: 窄侧边栏控制面板
- StatusBar: 底部状态栏
"""

import tkinter as tk
from tkinter import font as tkfont
from perfsun.gui.theme import AppTheme


class MetricCard(tk.Frame):
    """
    紧凑指标卡片组件

    展示单个性能指标的当前值、标签和迷你趋势。
    PerfDog 风格的紧凑卡片设计。

    ┌───────────────────┐
    │ FPS         58.6  │
    │ avg 60.0    60.0  │
    └───────────────────┘
    """

    def __init__(self, parent, label: str, color: str, unit: str = "",
                 width: int = None, height: int = None):
        """
        初始化指标卡片

        Args:
            parent: 父容器
            label: 指标名称 (如 "FPS")
            color: 指标主题色
            unit: 单位 (如 "%", "MB", "°C")
            width: 卡片宽度
            height: 卡片高度
        """
        w = width or AppTheme.METRIC_CARD_WIDTH
        h = height or AppTheme.METRIC_CARD_HEIGHT

        super().__init__(
            parent, width=w, height=h,
            bg=AppTheme.BG_CARD, highlightthickness=1,
            highlightcolor=AppTheme.BORDER_CARD,
            highlightbackground=AppTheme.BORDER_CARD
        )
        self.pack_propagate(False)

        self.label = label
        self.color = color
        self.unit = unit
        self._value = 0.0
        self._avg = 0.0

        # 构建内部布局
        self._build_card()

    def _build_card(self):
        """构建卡片内部布局"""
        # 顶部: 指标名 (左) + 当前值 (右)
        top_frame = tk.Frame(self, bg=AppTheme.BG_CARD)
        top_frame.pack(fill=tk.X, padx=12, pady=(10, 2))

        self.label_widget = tk.Label(
            top_frame, text=self.label,
            font=AppTheme.FONT_METRIC_LABEL,
            bg=AppTheme.BG_CARD, fg=self.color,
            anchor="w"
        )
        self.label_widget.pack(side=tk.LEFT)

        self.value_widget = tk.Label(
            top_frame, text="--",
            font=AppTheme.FONT_METRIC_VALUE,
            bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_PRIMARY,
            anchor="e"
        )
        self.value_widget.pack(side=tk.RIGHT)

        # 底部: 平均值 (左) + 最大值 (右)
        bottom_frame = tk.Frame(self, bg=AppTheme.BG_CARD)
        bottom_frame.pack(fill=tk.X, padx=12, pady=(2, 10))

        self.avg_widget = tk.Label(
            bottom_frame, text="",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_SECONDARY,
            anchor="w"
        )
        self.avg_widget.pack(side=tk.LEFT)

        self.max_widget = tk.Label(
            bottom_frame, text="",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_CARD, fg=AppTheme.TEXT_SECONDARY,
            anchor="e"
        )
        self.max_widget.pack(side=tk.RIGHT)

    def update(self, value: float, avg: float = 0, max_v: float = 0):
        """
        更新卡片显示值

        Args:
            value: 当前值
            avg: 平均值
            max_v: 最大值
        """
        self._value = value
        self._avg = avg

        # 格式化数值
        val_str = self._format_value(value)
        self.value_widget.config(text=val_str)

        # 更新统计
        if avg > 0:
            self.avg_widget.config(text=f"avg {self._format_value(avg)}")
        if max_v > 0:
            self.max_widget.config(text=f"max {self._format_value(max_v)}")

    def set_alert(self, active: bool):
        """设置告警高亮边框"""
        if active:
            self.config(highlightthickness=2,
                        highlightcolor=AppTheme.DANGER,
                        highlightbackground=AppTheme.DANGER)
        else:
            self.config(highlightthickness=1,
                        highlightcolor=AppTheme.BORDER_CARD,
                        highlightbackground=AppTheme.BORDER_CARD)

    def _format_value(self, value: float) -> str:
        """格式化数值显示"""
        if value >= 1000:
            return f"{value:.0f}{self.unit}" if self.unit else f"{value:.0f}"
        elif value >= 100:
            return f"{value:.0f}{self.unit}" if self.unit else f"{value:.0f}"
        elif value >= 1:
            return f"{value:.1f}{self.unit}" if self.unit else f"{value:.1f}"
        elif value > 0:
            return f"{value:.2f}{self.unit}" if self.unit else f"{value:.2f}"
        else:
            return f"0{self.unit}" if self.unit else "0"


class Sidebar(tk.Frame):
    """
    侧边栏控制面板

    窄侧边栏 (180px)，包含控制按钮。
    对标 PerfDog 右侧工具栏设计。
    """

    def __init__(self, parent, callbacks: dict = None):
        """
        初始化侧边栏

        Args:
            parent: 父容器
            callbacks: 回调字典 {
                "on_start": func,
                "on_stop": func,
                "on_mark": func,
                "on_export": func,
                "on_settings": func,
            }
        """
        super().__init__(
            parent, width=AppTheme.SIDEBAR_WIDTH,
            bg=AppTheme.BG_TOOLBAR
        )
        self.pack_propagate(False)

        self.callbacks = callbacks or {}
        self._is_recording = False

        self._build_sidebar()

    def _build_sidebar(self):
        """构建侧边栏"""
        # ── Logo / 标题 ──
        logo_frame = tk.Frame(self, bg=AppTheme.BG_TOOLBAR)
        logo_frame.pack(fill=tk.X, pady=(20, 25))

        tk.Label(
            logo_frame, text="PerfSun",
            font=AppTheme.FONT_TITLE,
            bg=AppTheme.BG_TOOLBAR, fg=AppTheme.TEXT_PRIMARY
        ).pack()

        tk.Label(
            logo_frame, text="Performance Profiler",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_TOOLBAR, fg=AppTheme.TEXT_SECONDARY
        ).pack()

        # ── 分隔线 ──
        self._add_separator()

        # ── 控制按钮 ──
        btn_frame = tk.Frame(self, bg=AppTheme.BG_TOOLBAR)
        btn_frame.pack(fill=tk.X, padx=12, pady=(5, 10))

        # 开始按钮 (绿色)
        self.start_btn = self._create_button(
            btn_frame, "▶  Start Recording",
            AppTheme.BTN_PRIMARY, AppTheme.BTN_PRIMARY_HOVER,
            self._on_start
        )
        self.start_btn.pack(fill=tk.X, pady=3)

        # 停止按钮 (红色, 初始禁用)
        self.stop_btn = self._create_button(
            btn_frame, "⏹  Stop Recording",
            AppTheme.BTN_RECORD, AppTheme.BTN_RECORD_HOVER,
            self._on_stop,
            disabled=True
        )
        self.stop_btn.pack(fill=tk.X, pady=3)

        # ── 分隔线 ──
        self._add_separator()

        # 标记按钮
        mark_btn = self._create_button(
            btn_frame, "🏷  Add Mark",
            AppTheme.BG_TOOLBAR_SEC, AppTheme.BTN_SECONDARY_HOVER,
            lambda: self._fire_callback("on_mark")
        )
        mark_btn.pack(fill=tk.X, pady=3)

        # 导出按钮
        export_btn = self._create_button(
            btn_frame, "📁  Export Data",
            AppTheme.BG_TOOLBAR_SEC, AppTheme.BTN_SECONDARY_HOVER,
            lambda: self._fire_callback("on_export")
        )
        export_btn.pack(fill=tk.X, pady=3)

        # 设置按钮
        settings_btn = self._create_button(
            btn_frame, "⚙  Settings",
            AppTheme.BG_TOOLBAR_SEC, AppTheme.BTN_SECONDARY_HOVER,
            lambda: self._fire_callback("on_settings")
        )
        settings_btn.pack(fill=tk.X, pady=3)

        # ── 底部状态 (设备指示) ──
        bottom_frame = tk.Frame(self, bg=AppTheme.BG_TOOLBAR)
        bottom_frame.pack(side=tk.BOTTOM, fill=tk.X, padx=12, pady=15)

        self.status_dot = tk.Canvas(
            bottom_frame, width=8, height=8,
            bg=AppTheme.BG_TOOLBAR, highlightthickness=0
        )
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.dot_oval = self.status_dot.create_oval(
            0, 0, 8, 8, fill=AppTheme.TEXT_SECONDARY, outline=""
        )

        self.status_label = tk.Label(
            bottom_frame, text="Ready",
            font=AppTheme.FONT_SMALL,
            bg=AppTheme.BG_TOOLBAR, fg=AppTheme.TEXT_SECONDARY
        )
        self.status_label.pack(side=tk.LEFT)

    def _create_button(self, parent, text, bg, hover_bg, command,
                       disabled=False):
        """创建样式化按钮"""
        btn = tk.Label(
            parent, text=text,
            font=AppTheme.FONT_SIDEBAR_BTN,
            bg=bg, fg=AppTheme.BTN_TEXT,
            relief=tk.FLAT, cursor="hand2" if not disabled else "arrow",
            padx=12, pady=10, anchor="w"
        )
        btn._normal_bg = bg
        btn._hover_bg = hover_bg

        if not disabled:
            btn.bind("<Enter>", lambda e: btn.config(bg=hover_bg))
            btn.bind("<Leave>", lambda e: btn.config(bg=bg))
        btn.bind("<Button-1>", lambda e: command() if command else None)

        return btn

    def _add_separator(self):
        """添加分隔线"""
        sep = tk.Frame(self, height=1, bg=AppTheme.BORDER)
        sep.pack(fill=tk.X, padx=15, pady=5)

    def _on_start(self):
        """开始按钮回调"""
        if not self._is_recording:
            self._fire_callback("on_start")

    def _on_stop(self):
        """停止按钮回调"""
        if self._is_recording:
            self._fire_callback("on_stop")

    def _fire_callback(self, name):
        """触发回调"""
        cb = self.callbacks.get(name)
        if cb:
            cb()

    def set_recording_state(self, is_recording: bool):
        """设置录制状态"""
        self._is_recording = is_recording
        if is_recording:
            self.start_btn.config(bg=AppTheme.BTN_DISABLED,
                                  cursor="arrow", state="disabled")
            self.stop_btn.config(bg=AppTheme.BTN_RECORD,
                                 cursor="hand2", state="normal")
            self.status_dot.itemconfig(self.dot_oval, fill=AppTheme.DANGER)
            self.status_label.config(text="Recording", fg=AppTheme.DANGER)
        else:
            self.start_btn.config(bg=AppTheme.BTN_PRIMARY,
                                  cursor="hand2", state="normal")
            self.stop_btn.config(bg=AppTheme.BTN_DISABLED,
                                 cursor="arrow", state="disabled")
            self.status_dot.itemconfig(self.dot_oval, fill=AppTheme.SUCCESS)
            self.status_label.config(text="Ready", fg=AppTheme.SUCCESS)


class StatusBar(tk.Frame):
    """
    底部状态栏

    显示录制状态、已用时间、样本数量。
    PerfDog 风格的简洁状态栏。
    """

    def __init__(self, parent):
        """
        初始化状态栏

        Args:
            parent: 父容器
        """
        super().__init__(
            parent, height=AppTheme.STATUS_BAR_HEIGHT,
            bg=AppTheme.BG_SECONDARY
        )
        self.pack_propagate(False)

        self._build_status_bar()

    def _build_status_bar(self):
        """构建状态栏"""

        # 左: 状态指示
        left_frame = tk.Frame(self, bg=AppTheme.BG_SECONDARY)
        left_frame.pack(side=tk.LEFT, padx=15, pady=6)

        self.state_dot = tk.Canvas(
            left_frame, width=8, height=8,
            bg=AppTheme.BG_SECONDARY, highlightthickness=0
        )
        self.state_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.state_dot_oval = self.state_dot.create_oval(
            0, 0, 8, 8, fill=AppTheme.TEXT_SECONDARY, outline=""
        )

        self.state_label = tk.Label(
            left_frame, text="Idle",
            font=AppTheme.FONT_STATUS,
            bg=AppTheme.BG_SECONDARY, fg=AppTheme.TEXT_SECONDARY
        )
        self.state_label.pack(side=tk.LEFT)

        # 中: 已用时间
        self.time_label = tk.Label(
            self, text="00:00:00",
            font=AppTheme.FONT_STATUS,
            bg=AppTheme.BG_SECONDARY, fg=AppTheme.TEXT_PRIMARY
        )
        self.time_label.pack(side=tk.LEFT, expand=True, pady=6)

        # 右: 样本数
        self.samples_label = tk.Label(
            self, text="Samples: 0",
            font=AppTheme.FONT_STATUS,
            bg=AppTheme.BG_SECONDARY, fg=AppTheme.TEXT_SECONDARY
        )
        self.samples_label.pack(side=tk.RIGHT, padx=15, pady=6)

    def update_recording(self, is_recording: bool):
        """更新录制状态"""
        if is_recording:
            self.state_dot.itemconfig(self.state_dot_oval, fill=AppTheme.DANGER)
            self.state_label.config(text="Recording", fg=AppTheme.DANGER)
        else:
            self.state_dot.itemconfig(self.state_dot_oval, fill=AppTheme.TEXT_SECONDARY)
            self.state_label.config(text="Idle", fg=AppTheme.TEXT_SECONDARY)

    def update_elapsed(self, seconds: float):
        """更新已用时间显示"""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)
        self.time_label.config(text=f"{hours:02d}:{minutes:02d}:{secs:02d}")

    def update_samples(self, count: int):
        """更新样本计数"""
        self.samples_label.config(text=f"Samples: {count}")

    def show_message(self, message: str, is_warning: bool = False):
        """在状态栏显示临时消息"""
        color = AppTheme.WARNING if is_warning else AppTheme.TEXT_SECONDARY
        self.state_label.config(text=message, fg=color)
        # 2 秒后恢复
        self.after(2000, self._restore_state)

    def _restore_state(self):
        """恢复状态显示"""
        from perfsun.gui.components import StatusBar
        # 直接由外部管理
        pass
