# PerfSun 性能采集工具 - 技术规格说明书

**版本**: 1.1.0
**日期**: 2026-04-26
**作者**: PerfSun Development Team

---

## 1. 项目概述

### 1.1 项目目标

PerfSun 是一款跨平台（Windows、Android、iOS）性能数据采集工具，无需 ROOT/越狱即可获取设备性能指标，定位对标行业标杆 PerfDog。

### 1.2 核心能力

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

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                           PerfSun CLI                               │
│                    (argparse + rich console)                        │
├─────────────────────────────────────────────────────────────────────┤
│                         Core Engine                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                │
│  │ DataCollector│  │ DataRecorder │  │ DataExporter│                │
│  │   Manager    │  │   Manager    │  │   Manager    │                │
│  └──────────────┘  └──────────────┘  └──────────────┘                │
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

### 2.2 核心类图

```
Collectible (Abstract Base)
├── AndroidCollector
├── IOSCollector
└── WindowsCollector

MetricsSnapshot (Data Class)
├── FPSData
├── CPUData
├── MemoryData
├── GPUData
├── NetworkData
├── TemperatureData
├── JankStats
└── PowerEstimate

DataRecorder
├── SQLite 持久化
├── 会话 CRUD
└── 时间范围查询

DataExporter
├── CSV 导出
├── JSON 导出
├── Excel 导出（3 sheet）
└── HTML 导出（Chart.js 5 图）

AlertManager
├── AlertRule (条件/阈值/等级)
├── AlertEvent (事件记录)
├── 防抖抑制
└── 回调通知

PowerEstimator
├── 4 种设备类型参数
├── CPU/GPU/屏幕/网络分项
└── 电池消耗预测
```

### 2.3 数据流

```
设备 → PlatformAdapter → Collector → DataAggregator → Recorder/Exporter
                         ↓
                    Real-time UI
                    (WebSocket)
```

---

## 3. 模块详细设计

### 3.1 核心模块

#### 3.1.1 收集器管理器 (CollectorManager)

**职责**:
- 管理所有平台收集器生命周期
- 处理多设备并发采集
- 动态注册/注销收集器

**关键方法**:
```python
class CollectorManager:
    def register_collector(self, platform: str, collector: Collectible) -> None
    def unregister_collector(self, platform: str, device_id: str) -> None
    def start_collection(self, device_id: str, config: CollectorConfig) -> None
    def stop_collection(self, device_id: str) -> None
    def get_collector(self, device_id: str) -> Optional[Collectible]
```

#### 3.1.2 数据记录器 (DataRecorder)

**职责**:
- SQLite 数据库操作
- 记录会话管理
- 数据查询和过滤

**数据库Schema**:
```sql
CREATE TABLE sessions (
    id TEXT PRIMARY KEY,
    device_id TEXT NOT NULL,
    platform TEXT NOT NULL,
    package_name TEXT,
    start_time REAL NOT NULL,
    end_time REAL,
    duration REAL,
    sample_count INTEGER DEFAULT 0
);

CREATE TABLE metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    metric_type TEXT NOT NULL,
    value REAL NOT NULL,
    metadata TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);

CREATE TABLE marks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT NOT NULL,
    timestamp REAL NOT NULL,
    mark_name TEXT NOT NULL,
    mark_type TEXT DEFAULT 'custom',
    FOREIGN KEY (session_id) REFERENCES sessions(id)
);
```

#### 3.1.3 数据导出器 (DataExporter)

**支持格式**:
- CSV: 适用于大数据量、日志分析
- JSON: 适用于 API 集成、Web 前端
- Excel: 适用于报告生成、图表展示（3 个工作表）
- HTML: 交互式报告（Chart.js 5 张趋势图）

#### 3.1.4 告警管理器 (AlertManager)

**职责**:
- 管理和匹配告警规则
- 实时检测指标是否超过阈值
- 防抖抑制（同规则 5 秒内不重复触发）
- 回调通知机制
- 告警事件记录和统计

**默认规则**:
| 规则 | 指标 | 条件 | 阈值 | 等级 |
|-----|------|------|------|------|
| FPS过低 | fps | < 30 | WARNING | 帧率过低 |
| 严重掉帧 | fps | < 20 | ERROR | 严重掉帧 |
| CPU过载 | cpu_total | > 80% | WARNING | CPU 过载 |
| 内存过高 | memory_pss | > 1024MB | WARNING | 内存过高 |
| CPU过热 | temperature_cpu | > 75°C | ERROR | 过热 |
| GPU过热 | temperature_battery | > 45°C | WARNING | 过热 |
| 卡顿率过高 | jank_rate | > 5% | WARNING | 卡顿过多 |

#### 3.1.5 功耗估算器 (PowerEstimator)

