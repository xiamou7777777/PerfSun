"""
PerfSun 专业图表组件 (对标 PerfDog)

基于 Tkinter Canvas 实现的高质量时序图表，支持：
- Y 轴刻度标签和网格线
- X 轴时间标签
- 平滑曲线 + 渐变填充
- 图例 (当前值/平均值/最大值)
- 自动缩放 Y 轴
- 垂直标记线
"""

import math
import tkinter as tk
from collections import deque
from perfsun.gui.theme import AppTheme


class TimeSeriesChart(tk.Frame):
    """
    专业时序图表组件

    在 Canvas 上绘制带坐标轴、网格、图例的实时趋势曲线。
    布局:
    ┌─────────────────────────────────┐
    │  图例: 指标名 当前 平均 最大     │
    │  ┌─┬─────────────────────────┐  │
    │  │Y│                         │  │
    │  │ │  曲线 + 填充             │  │
    │  │ │                         │  │
    │  │ │  · · · 网格 · · ·      │  │
    │  │ │                         │  │
    │  └─┴─────────────────────┬───┘  │
    │          X 轴时间标签     │      │
    └──────────────────────────┴──────┘
    """

    def __init__(self, parent, metric_key: str, label: str, color: str,
                 y_min: float = 0, y_max: float = None, unit: str = "",
                 height: int = 220, width: int = None):
        """
        初始化图表

        Args:
            parent: 父容器
            metric_key: 指标键名
            label: 显示标签
            color: 曲线颜色
            y_min: Y 轴最小值
            y_max: Y 轴最大值 (None=自动缩放)
            unit: 单位
            height: 图表高度
            width: 图表宽度
        """
        super().__init__(parent, bg=AppTheme.BG_PRIMARY)
        self.metric_key = metric_key
        self.label = label
        self.color = color
        self.y_min = y_min
        self.y_max_fixed = y_max
        self.unit = unit
        self._user_set_y_max = y_max is not None

        # 数据存储
        self.max_points = 200
        self.data_points = deque(maxlen=self.max_points)  # (timestamp, value)

        # 标记线
        self.marks = []  # [(timestamp, label, color), ...]

        # Canvas 布局参数
        self.padding_left = 50      # Y 轴标签宽度
        self.padding_right = 10     # 右侧边距
        self.padding_top = 30       # 图例高度 (顶部留白)
        self.padding_bottom = 28    # X 轴标签高度

        # 缓存 Canvas 项目 ID
        self._chart_area = None
        self._curve_item = None
        self._fill_items = []
        self._grid_items = []
        self._axis_items = []
        self._legend_items = []
        self._mark_items = []

        # 当前图例值
        self._current_value = 0.0
        self._avg_value = 0.0
        self._max_value = 0.0

        # 构建 UI
        self._build_chart(parent, width, height)

    def _build_chart(self, parent, width, height):
        """构建图表 Canvas"""
        w = width or parent.winfo_width() or 500
        h = height
        self.canvas = tk.Canvas(
            self, width=w, height=h,
            bg=AppTheme.BG_PRIMARY, highlightthickness=0, bd=0
        )
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

    def _on_resize(self, event):
        """窗口大小变化时重绘"""
        self._draw_all()

    # ── 公共接口 ─────────────────────────────────

    def add_point(self, timestamp: float, value: float):
        """添加数据点"""
        self.data_points.append((timestamp, value))
        self._current_value = value
        self._update_stats()
        self._draw_all()

    def add_points(self, points: list):
        """批量添加数据点 [(timestamp, value), ...]"""
        for ts, val in points:
            self.data_points.append((ts, val))
        if points:
            self._current_value = points[-1][1]
        self._update_stats()
        self._draw_all()

    def add_mark(self, timestamp: float, label: str = "", color: str = None):
        """添加垂直标记线"""
        self.marks.append((timestamp, label, color or AppTheme.WARNING))
        self._draw_all()

    def clear_marks(self):
        """清除标记线"""
        self.marks.clear()
        self._draw_all()

    def clear(self):
        """清除所有数据"""
        self.data_points.clear()
        self.marks.clear()
        self._current_value = 0.0
        self._avg_value = 0.0
        self._max_value = 0.0
        self._draw_all()

    def set_y_range(self, y_min: float = 0, y_max: float = None):
        """设置 Y 轴范围"""
        self.y_min = y_min
        self.y_max_fixed = y_max
        self._user_set_y_max = y_max is not None
        self._draw_all()

    # ── 内部统计 ─────────────────────────────────

    def _update_stats(self):
        """更新统计值"""
        if not self.data_points:
            self._avg_value = 0.0
            self._max_value = 0.0
            return
        values = [v for _, v in self.data_points]
        self._avg_value = sum(values) / len(values)
        self._max_value = max(values)

    # ── 布局计算 ─────────────────────────────────

    def _compute_layout(self):
        """计算绘图区域坐标"""
        cw = self.canvas.winfo_width() or 500
        ch = self.canvas.winfo_height() or 220
        plot_x = self.padding_left
        plot_y = self.padding_top
        plot_w = max(cw - self.padding_left - self.padding_right, 100)
        plot_h = max(ch - self.padding_top - self.padding_bottom, 50)
        return cw, ch, plot_x, plot_y, plot_w, plot_h

    def _get_y_range(self):
        """获取 Y 轴范围"""
        if self._user_set_y_max and self.y_max_fixed is not None:
            return self.y_min, self.y_max_fixed

        if not self.data_points:
            return self.y_min, 100.0

        values = [v for _, v in self.data_points]
        data_max = max(values)
        data_min = min(values)

        if data_max <= 0 and self.y_min >= 0:
            return self.y_min, 100.0

        # 自动缩放: 留 20% 余量
        range_val = data_max - data_min
        if range_val < 1:
            range_val = 1
        y_max = data_max + range_val * 0.2
        y_min = max(0, data_min - range_val * 0.1)

        # 确保 y_min < y_max
        if y_max - y_min < 1:
            y_max = y_min + 1

        return y_min, y_max

    def _calc_ticks(self, y_min, y_max):
        """计算 Y 轴刻度值 (4-6 个刻度)"""
        range_val = y_max - y_min
        if range_val <= 0:
            return [0, 25, 50, 75, 100]

        # 计算合适的刻度间隔
        raw_step = range_val / 5
        magnitude = 10 ** math.floor(math.log10(raw_step))
        residual = raw_step / magnitude
        if residual <= 1.5:
            step = magnitude
        elif residual <= 3.5:
            step = 2 * magnitude
        elif residual <= 7.5:
            step = 5 * magnitude
        else:
            step = 10 * magnitude

        ticks = []
        start = math.floor(y_min / step) * step
        while start <= y_max + step:
            ticks.append(round(start, 2))
            start += step

        return ticks

    # ── 绘制方法 ─────────────────────────────────

    def _draw_all(self):
        """重绘整个图表"""
        if not self.canvas.winfo_width() or not self.canvas.winfo_height():
            return
        self.canvas.delete("all")
        self._draw_legend()
        self._draw_axes_and_grid()
        self._draw_marks()
        self._draw_curve()
        self._draw_fill()

    def _draw_legend(self):
        """绘制顶部图例"""
        cw, ch, px, py, pw, ph = self._compute_layout()

        # 指标名 + 颜色小方块
        legend_y = 6
        self.canvas.create_rectangle(
            8, legend_y + 2, 18, legend_y + 12,
            fill=self.color, outline=""
        )
        self.canvas.create_text(
            22, legend_y + 7, anchor="w",
            text=self.label, fill=AppTheme.TEXT_PRIMARY,
            font=AppTheme.FONT_HEADER
        )

        # 当前值 (大号)
        val_text = f"{self._current_value:.1f}" if self._current_value else "--"
        unit_text = f" {self.unit}" if self.unit else ""
        self.canvas.create_text(
            cw - 10, legend_y + 7, anchor="e",
            text=f"{val_text}{unit_text}", fill=self.color,
            font=AppTheme.FONT_METRIC_VALUE
        )

        # 平均值 + 最大值 (右上角当前值旁边)
        avg_text = f"平均: {self._avg_value:.1f}" if self._avg_value else ""
        max_text = f"最大: {self._max_value:.1f}" if self._max_value else ""
        stats_parts = [s for s in [avg_text, max_text] if s]
        if stats_parts:
            self.canvas.create_text(
                cw - 10, legend_y + 24, anchor="e",
                text="  |  ".join(stats_parts),
                fill=AppTheme.TEXT_SECONDARY, font=AppTheme.FONT_CHART_LABEL
            )

    def _draw_axes_and_grid(self):
        """绘制坐标轴和网格线"""
        cw, ch, px, py, pw, ph = self._compute_layout()
        y_min, y_max = self._get_y_range()
        ticks = self._calc_ticks(y_min, y_max)

        # Y 轴线和网格线
        for tick_val in ticks:
            # 将数值映射到像素
            ratio = (tick_val - y_min) / (y_max - y_min) if y_max != y_min else 0
            y_pos = py + ph - (ratio * ph)

            # 网格线 (虚线)
            if tick_val > y_min:
                self.canvas.create_line(
                    px, y_pos, px + pw, y_pos,
                    fill=AppTheme.CHART_GRID, dash=(3, 4), width=1
                )

            # Y 轴标签
            label = self._format_y_tick(tick_val)
            self.canvas.create_text(
                px - 6, y_pos, anchor="e",
                text=label, fill=AppTheme.CHART_AXIS,
                font=AppTheme.FONT_CHART_LABEL
            )

        # Y 轴线 (左边界)
        self.canvas.create_line(
            px, py, px, py + ph,
            fill=AppTheme.BORDER, width=1
        )

        # X 轴线 (底边界)
        self.canvas.create_line(
            px, py + ph, px + pw, py + ph,
            fill=AppTheme.BORDER, width=1
        )

        # X 轴时间标签
        if self.data_points:
            first_ts = self.data_points[0][0]
            last_ts = self.data_points[-1][0]
            duration = max(last_ts - first_ts, 0.1)

            # 显示 4-6 个时间标签
            num_labels = min(6, len(self.data_points))
            for i in range(num_labels):
                ratio = i / (num_labels - 1) if num_labels > 1 else 0.5
                x_pos = px + ratio * pw
                ts = first_ts + ratio * duration

                # 格式化为 MM:SS
                from datetime import datetime
                time_str = datetime.fromtimestamp(ts).strftime("%M:%S")

                self.canvas.create_text(
                    x_pos, py + ph + 14, anchor="n",
                    text=time_str, fill=AppTheme.CHART_AXIS,
                    font=AppTheme.FONT_CHART_LABEL
                )

    def _draw_marks(self):
        """绘制垂直标记线"""
        if not self.marks or not self.data_points:
            return

        cw, ch, px, py, pw, ph = self._compute_layout()
        first_ts = self.data_points[0][0]
        last_ts = self.data_points[-1][0]
        duration = max(last_ts - first_ts, 0.1)

        for ts, label, color in self.marks:
            ratio = (ts - first_ts) / duration if duration > 0 else 0
            x_pos = px + ratio * pw
            if px <= x_pos <= px + pw:
                self.canvas.create_line(
                    x_pos, py, x_pos, py + ph,
                    fill=color, dash=(6, 3), width=1.5
                )
                if label:
                    self.canvas.create_text(
                        x_pos, py - 4, anchor="s",
                        text=label, fill=color,
                        font=AppTheme.FONT_CHART_LABEL
                    )

    def _draw_curve(self):
        """绘制数据曲线"""
        if len(self.data_points) < 2:
            return

        cw, ch, px, py, pw, ph = self._compute_layout()
        y_min, y_max = self._get_y_range()
        first_ts = self.data_points[0][0]
        last_ts = self.data_points[-1][0]
        duration = max(last_ts - first_ts, 0.1)

        points = []
        for ts, val in self.data_points:
            x_ratio = (ts - first_ts) / duration if duration > 0 else 0
            x_pos = px + x_ratio * pw
            y_ratio = (val - y_min) / (y_max - y_min) if y_max != y_min else 0
            y_ratio = max(0, min(1, y_ratio))  # 裁剪到 [0,1]
            y_pos = py + ph - (y_ratio * ph)
            points.extend([x_pos, y_pos])

        if len(points) >= 4:
            self._curve_item = self.canvas.create_line(
                points, fill=self.color,
                width=AppTheme.CHART_LINE_WIDTH,
                smooth=True, splinesteps=10
            )

    def _draw_fill(self):
        """绘制渐变填充区域"""
        if len(self.data_points) < 2:
            return

        cw, ch, px, py, pw, ph = self._compute_layout()
        y_min, y_max = self._get_y_range()
        first_ts = self.data_points[0][0]
        last_ts = self.data_points[-1][0]
        duration = max(last_ts - first_ts, 0.1)

        # 构建填充多边形: 从左下角开始, 沿曲线, 到右下角
        fill_points = []

        # 左下角
        first_x = px
        fill_points.extend([first_x, py + ph])

        # 曲线上的点
        for ts, val in self.data_points:
            x_ratio = (ts - first_ts) / duration if duration > 0 else 0
            x_pos = px + x_ratio * pw
            y_ratio = (val - y_min) / (y_max - y_min) if y_max != y_min else 0
            y_ratio = max(0, min(1, y_ratio))
            y_pos = py + ph - (y_ratio * ph)
            fill_points.extend([x_pos, y_pos])

        # 右下角
        last_x = px + pw
        fill_points.extend([last_x, py + ph])

        if len(fill_points) >= 6:
            item = self.canvas.create_polygon(
                fill_points, fill=self.color,
                stipple=AppTheme.CHART_FILL_ALPHA,
                outline="", tags="chart_fill"
            )
            self._fill_items.append(item)

    def _format_y_tick(self, value: float) -> str:
        """格式化 Y 轴刻度标签"""
        if value >= 1000:
            return f"{value:.0f}"
        elif value >= 100:
            return f"{value:.0f}"
        elif value >= 10:
            return f"{value:.1f}"
        elif value >= 1:
            return f"{value:.1f}"
        else:
            return f"{value:.2f}"
