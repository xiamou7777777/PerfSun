# PerfSun 性能采集工具

**版本**: 1.1.0
**更新时间**: 2026-04-26

---

## 项目简介

PerfSun 是一款跨平台(Windows、Android、iOS)性能数据采集工具,无需 ROOT/越狱即可获取设备性能指标,定位对标行业标杆 PerfDog。

### 核心能力

| 指标类型 | Android | iOS | Windows |
|---------|---------|-----|---------|
| FPS/帧耗时/Jank | ✅ dumpsys gfxinfo | ✅ CADisplayLink | ✅ DXGI Hook |
| CPU使用率 | ✅ /proc/stat | ✅ libimobiledevice | ✅ PDH |
| GPU使用率 | ⚠️ 部分设备 | ⚠️ 越狱 | ✅ DXGI/NVAPI |
| 内存(PSS/RSS) | ✅ dumpsys meminfo | ✅ sysmontap | ✅ psutil |
| 电量/功耗 | ✅ batterystats | ⚠️ 估算 | ✅ WMI |
| 网络流量 | ✅ /proc/net/dev | ✅ libimobiledevice | ✅ PDH |
| 温度 | ✅ sysfs | ⚠️ 越狱 | ⚠️ WMI |
| 功耗估算 | ✅ 模型估算 | ✅ 模型估算 | ✅ 模型估算 |
| 阈值告警 | ✅ 实时检测 | ✅ 实时检测 | ✅ 实时检测 |

---

## 功能特性

### 1. 实时采集
- 以指定频率(如 1Hz)采样所有指标
- 支持动态调整采样频率
- 支持单独采集特定指标(FPS only, CPU only 等)

### 2. 帧率采集
- 支持显示实时 FPS、帧时间曲线
- 卡顿次数统计(Jank / BigJank)
- 帧率数据平滑处理

### 3. 进程监控
- 用户指定包名(Android)/BundleID(iOS)/进程名(Windows)
- 自动关联子进程

### 4. 自定义打点
- 通过命令行发送标记
- 在时序图上体现事件标记

### 5. 录制与回放
- 数据存入本地 SQLite 数据库
- 支持离线分析

### 6. 阈值告警
- 当 CPU、内存或帧率低于阈值时触发提示

### 7. 多设备并发
- 同时连接多台 Android 或 iOS 设备
- 分别采集,统一管理

### 8. 数据导出
- 导出为 CSV/JSON/Excel 标准格式
- 生成包含图表的 HTML 报告（5张趋势图：FPS、帧时间、CPU+内存、GPU+网络、温度）

### 9. 阈值告警系统
- 内置 7 条默认告警规则（FPS过低、CPU过载、内存过高、过热等）
- 支持自定义告警规则和阈值
- 告警防抖抑制，避免重复告警
- 告警回调通知机制
- 实时仪表盘告警显示

### 10. 功耗估算
- 基于性能指标的功耗模型
- 支持手机/平板/笔记本/台式机四种设备类型
- CPU/GPU/屏幕/网络分项功耗
- 电池消耗速率预测（%/小时）
- 累计能耗计算（焦耳/mAh）

### 11. 图形界面 (GUI)
- 基于 PyQt6 的桌面图形界面
- 实时曲线图表显示
- 设备管理和配置面板
- 采集控制与监控

---

## 系统要求

### Python 版本
- Python 3.10 或更高版本

### 平台支持

#### Android
- Android 5.0 (API 21) 及以上
- 需要启用 USB 调试
- ADB 工具已安装并配置到系统 PATH

#### iOS
- iOS 13 及以上
- 需要连接 Mac 设备
- 需要安装 Xcode Command Line Tools
- 需要 pymobiledevice3 库

#### Windows
- Windows 10/11
- 需要管理员权限(部分功能)

---

## 安装指南

### 1. 克隆项目

```bash
git clone https://github.com/perfsun/perfsun.git
cd PerfSun
```

### 2. 创建虚拟环境(推荐)

```bash
python -m venv venv
source venv/bin/activate  # Linux/macOS
venv\Scripts\activate     # Windows
```

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

### 4. 可选依赖安装

```bash
# iOS 支持
pip install pymobiledevice3

# NVIDIA GPU 支持
pip install py3nvml

# Web 服务支持
pip install websockets fastapi
```

### 5. 验证安装

```bash
python -m perfsun info
```

---

## 使用方法

### 1. 检测设备

```bash
# 列出所有已连接设备
python -m perfsun devices
```

输出示例:
```
Platform   Device ID     Status    Model
---------  ------------  --------  --------------
Android    8ABC123456    online    Pixel 6
Windows    DESKTOP-ABC   local     -
```

