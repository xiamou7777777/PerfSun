"""
PerfSun GUI 模块 (对标 PerfDog)

基于 Tkinter + Canvas 构建的专业性能监控图形界面。
采用深色主题，窄侧边栏 + 图表主体布局。
"""

from perfsun.gui.main_window import PerfSunApp, run_gui

__all__ = [
    "PerfSunApp",
    "run_gui",
]