**职责**:
- 基于性能指标估算设备功耗
- 支持手机/平板/笔记本/台式机
- 分项功耗（CPU/GPU/屏幕/网络/基础）
- 电池消耗速率和累计能耗计算

**估算模型**:
```python
# 功率 = 使用率 × 硬件参数
cpu_power = cpu_usage * cpu_cores * cpu_power_per_core
gpu_power = gpu_usage * gpu_power
screen_power = screen_power * 0.8  # 常亮估算
network_power = net_activity * network_power
total_power = (cpu + gpu + screen + network + base) * thermal_factor

# 电池消耗
drain_rate = (total_power / 3.7V * 1000) / battery_mAh * 100  # %/h
```

---

## 4. Android 采集实现

### 4.1 ADB 连接管理

**连接方式**:
1. USB 连接: `adb devices` 自动检测
2. 无线 ADB: `adb connect <ip>:<port>`

**设备检测流程**:
```python
def detect_devices(self) -> List[AndroidDevice]:
    result = subprocess.run(['adb', 'devices'], capture_output=True, text=True)
    devices = []
    for line in result.stdout.strip().split('\n')[1:]:
        if 'device' in line and 'unauthorized' not in line:
            device_id = line.split()[0]
            devices.append(AndroidDevice(id=device_id, connection=self._get_connection_type(device_id)))
    return devices
```

### 4.2 FPS 采集

**数据来源**: `dumpsys gfxinfo <package> framestats`

**解析字段**:
- `FrameTime`: 帧渲染时间
- `Flags`: 帧状态标志
- `IntendedVsync` / `ActualVsync`: 预期vsync和实际vsync

**Jank 判定算法**:
```python
def is_jank(self, frame_time_ms: float, prev_frame_time_ms: float) -> bool:
    """
    Jank: 当前帧时间 > 上一帧时间 * 2 且 > 84ms (60Hz)
    BigJank: 当前帧时间 > 125ms
    """
    if frame_time_ms > 125:
        return 'big_jank'
    elif frame_time_ms > prev_frame_time_ms * 2 and frame_time_ms > 84:
        return 'jank'
    return None
```

### 4.3 内存采集

**数据来源**: `dumpsys meminfo <pid>`

**提取字段**:
- `TOTAL`: 总 PSS
- `Java Heap`: Java 堆内存
- `Native Heap`: Native 堆内存
- `Code`: 代码段内存
- `Stack`: 栈内存
- `Graphics`: 图形内存

### 4.4 CPU 采集

**数据来源**: `/proc/stat` (系统) 和 `/proc/<pid>/stat` (进程)

**计算公式**:
```python
def calculate_cpu_usage(self, cpu_times: CpuTimes) -> float:
    total = cpu_times.user + cpu_times.nice + cpu_times.system + cpu_times.idle
    if total == 0:
        return 0.0
    busy = total - cpu_times.idle - cpu_times.iowait
    return (busy / total) * 100.0
```

---

## 5. iOS 采集实现

### 5.1 连接方式

**推荐方案**: `pymobiledevice3` (Python 库)
**备选方案**: `libimobiledevice` (C 库封装)

### 5.2 FPS 采集

**数据来源**: `dvt sysmontap` 或 `xctrace record`

**解析显示链路**:
```python
def get_fps(self) -> float:
    sysmontap = self.device.developer.dvt.sysmontap
    data = sysmontap.parse()
    # 从 DisplayLink 数据计算 FPS
    return data.get('DisplayRefreshRate', 0)
```

### 5.3 CPU/内存采集

**数据来源**: `sysmontap` 服务

**提取字段**:
- `cpu_instructions`: CPU 指令数
- `memory_phys_footprint`: 物理内存占用
- `memory_compressed`: 压缩内存

---

## 6. Windows 采集实现

### 6.1 PDH 性能计数器

**关键计数器**:
- `\Processor(_Total)\% Processor Time`: CPU 总使用率
- `\Process(_Total)\Working Set`: 内存使用
- `\Network Interface(*)\Bytes Received/sec`: 网络接收
- `\GPU Engine(*)\Utilization Percentage`: GPU 使用率

### 6.2 FPS 采集

**方案**: Hook DXGI Present 调用

**实现方式**:
```python
# 使用 py-dxgi 实现帧率统计
def get_dxgi_fps(self, process_name: str) -> float:
    # 查询 DXGI 提供者获取帧率
    pass
```

### 6.3 GPU 采集

**支持库**:
- NVIDIA: `py3nvml` (NVML API)
- AMD: `pyamd` (ADL API)
- 通用: DXGI 查询

---

## 7. CLI 接口设计

### 7.1 命令结构

```
perfsun [OPTIONS] COMMAND [ARGS]...
```

### 7.2 核心命令

#### 7.2.1 devices - 列出设备

```bash
perfsun devices
```