### 2. 实时采集

```bash
# 基本用法
python -m perfsun run -p com.example.game

# 指定采样间隔(0.5秒)
python -m perfsun run -p com.example.game -i 0.5

# 指定采集时长(60秒)
python -m perfsun run -p com.example.game --duration 60

# 添加自定义标记
python -m perfsun run -p com.example.game --mark start_game --mark level_2

# 仅采集 FPS
python -m perfsun run -p com.example.game --fps-only

# 采集并导出 CSV
python -m perfsun run -p com.example.game -o data.csv --format csv

# 指定设备
python -m perfsun run -p com.example.game -d 8ABC123456
```

### 3. 添加标记

```bash
# 在当前会话中添加标记
python -m perfsun mark "scene_2_loaded"

# 为指定会话添加标记
python -m perfsun mark "button_clicked" --session SESSION_ID
```

### 4. 导出会话数据

```bash
# 导出为 CSV
python -m perfsun export --session SESSION_ID --format csv --output data.csv

# 导出为 JSON
python -m perfsun export --session SESSION_ID --format json --output data.json

# 导出为 HTML 报告
python -m perfsun export --session SESSION_ID --format html --output report.html
```

### 5. 会话管理

```bash
# 列出所有会话
python -m perfsun sessions

# 删除会话
python -m perfsun delete --session SESSION_ID
```

### 6. 告警管理

```bash
# 查看告警历史（实时采集模式中自动显示）
python -m perfsun alerts
```

### 7. 数据库统计

```bash
python -m perfsun stats
```

### 8. 查看系统信息

```bash
python -m perfsun info
```

### 9. 启动图形界面

```bash
python -m perfsun gui
```

---

## 命令行参数详解

### run 命令

| 参数 | 简写 | 默认值 | 说明 |
|-----|------|--------|------|
| --package | -p | 必需 | 目标包名/BundleID/进程名 |
| --device | -d | 自动选择 | 设备ID |
| --platform | - | auto | 平台类型(android/ios/windows/auto) |
| --interval | -i | 1.0 | 采样间隔(秒) |
| --duration | - | 0 | 采集时长(秒),0表示无限 |
| --output | -o | - | 输出文件路径 |
| --format | - | csv | 导出格式(csv/json/excel/html) |
| --mark | - | - | 自定义标记 |
| --fps-only | - | False | 仅采集FPS |
| --cpu-only | - | False | 仅采集CPU |
| --memory-only | - | False | 仅采集内存 |

### mark 命令

| 参数 | 说明 |
|-----|------|
| mark_name | 标记名称 |
| --session | 会话ID(可选) |

### export 命令

| 参数 | 说明 |
|-----|------|
| --session | 必需,会话ID |
| --format | 导出格式(csv/json/excel/html) |
| --output | 输出文件路径 |

---

## 数据格式说明

### CSV 导出格式

```csv
timestamp,device_id,platform,package_name,fps,fps_min,fps_max,frame_time_avg,
cpu_total,cpu_process,memory_pss,memory_rss,memory_vss,gpu,
network_upload,network_download,jank_count,big_jank_count,jank_rate,
temperature_cpu,temperature_battery,battery_level,marks
```

### JSON 导出格式

```json
{
    "export_time": "2026-04-18T12:00:00",
    "session": {
        "id": "session_id",
        "device_id": "device_id",
        "platform": "android",
        "package_name": "com.example.app",
        "start_time": 1713456789.0,
        "duration": 60.0,
        "sample_count": 60
    },
    "marks": [
        {"timestamp": 1713456790.0, "name": "start_game", "mark_type": "user"}
    ],
    "metrics_count": 60,
    "metrics": [...]
}
```

---

## 架构设计

### 整体架构

```
┌─────────────────────────────────────────────────────────────────────┐
│                           PerfSun CLI                               │
│                    (Click + Rich Console)                           │
├─────────────────────────────────────────────────────────────────────┤
│                         Core Engine                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────┐  │
│  │ DataCollector│  │ DataRecorder │  │ DataExporter │  │ Alert    │  │
│  │   Manager    │  │   Manager    │  │   Manager    │  │ Manager  │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────┘  │
├─────────────────────────────────────────────────────────────────────┤
│                      Platform Collectors                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │AndroidCollector│ │  IOSCollector │ │WindowsCollector│              │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
├─────────────────────────────────────────────────────────────────────┤
│                      Platform Adapters                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │  ADB Client  │  │libimobiledevice│ │   PDH/WMI   │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
└─────────────────────────────────────────────────────────────────────┘
```

### 模块说明

