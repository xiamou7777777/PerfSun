"""
PerfSun 阈值告警管理器

本模块实现性能指标的阈值告警功能，对标 PerfDog 的告警系统。
当指标超过或低于设定阈值时，触发告警通知。

支持的告警类型：
- FPS 低于阈值（画面卡顿告警）
- CPU 使用率过高
- 内存使用过高
- GPU 使用率过高
- 温度过高（过热告警）
- Jank 率过高

告警触发方式：
- 控制台输出
- 回调函数
- 日志记录
- 自定义通知（可扩展）
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Callable, Any
from enum import Enum
import logging
import time
from datetime import datetime


logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """
    告警严重等级

    定义告警的严重程度，用于决定通知方式和处理策略。
    """
    INFO = "info"           # 信息提示
    WARNING = "warning"     # 警告
    ERROR = "error"         # 错误/严重
    CRITICAL = "critical"   # 严重告警


class AlertCondition(Enum):
    """
    告警触发条件类型
    """
    GREATER_THAN = "greater_than"   # 大于阈值时触发
    LESS_THAN = "less_than"         # 小于阈值时触发
    EQUAL = "equal"                 # 等于阈值时触发
    BETWEEN = "between"             # 在范围内触发
    OUTSIDE = "outside"             # 在范围外触发


@dataclass
class AlertRule:
    """
    告警规则定义

    定义一条告警规则的完整配置。

    Attributes:
        name: 告警规则名称
        metric_key: 监控的指标键名（如 fps、cpu_total、memory_pss）
        condition: 触发条件类型
        threshold: 阈值（单个值或 [min, max] 数组）
        severity: 告警等级
        duration: 持续超过阈值多少秒才触发（防抖）
        enabled: 是否启用
        message: 告警消息模板
        unit: 指标单位（用于消息格式化）
    """
    name: str
    metric_key: str
    condition: AlertCondition
    threshold: Any
    severity: AlertSeverity = AlertSeverity.WARNING
    duration: float = 0.0
    enabled: bool = True
    message: str = ""
    unit: str = ""

    def check_value(self, value: float) -> bool:
        """
        检查值是否触发告警

        Args:
            value: 当前指标值

        Returns:
            是否触发告警
        """
        if not self.enabled:
            return False

        if self.condition == AlertCondition.GREATER_THAN:
            return value > self.threshold
        elif self.condition == AlertCondition.LESS_THAN:
            return value < self.threshold
        elif self.condition == AlertCondition.EQUAL:
            return value == self.threshold
        elif self.condition == AlertCondition.BETWEEN:
            return self.threshold[0] <= value <= self.threshold[1]
        elif self.condition == AlertCondition.OUTSIDE:
            return value < self.threshold[0] or value > self.threshold[1]

        return False

    def format_message(self, value: float) -> str:
        """
        格式化告警消息

        Args:
            value: 当前指标值

        Returns:
            格式化后的告警消息
        """
        if self.message:
            return self.message.format(
                name=self.name,
                value=value,
                threshold=self.threshold,
                unit=self.unit
            )
        return f"[{self.severity.value.upper()}] {self.name}: {value:.2f}{self.unit} " \
               f"(阈值: {self.threshold}{self.unit})"


@dataclass
class AlertEvent:
    """
    告警事件

    记录一次告警触发事件的详细信息。

    Attributes:
        rule_name: 触发的规则名称
        metric_key: 指标键名
        value: 触发时的指标值
        threshold: 阈值
        severity: 告警等级
        timestamp: 触发时间戳
        message: 告警消息
    """
    rule_name: str
    metric_key: str
    value: float
    threshold: Any
    severity: AlertSeverity
    timestamp: float
    message: str

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "rule_name": self.rule_name,
            "metric_key": self.metric_key,
            "value": self.value,
            "threshold": self.threshold,
            "severity": self.severity.value,
            "timestamp": self.timestamp,
            "time": datetime.fromtimestamp(self.timestamp).strftime('%H:%M:%S'),
            "message": self.message,
        }


class AlertManager:
    """
    告警管理器

    管理和协调所有告警规则，对标 PerfDog 的阈值告警功能。
    支持自定义告警规则、回调通知和历史记录。

    Attributes:
        rules: 告警规则列表
        alerts: 告警事件历史
        callback: 告警触发时的回调函数
        _last_alert_time: 上次告警时间（用于防抖）
        _alert_counts: 各规则的告警计数
    """

    def __init__(self, callback: Optional[Callable[[AlertEvent], None]] = None):
        """
        初始化告警管理器

        Args:
            callback: 可选的告警回调函数，触发告警时调用
        """
        self.rules: List[AlertRule] = []
        self.alerts: List[AlertEvent] = []
        self.callback = callback
        self._last_alert_time: Dict[str, float] = {}
        self._alert_counts: Dict[str, int] = {}
        self._suppress_seconds: float = 5.0  # 同规则告警抑制时间（秒）

        # 初始化默认告警规则
        self._init_default_rules()
        logger.info("告警管理器初始化完成")

    def _init_default_rules(self) -> None:
        """
        初始化默认告警规则

        设置一组常用的性能告警规则。
        """
        default_rules = [
            AlertRule(
                name="FPS过低",
                metric_key="fps",
                condition=AlertCondition.LESS_THAN,
                threshold=30.0,
                severity=AlertSeverity.WARNING,
                message="帧率过低: {value:.1f}fps (阈值: {threshold}fps)",
                unit="fps",
            ),
            AlertRule(
                name="严重掉帧",
                metric_key="fps",
                condition=AlertCondition.LESS_THAN,
                threshold=20.0,
                severity=AlertSeverity.ERROR,
                message="严重掉帧: {value:.1f}fps (阈值: {threshold}fps)",
                unit="fps",
            ),
            AlertRule(
                name="CPU过载",
                metric_key="cpu_total",
                condition=AlertCondition.GREATER_THAN,
                threshold=80.0,
                severity=AlertSeverity.WARNING,
                message="CPU使用率过高: {value:.1f}% (阈值: {threshold}%)",
                unit="%",
            ),
            AlertRule(
                name="内存过高",
                metric_key="memory_pss",
                condition=AlertCondition.GREATER_THAN,
                threshold=1024.0,
                severity=AlertSeverity.WARNING,
                message="内存使用过高: {value:.1f}MB (阈值: {threshold}MB)",
                unit="MB",
            ),
            AlertRule(
                name="CPU过热",
                metric_key="temperature_cpu",
                condition=AlertCondition.GREATER_THAN,
                threshold=75.0,
                severity=AlertSeverity.ERROR,
                message="CPU温度过高: {value:.1f}°C (阈值: {threshold}°C)",
                unit="°C",
            ),
            AlertRule(
                name="GPU过热",
                metric_key="temperature_battery",
                condition=AlertCondition.GREATER_THAN,
                threshold=45.0,
                severity=AlertSeverity.WARNING,
                message="电池温度过高: {value:.1f}°C (阈值: {threshold}°C)",
                unit="°C",
            ),
            AlertRule(
                name="卡顿率过高",
                metric_key="jank_rate",
                condition=AlertCondition.GREATER_THAN,
                threshold=5.0,
                severity=AlertSeverity.WARNING,
                message="卡顿率过高: {value:.2f}% (阈值: {threshold}%)",
                unit="%",
            ),
        ]

        for rule in default_rules:
            self.add_rule(rule)

    def add_rule(self, rule: AlertRule) -> None:
        """
        添加告警规则

        Args:
            rule: 告警规则

        Raises:
            ValueError: 规则名称重复
        """
        # 检查名称唯一性
        for existing in self.rules:
            if existing.name == rule.name:
                raise ValueError(f"告警规则名称已存在: {rule.name}")

        self.rules.append(rule)
        logger.debug(f"已添加告警规则: {rule.name} ({rule.metric_key})")

    def remove_rule(self, rule_name: str) -> bool:
        """
        移除告警规则

        Args:
            rule_name: 规则名称

        Returns:
            是否移除成功
        """
        for i, rule in enumerate(self.rules):
            if rule.name == rule_name:
                self.rules.pop(i)
                logger.debug(f"已移除告警规则: {rule_name}")
                return True
        return False

    def update_rule(self, rule_name: str, **kwargs) -> bool:
        """
        更新告警规则参数

        Args:
            rule_name: 规则名称
            **kwargs: 要更新的字段（threshold, severity, enabled 等）

        Returns:
            是否更新成功
        """
        for rule in self.rules:
            if rule.name == rule_name:
                for key, value in kwargs.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                logger.debug(f"已更新告警规则: {rule_name}")
                return True
        return False

    def enable_rule(self, rule_name: str) -> bool:
        """
        启用告警规则

        Args:
            rule_name: 规则名称

        Returns:
            是否启用成功
        """
        return self.update_rule(rule_name, enabled=True)

    def disable_rule(self, rule_name: str) -> bool:
        """
        禁用告警规则

        Args:
            rule_name: 规则名称

        Returns:
            是否禁用成功
        """
        return self.update_rule(rule_name, enabled=False)

    def check_metrics(self, metrics: Dict[str, float]) -> List[AlertEvent]:
        """
        检查指标是否触发告警

        对传入的指标字典检查所有启用的告警规则。

        Args:
            metrics: 指标字典，key 为指标名，value 为指标值

        Returns:
            本次触发的告警事件列表
        """
        triggered = []

        for rule in self.rules:
            if not rule.enabled:
                continue

            if rule.metric_key not in metrics:
                continue

            value = metrics[rule.metric_key]
            if not rule.check_value(value):
                continue

            # 防抖检查
            last_time = self._last_alert_time.get(rule.name, 0)
            if time.time() - last_time < self._suppress_seconds:
                continue

            # 创建告警事件
            event = AlertEvent(
                rule_name=rule.name,
                metric_key=rule.metric_key,
                value=value,
                threshold=rule.threshold,
                severity=rule.severity,
                timestamp=time.time(),
                message=rule.format_message(value),
            )

            self.alerts.append(event)
            self._last_alert_time[rule.name] = time.time()
            self._alert_counts[rule.name] = self._alert_counts.get(rule.name, 0) + 1
            triggered.append(event)

            # 日志记录
            log_func = {
                AlertSeverity.INFO: logger.info,
                AlertSeverity.WARNING: logger.warning,
                AlertSeverity.ERROR: logger.error,
                AlertSeverity.CRITICAL: logger.critical,
            }.get(rule.severity, logger.warning)
            log_func(f"告警触发: {event.message}")

            # 回调通知
            if self.callback:
                try:
                    self.callback(event)
                except Exception as e:
                    logger.error(f"告警回调执行失败: {e}")

        return triggered

    def check_snapshot(self, snapshot: Any) -> List[AlertEvent]:
        """
        检查指标快照是否触发告警

        Args:
            snapshot: 指标快照对象（需有 to_dict 或 to_csv_row 方法）

        Returns:
            本次触发的告警事件列表
        """
        try:
            if hasattr(snapshot, 'to_csv_row'):
                metrics = snapshot.to_csv_row()
            elif hasattr(snapshot, 'to_dict'):
                metrics = snapshot.to_dict()
            else:
                metrics = {}

            return self.check_metrics(metrics)
        except Exception as e:
            logger.error(f"检查快照告警失败: {e}")
            return []

    def get_alerts(
        self,
        count: Optional[int] = None,
        severity: Optional[AlertSeverity] = None,
    ) -> List[AlertEvent]:
        """
        获取告警历史

        Args:
            count: 返回条数限制
            severity: 按等级过滤

        Returns:
            告警事件列表
        """
        result = self.alerts

        if severity:
            result = [a for a in result if a.severity == severity]

        if count:
            result = result[-count:]

        return result

    def get_active_alerts(self) -> List[AlertEvent]:
        """
        获取活跃告警（最近 60 秒内触发的告警）

        Returns:
            活跃告警列表
        """
        now = time.time()
        return [a for a in self.alerts if now - a.timestamp < 60]

    def get_stats(self) -> Dict[str, Any]:
        """
        获取告警统计信息

        Returns:
            告警统计字典
        """
        return {
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for r in self.rules if r.enabled),
            "total_alerts": len(self.alerts),
            "alert_counts": dict(self._alert_counts),
            "active_alerts": len(self.get_active_alerts()),
        }

    def clear_alerts(self) -> None:
        """
        清除所有告警历史
        """
        self.alerts.clear()
        self._alert_counts.clear()
        self._last_alert_time.clear()
        logger.debug("告警历史已清除")

    def set_callback(self, callback: Callable[[AlertEvent], None]) -> None:
        """
        设置告警回调函数

        Args:
            callback: 告警触发时的回调函数
        """
        self.callback = callback
        logger.debug("告警回调已设置")

    def set_suppress_time(self, seconds: float) -> None:
        """
        设置告警抑制时间

        同一规则在抑制时间内不会重复触发。

        Args:
            seconds: 抑制时间（秒）
        """
        self._suppress_seconds = max(0, seconds)
