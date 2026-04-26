"""
PerfSun - 跨平台性能采集工具

入口点模块，提供 `python -m perfsun` 命令行启动功能。

使用方法：
    python -m perfsun devices                     # 列出设备
    python -m perfsun run -p com.example.game     # 实时采集
    python -m perfsun sessions                     # 列出会话
    python -m perfsun export --session ID --format html --output report.html  # 导出报告
    python -m perfsun stats                        # 数据库统计
    python -m perfsun info                         # 版本信息
"""

from perfsun.cli import main


if __name__ == '__main__':
    main()