| 模块 | 路径 | 说明 |
|-----|------|------|
| core/data_point | perfsun/core/data_point.py | 数据结构定义 |
| core/collector_manager | perfsun/core/collector_manager.py | 采集器生命周期管理 |
| core/data_recorder | perfsun/core/data_recorder.py | SQLite 数据持久化 |
| core/data_exporter | perfsun/core/data_exporter.py | 数据导出(CSV/JSON/Excel/HTML) |
| core/alert_manager | perfsun/core/alert_manager.py | 阈值告警系统 |
| collectors/android | perfsun/collectors/android.py | Android 平台采集 |
| collectors/ios | perfsun/collectors/ios.py | iOS 平台采集 |
| collectors/windows | perfsun/collectors/windows.py | Windows 平台采集 |
| utils/adb | perfsun/utils/adb.py | ADB 命令封装 |
| utils/jank_detector | perfsun/utils/jank_detector.py | 卡顿检测算法（含自适应阈值） |
| utils/frame_smoother | perfsun/utils/frame_smoother.py | 帧率平滑算法（滑动平均/指数/卡尔曼） |
| utils/power_estimator | perfsun/utils/power_estimator.py | 功耗估算模型 |

---

## 卡顿检测算法

### 判定规则

- **Jank**: 当前帧时间 > 上一帧时间 × 2 且 > 84ms (60Hz 下两帧)
- **BigJank**: 当前帧时间 > 125ms

### 自适应阈值

设备刷新率不同时,阈值会自动调整:

| 刷新率 | Jank 阈值 | BigJank 阈值 |
|-------|----------|-------------|
| 60Hz | 84ms | 125ms |
| 90Hz | 56ms | 83ms |
| 120Hz | 42ms | 62ms |
| 144Hz | 35ms | 52ms |

---

## 帧率平滑算法

### 支持的平滑方式

| 算法 | 类名 | 说明 | 适用场景 |
|-----|------|------|---------|
| 滑动平均 | FrameRateSmoother | 基于固定窗口的移动平均 | 通用场景，平滑效果适中 |
| 指数平滑 | ExponentialSmoother | 指数加权移动平均(EWMA) | 对实时性要求高的场景 |
| 卡尔曼滤波 | KalmanSmoother | 基于卡尔曼滤波的预测-更新 | 噪声较大的数据源 |

### 使用示例

```python
from perfsun.utils.frame_smoother import create_smoother

# 滑动平均（窗口大小5）
smoother = create_smoother("moving_average", window_size=5)
fps = smoother.add_frame_time(16.67)

# 指数平滑（alpha=0.3）
smoother = create_smoother("exponential", alpha=0.3)

# 卡尔曼滤波
smoother = create_smoother("kalman", q=0.1, r=1.0)
```

---

## 阈值告警系统

### 默认告警规则

| 规则名称 | 指标 | 条件 | 阈值 | 等级 |
|---------|------|------|------|------|
| FPS过低 | fps | < | 30 fps | WARNING |
| 严重掉帧 | fps | < | 20 fps | ERROR |
| CPU过载 | cpu_total | > | 80% | WARNING |
| 内存过高 | memory_pss | > | 1024 MB | WARNING |
| CPU过热 | temperature_cpu | > | 75°C | ERROR |
| GPU过热 | temperature_battery | > | 45°C | WARNING |
| 卡顿率过高 | jank_rate | > | 5% | WARNING |

### 告警触发流程

```
指标快照 → 遍历告警规则 → 条件判定 → 防抖检查 → 事件记录 → 回调通知
```

### 自定义告警规则

```python
from perfsun.core.alert_manager import AlertManager, AlertRule, AlertCondition, AlertSeverity

manager = AlertManager()

# 添加自定义规则
rule = AlertRule(
    name="内存告警",
    metric_key="memory_pss",
    condition=AlertCondition.GREATER_THAN,
    threshold=2048.0,  # 2GB
    severity=AlertSeverity.ERROR,
    message="内存使用过高: {value:.0f}MB",
    unit="MB",
)
manager.add_rule(rule)

# 检查指标
alerts = manager.check_metrics({"memory_pss": 2500.0})
for alert in alerts:
    print(f"⚠ {alert.message}")
```

---

## 功耗估算

### 设备类型参数

| 设备类型 | CPU 每核功耗 | GPU 功耗 | 屏幕功耗 | 网络功耗 | 基础功耗 |
|---------|-------------|---------|---------|---------|---------|
| 手机 | 0.4W | 1.5W | 0.8W | 0.3W | 0.2W |
| 平板 | 0.5W | 2.0W | 1.5W | 0.4W | 0.3W |
| 笔记本 | 1.0W | 3.0W | 2.0W | 0.5W | 0.5W |
| 台式机 | 2.0W | 5.0W | 3.0W | 0.5W | 1.0W |