输出:
```
Platform   Device ID     Status    Model           Package/Process
---------  ------------  --------  --------------  -----------------
Android    8ABC123456    online    Pixel 6         com.example.app
iOS        00001234-AB   online    iPhone 14 Pro   com.example.app
Windows    DESKTOP-ABC   local     -               example.exe
```

#### 7.2.2 run - 实时采集

```bash
perfsun run -p com.example.game -o data.csv --interval 0.5 --mark start_game
```

参数:
- `-p, --package`: 目标包名/进程名
- `-o, --output`: 输出文件路径
- `-i, --interval`: 采样间隔（秒），默认 1.0
- `--mark`: 发送自定义标记
- `--duration`: 采集时长（秒），0 表示无限
- `--platform`: 平台类型（android/ios/windows/auto）

#### 7.2.3 record - 录制会话

```bash
perfsun record --duration 60 --export report.html
```

参数:
- `--session`: 会话 ID（从 run 命令获取）
- `--duration`: 录制时长
- `--export`: 导出格式（csv/json/excel/html）

#### 7.2.4 mark - 添加标记

```bash
perfsun mark "scene_2_loaded"
```

#### 7.2.5 export - 导出数据

```bash
perfsun export --session SESSION_ID --format csv --output data.csv
```

#### 7.2.6 alerts - 查看告警

```bash
perfsun alerts
perfsun alerts --session SESSION_ID
```

#### 7.2.7 stats - 数据库统计

```bash
perfsun stats
```

#### 7.2.8 info - 系统信息

```bash
perfsun info
```

#### 7.2.9 gui - 图形界面

```bash
perfsun gui
```

---

## 8. 数据格式规范

### 8.1 实时数据 JSON 格式

```json
{
    "timestamp": 1713456789.123,
    "device_id": "8ABC123456",
    "platform": "android",
    "metrics": {
        "fps": {
            "value": 58.5,
            "unit": "fps",
            "min": 45,
            "max": 62
        },
        "cpu": {
            "total": 35.2,
            "process": 12.5,
            "unit": "percent"
        },
        "memory": {
            "pss": 256,
            "rss": 512,
            "vss": 1024,
            "unit": "MB"
        },
        "gpu": {
            "value": 28.0,
            "unit": "percent"
        },
        "network": {
            "upload": 1024,
            "download": 2048,
            "unit": "KB/s"
        },
        "temperature": {
            "cpu": 42.5,
            "battery": 35.0,
            "unit": "celsius"
        }
    },
    "marks": ["start_game"],
    "jank_stats": {
        "jank_count": 2,
        "big_jank_count": 0,
        "jank_rate": 0.5
    }
}
```

### 8.2 导出 CSV 格式

```csv
timestamp,device_id,platform,fps,cpu_total,cpu_process,memory_pss,memory_rss,gpu,net_up,net_down,jank,jank_big,temp_cpu,temp_battery
1713456789.123,8ABC123456,android,58.5,35.2,12.5,256,512,28.0,1024,2048,2,0,42.5,35.0
```

---

## 9. 依赖管理

### 9.1 核心依赖

```
# requirements.txt
# Core
click>=8.1.0
rich>=13.0.0
pandas>=2.0.0
numpy>=1.24.0

# Android
adbutils>=0.15.0

# iOS
pymobiledevice3>=3.0.0

# Windows
psutil>=5.9.0
pywin32>=300
pygments>=2.15.0

# Export
xlsxwriter>=3.1.0
openpyxl>=3.1.0
jinja2>=3.1.0

# GUI
PyQt6>=6.7.0
pyqtgraph>=0.13.3

# Utilities
schedule>=1.2.0
```

### 9.2 可选依赖

```
# For GPU monitoring on NVIDIA
py3nvml>=0.2.0

# For DXGI frame rate
py-dxgi>=0.1.0

# For web UI
websockets>=11.0.0
fastapi>=0.100.0
```

---

## 10. 关键难点与解决方案

### 10.1 非 ROOT iOS 性能采集限制

**问题**: iOS 非越狱环境无法直接访问系统性能数据。

**解决方案**:
1. 使用 `pymobiledevice3` 的 `dvt` 服务（需开发者证书签名）
2. 对于 CADisplayLink FPS，通过远程帧回调获取
3. 电量使用基于 CPU/屏幕亮度的估算模型

### 10.2 实时帧率抖动过滤

**问题**: 瞬时帧率波动大，影响数据可读性。

**解决方案**:
```python
class FrameRateSmoother:
    def __init__(self, window_size: int = 5):
        self.window_size = window_size
        self.frame_times = deque(maxlen=window_size)

    def add(self, frame_time: float) -> float:
        self.frame_times.append(frame_time)
        return sum(self.frame_times) / len(self.frame_times)
```

### 10.3 多线程采集性能影响

