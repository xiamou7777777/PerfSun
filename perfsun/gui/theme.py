"""
PerfSun GUI 主题配置 (对标 PerfDog 深色风格)

集中管理所有视觉设计令牌，包括颜色、字体、布局常量。
采用 GitHub Dark Mode 风格的专业深色配色方案。
"""


class AppTheme:
    """PerfDog 风格深色主题设计令牌"""

    # ── 背景色系 ──────────────────────────────────
    BG_PRIMARY = "#0D1117"       # 主背景 (最深)
    BG_SECONDARY = "#161B22"     # 卡片/区块背景
    BG_TERTIARY = "#21262D"      # 悬停/激活状态
    BG_TOOLBAR = "#0D1117"       # 侧边栏背景
    BG_TOOLBAR_SEC = "#161B22"   # 侧边栏按钮区
    BG_CARD = "#161B22"          # 指标卡片背景
    BG_INPUT = "#0D1117"         # 输入框背景

    # ── 文本色系 ──────────────────────────────────
    TEXT_PRIMARY = "#E6EDF3"     # 主文本 (亮白)
    TEXT_SECONDARY = "#8B949E"   # 辅助文本 (灰)
    TEXT_DIM = "#484F58"         # 禁用/占位文本
    TEXT_ACCENT = "#58A6FF"      # 强调文本 (蓝)

    # ── 指标颜色 (每个指标独立色系) ───────────────
    FPS = "#58A6FF"              # 蓝色
    CPU = "#3FB950"              # 绿色
    MEMORY = "#D29922"           # 琥珀色
    GPU = "#BC8CFF"              # 紫色
    NETWORK = "#F0883E"          # 橙色
    TEMPERATURE = "#F85149"      # 红色
    POWER = "#79C0FF"            # 亮蓝
    JANK = "#F85149"             # 红色 (卡顿)

    METRIC_COLORS = {
        "fps": FPS,
        "cpu": CPU,
        "memory": MEMORY,
        "gpu": GPU,
        "network": NETWORK,
        "temperature": TEMPERATURE,
        "power": POWER,
        "jank": JANK,
    }

    # ── 语义色 ────────────────────────────────────
    SUCCESS = "#3FB950"          # 成功/就绪
    WARNING = "#D29922"          # 警告
    DANGER = "#F85149"           # 危险/录制中
    INFO = "#58A6FF"             # 信息

    # ── 按钮色系 ──────────────────────────────────
    BTN_RECORD = "#DA3633"       # 录制按钮 (红)
    BTN_RECORD_HOVER = "#B62324"
    BTN_STOP = "#DA3633"         # 停止按钮
    BTN_STOP_HOVER = "#B62324"
    BTN_PRIMARY = "#238636"      # 主要按钮 (绿)
    BTN_PRIMARY_HOVER = "#2EA043"
    BTN_SECONDARY = "#21262D"    # 次要按钮
    BTN_SECONDARY_HOVER = "#30363D"
    BTN_TEXT = "#C9D1D9"
    BTN_DISABLED = "#484F58"

    # ── 边框 ──────────────────────────────────────
    BORDER = "#30363D"           # 默认边框
    BORDER_FOCUS = "#58A6FF"    # 聚焦边框
    BORDER_CARD = "#21262D"     # 卡片边框

    # ── 图表 ──────────────────────────────────────
    CHART_GRID = "#21262D"       # 网格线
    CHART_AXIS = "#484F58"       # 坐标轴标签
    CHART_LINE_WIDTH = 2
    CHART_FILL_ALPHA = "gray50"  # 填充透明度

    # ── 布局尺寸 ──────────────────────────────────
    SIDEBAR_WIDTH = 180          # 侧边栏宽度
    METRIC_CARD_WIDTH = 165      # 指标卡片宽度
    METRIC_CARD_HEIGHT = 90      # 指标卡片高度
    STATUS_BAR_HEIGHT = 36       # 状态栏高度
    HEADER_HEIGHT = 52           # 顶部栏高度
    CHART_TOOLBAR_HEIGHT = 32    # 图表工具栏高度

    # ── 字体 ──────────────────────────────────────
    FONT_FAMILY = "Segoe UI"
    FONT_TITLE = (FONT_FAMILY, 18, "bold")
    FONT_HEADER = (FONT_FAMILY, 11, "bold")
    FONT_NORMAL = (FONT_FAMILY, 10)
    FONT_SMALL = (FONT_FAMILY, 9)
    FONT_METRIC_VALUE = (FONT_FAMILY, 22, "bold")
    FONT_METRIC_LABEL = (FONT_FAMILY, 9, "bold")
    FONT_CHART_LABEL = (FONT_FAMILY, 8)
    FONT_BUTTON = (FONT_FAMILY, 10, "bold")
    FONT_STATUS = (FONT_FAMILY, 9)
    FONT_SIDEBAR_BTN = (FONT_FAMILY, 11)