### 估算模型

```
总功耗 = (CPU功耗 + GPU功耗 + 屏幕功耗 + 网络功耗 + 基础功耗) × 温度系数

CPU功耗 = CPU使用率 × 核心数 × cpu_power_per_core
GPU功耗 = GPU使用率 × gpu_power
屏幕功耗 = screen_power × 0.8（采集时屏幕常亮）
网络功耗 = 网络活跃度 × network_power
温度系数 = 1.0 + max(0, 温度 - 40) × thermal_coefficient
```

### 使用示例

```python
from perfsun.utils.power_estimator import PowerEstimator, DeviceType

estimator = PowerEstimator(
    device_type=DeviceType.PHONE,
    cpu_cores=8,
    battery_capacity=4000,  # mAh
)

# 基于指标快照估算
estimate = estimator.estimate_from_snapshot(snapshot)
print(f"当前功耗: {estimate.total_power:.2f}W")
print(f"电池消耗: {estimate.battery_drain_rate:.1f}%/h")
print(f"累计能耗: {estimator.get_total_energy():.1f}J")
```

---

## 注意事项

### Android

1. **设备授权**: 首次连接时需要在设备上确认 USB 调试授权
2. **无线 ADB**: 支持通过 `adb connect <ip>:<port>` 无线连接
3. **包名验证**: 确保包名正确,可通过 `adb shell pm list packages` 查看
4. **GPU 支持**: 部分设备 GPU 使用率可能无法获取

### iOS

1. **Mac 依赖**: 必须连接 Mac 设备才能使用
2. **开发者证书**: 部分功能需要有效的开发者证书
3. **越狱限制**: 非越狱环境电量、温度等指标受限
4. **pymobiledevice3**: 确保版本兼容 iOS 设备系统版本

### Windows

1. **管理员权限**: 部分功能(如性能计数器)需要管理员权限
2. **FPS 采集**: 需要针对特定进程进行 DXGI Hook
3. **GPU 支持**: 仅支持 NVIDIA 显卡(通过 NVML)

---

## 故障排查

### 常见问题

**Q: Android 设备未检测到**
```
1. 检查 USB 连接是否正常
2. 确认设备已启用 USB 调试
3. 运行 'adb devices' 查看设备状态
4. 尝试重新安装 ADB 驱动
```

**Q: 采集数据为空**
```
1. 确认包名正确
2. 检查应用是否正在运行
3. 查看日志输出(添加 -v 参数)
4. 尝试重新连接设备
```

**Q: iOS 采集失败**
```
1. 确认 pymobiledevice3 已安装
2. 检查 Mac 与 iOS 设备连接
3. 验证开发者证书是否有效
4. 查看设备是否已信任此电脑
```

---

## 开发指南

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-cov

# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_jank_detector.py -v

# 生成覆盖率报告
python -m pytest tests/ --cov=perfsun --cov-report=html
```

### 代码规范

- 遵循 PEP 8 代码规范
- 使用中文注释
- 所有公共API需有文档字符串

---

## 扩展开发

### 添加新平台支持

1. 在 `perfsun/collectors/` 下创建新平台采集器类
2. 继承 `Collectible` 基类
3. 实现所有抽象方法
4. 在 `cli.py` 中注册新平台

### 添加新指标

1. 在 `data_point.py` 中定义新指标数据结构
2. 在对应平台的 `collect()` 方法中实现采集逻辑
3. 更新 `data_exporter.py` 的导出字段

---

## 许可证

本项目采用 MIT 许可证。详见 LICENSE 文件。

---

## 更新日志

### v1.1.0 (2026-04-26)
- 新增实时仪表盘（Rich Live Dashboard）
- 新增阈值告警系统（AlertManager）
- 新增功耗估算模块（PowerEstimator）
- 新增图形界面（PyQt6 GUI）
- 新增 HTML 报告 5 张趋势图表
- 完善帧率平滑算法（指数平滑、卡尔曼滤波）
- 完善自适应 Jank 检测（AdaptiveJankDetector）
- 完善 ADBTools（电池信息、进程管理）
- 完善所有代码中文注释和文档
- 新增 alerts、gui、info CLI 命令

### v1.0.0 (2026-04-18)
- 初始版本发布
- 支持 Android/iOS/Windows 三大平台
- 实现 FPS、CPU、内存、GPU、网络等指标采集
- 支持 CSV/JSON/Excel/HTML 数据导出
- 内置卡顿检测和帧率平滑算法