**问题**: 高频采集可能影响被测应用性能。

**解决方案**:
1. 采集频率默认限制在 1Hz，避免过度采集
2. 使用异步 I/O 和连接池
3. 对于 Android，使用 `adb shell` 批处理命令
4. 监控采集器自身的 CPU 使用率并报警

### 10.4 ADB 断开重连

**问题**: USB 断开或无线网络波动导致采集中断。

**解决方案**:
```python
def reconnect_with_retry(self, device_id: str, max_retries: int = 3) -> bool:
    for attempt in range(max_retries):
        try:
            subprocess.run(['adb', 'connect', device_id], check=True)
            if self.is_device_online(device_id):
                return True
        except subprocess.CalledProcessError:
            time.sleep(2 ** attempt)  # 指数退避
    return False
```

---

## 11. 测试验证方法

### 11.1 FPS 准确性验证

**方法**: 对比 PerfDog/GameBench 采集结果

**判定标准**:
- 平均 FPS 误差 < 2 fps
- Jank 次数误差 < 15%

### 11.2 内存误差验证

**方法**: 对比 `dumpsys meminfo` 与 Android Studio Profiler

**判定标准**:
- PSS 误差 < 10%

### 11.3 CPU 采样准确性

**方法**: 对比 `top` / `htop` 读数

**判定标准**:
- 采样值与系统监控工具读数误差 < 5%

---

## 12. 扩展性设计

### 12.1 插件化采集器

```python
class CollectorPlugin:
    def __init__(self, name: str, platform: str):
        self.name = name
        self.platform = platform

    def collect(self) -> DataPoint:
        raise NotImplementedError

    def get_metrics(self) -> List[str]:
        raise NotImplementedError

# 注册插件
manager.register_plugin(CollectorPlugin('linux_net', 'linux'))
```

### 12.2 支持的平台扩展

- Linux: 使用 `/proc` 文件系统和 `sysfs`
- macOS: 使用 `powermetrics` 和 `top`

---

## 13. 错误处理与优雅降级

### 13.1 异常处理策略

```python
try:
    data = collector.collect()
except DeviceDisconnectedError:
    logger.warning("Device disconnected, attempting reconnect...")
    collector.reconnect()
except PermissionDeniedError:
    logger.error("Permission denied, check ADB authorization")
    # 优雅降级：记录警告，继续采集其他指标
except UnsupportedMetricError as e:
    logger.warning(f"Metric {e.metric} not supported on this device")
```

### 13.2 降级行为

| 场景 | 降级行为 |
|------|---------|
| GPU 不可用 | 字段留空，记录警告 |
| iOS 电量 | 使用估算模型 |
| 网络断开 | 本地缓存，恢复后上传 |
| 设备未授权 | 跳过该设备，继续检测 |

---

## 14. 安全注意事项

1. **ADB 授权**: 仅处理已授权设备，忽略 unauthorized 状态
2. **数据隔离**: 采集数据仅存储在本地，不上传第三方服务器
3. **权限最小化**: 仅请求必要权限，避免过度采集敏感信息
4. **证书安全**: iOS 开发者证书妥善保管，不硬编码在代码中

---

## 15. 文件结构

```
PerfSun/
├── SPEC.md
├── README.md
├── requirements.txt
├── pyproject.toml
├── perfsun/
│   ├── __init__.py
│   ├── __main__.py
│   ├── cli.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── collector_manager.py
│   │   ├── data_point.py
│   │   ├── data_recorder.py
│   │   ├── data_exporter.py
│   │   └── alert_manager.py          # 阈值告警系统
│   ├── collectors/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── android.py
│   │   ├── ios.py
│   │   └── windows.py
│   ├── utils/
│   │   ├── __init__.py
│   │   ├── adb.py
│   │   ├── frame_smoother.py
│   │   ├── jank_detector.py
│   │   └── power_estimator.py         # 功耗估算
│   ├── gui/
│   │   ├── __init__.py
│   │   ├── main_window.py
│   │   ├── main_window_simple.py      # PyQt6 图形界面
│   │   ├── main_window_tk.py          # Tkinter 备选界面
│   │   ├── device_panel.py            # 设备面板
│   │   ├── config_panel.py            # 配置面板
│   │   ├── metrics_panel.py           # 指标面板
│   │   └── chart_widget.py            # 图表组件
│   └── templates/
│       └── report.html
└── tests/
    ├── __init__.py
    ├── test_jank_detector.py
    ├── test_frame_smoother.py
    ├── test_data_exporter.py
    ├── test_data_recorder.py          # SQLite 持久化测试
    ├── test_alert_manager.py          # 告警系统测试
    └── test_power_estimator.py        # 功耗估算测试
```

---

**文档版本历史**:
- v1.0.0 (2026-04-18): 初始版本
