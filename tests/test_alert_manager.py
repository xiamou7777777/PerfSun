"""
PerfSun 告警管理器单元测试

测试阈值告警功能：
- 告警规则定义和检查
- 告警触发和防抖
- 告警事件记录
- 告警统计和查询
"""

import pytest
import time
from perfsun.core.alert_manager import (
    AlertManager,
    AlertRule,
    AlertEvent,
    AlertSeverity,
    AlertCondition,
)


class TestAlertSeverity:
    """AlertSeverity 枚举测试类"""

    def test_severity_values(self):
        """测试告警等级枚举值"""
        assert AlertSeverity.INFO.value == "info"
        assert AlertSeverity.WARNING.value == "warning"
        assert AlertSeverity.ERROR.value == "error"
        assert AlertSeverity.CRITICAL.value == "critical"

    def test_severity_order(self):
        """测试告警等级顺序"""
        severities = [AlertSeverity.INFO, AlertSeverity.WARNING,
                      AlertSeverity.ERROR, AlertSeverity.CRITICAL]
        assert len(severities) == 4


class TestAlertCondition:
    """AlertCondition 枚举测试类"""

    def test_condition_values(self):
        """测试告警条件枚举值"""
        assert AlertCondition.GREATER_THAN.value == "greater_than"
        assert AlertCondition.LESS_THAN.value == "less_than"
        assert AlertCondition.EQUAL.value == "equal"
        assert AlertCondition.BETWEEN.value == "between"
        assert AlertCondition.OUTSIDE.value == "outside"


class TestAlertRule:
    """AlertRule 测试类"""

    def test_rule_creation(self):
        """测试告警规则创建"""
        rule = AlertRule(
            name="测试规则",
            metric_key="fps",
            condition=AlertCondition.LESS_THAN,
            threshold=30.0,
            severity=AlertSeverity.WARNING,
        )
        assert rule.name == "测试规则"
        assert rule.metric_key == "fps"
        assert rule.enabled is True

    def test_check_greater_than(self):
        """测试大于条件检查"""
        rule = AlertRule(
            name="CPU过载",
            metric_key="cpu",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
        )
        assert rule.check_value(90.0) is True
        assert rule.check_value(80.0) is False  # 不包含等于
        assert rule.check_value(50.0) is False

    def test_check_less_than(self):
        """测试小于条件检查"""
        rule = AlertRule(
            name="FPS过低",
            metric_key="fps",
            condition=AlertCondition.LESS_THAN,
            threshold=30.0,
        )
        assert rule.check_value(20.0) is True
        assert rule.check_value(30.0) is False  # 不包含等于
        assert rule.check_value(60.0) is False

    def test_check_equal(self):
        """测试等于条件检查"""
        rule = AlertRule(
            name="精确匹配",
            metric_key="value",
            condition=AlertCondition.EQUAL,
            threshold=42.0,
        )
        assert rule.check_value(42.0) is True
        assert rule.check_value(41.0) is False

    def test_check_between(self):
        """测试范围条件检查"""
        rule = AlertRule(
            name="温度正常范围",
            metric_key="temp",
            condition=AlertCondition.BETWEEN,
            threshold=[20.0, 80.0],
        )
        assert rule.check_value(50.0) is True
        assert rule.check_value(20.0) is True   # 包含边界
        assert rule.check_value(80.0) is True   # 包含边界
        assert rule.check_value(10.0) is False
        assert rule.check_value(90.0) is False

    def test_check_outside(self):
        """测试范围外条件检查"""
        rule = AlertRule(
            name="温度异常",
            metric_key="temp",
            condition=AlertCondition.OUTSIDE,
            threshold=[0.0, 100.0],
        )
        assert rule.check_value(-10.0) is True
        assert rule.check_value(110.0) is True
        assert rule.check_value(50.0) is False  # 在范围内

    def test_disabled_rule(self):
        """测试禁用规则"""
        rule = AlertRule(
            name="已禁用规则",
            metric_key="cpu",
            condition=AlertCondition.GREATER_THAN,
            threshold=50.0,
            enabled=False,
        )
        assert rule.check_value(90.0) is False  # 已禁用，不触发

    def test_format_message_custom(self):
        """测试自定义告警消息格式化"""
        rule = AlertRule(
            name="FPS过低",
            metric_key="fps",
            condition=AlertCondition.LESS_THAN,
            threshold=30.0,
            message="帧率过低: {value:.1f}fps (阈值: {threshold}fps)",
            unit="fps",
        )
        msg = rule.format_message(25.5)
        assert "帧率过低" in msg
        assert "25.5" in msg
        assert "fps" in msg

    def test_format_message_default(self):
        """测试默认告警消息格式化"""
        rule = AlertRule(
            name="CPU过载",
            metric_key="cpu",
            condition=AlertCondition.GREATER_THAN,
            threshold=80.0,
            severity=AlertSeverity.WARNING,
            unit="%",
        )
        msg = rule.format_message(95.0)
        assert "WARNING" in msg
        assert "CPU" in msg
        assert "95.00%" in msg


class TestAlertEvent:
    """AlertEvent 测试类"""

    def test_event_creation(self):
        """测试告警事件创建"""
        event = AlertEvent(
            rule_name="FPS过低",
            metric_key="fps",
            value=25.0,
            threshold=30.0,
            severity=AlertSeverity.WARNING,
            timestamp=1000.0,
            message="帧率过低: 25.0fps",
        )
        assert event.rule_name == "FPS过低"
        assert event.value == 25.0
        assert event.severity == AlertSeverity.WARNING

    def test_to_dict(self):
        """测试转换为字典"""
        event = AlertEvent(
            rule_name="测试",
            metric_key="fps",
            value=25.0,
            threshold=30.0,
            severity=AlertSeverity.WARNING,
            timestamp=1713456789.0,
            message="测试告警",
        )
        data = event.to_dict()
        assert data["rule_name"] == "测试"
        assert data["severity"] == "warning"
        assert "time" in data
        assert data["value"] == 25.0


class TestAlertManager:
    """AlertManager 测试类"""

    def setup_method(self):
        """每个测试方法执行前的 setup"""
        self.manager = AlertManager()

    def test_initialization(self):
        """测试初始化状态"""
        stats = self.manager.get_stats()
        assert stats["total_rules"] == 7  # 默认规则数
        assert stats["enabled_rules"] == 7
        assert stats["total_alerts"] == 0
        assert stats["active_alerts"] == 0

    def test_default_rules(self):
        """测试默认告警规则"""
        rule_names = [r.name for r in self.manager.rules]
        assert "FPS过低" in rule_names
        assert "严重掉帧" in rule_names
        assert "CPU过载" in rule_names
        assert "内存过高" in rule_names
        assert "CPU过热" in rule_names
        assert "GPU过热" in rule_names
        assert "卡顿率过高" in rule_names

    def test_add_rule(self):
        """测试添加规则"""
        rule = AlertRule(
            name="自定义规则",
            metric_key="custom_metric",
            condition=AlertCondition.GREATER_THAN,
            threshold=100.0,
        )
        self.manager.add_rule(rule)
        assert len(self.manager.rules) == 8

    def test_add_duplicate_rule(self):
        """测试添加重复规则"""
        rule = AlertRule(
            name="FPS过低",  # 已存在的规则名
            metric_key="fps",
            condition=AlertCondition.LESS_THAN,
            threshold=30.0,
        )
        with pytest.raises(ValueError, match="告警规则名称已存在"):
            self.manager.add_rule(rule)

    def test_remove_rule(self):
        """测试移除规则"""
        assert self.manager.remove_rule("FPS过低") is True
        assert len(self.manager.rules) == 6

        assert self.manager.remove_rule("不存在的规则") is False

    def test_update_rule(self):
        """测试更新规则"""
        assert self.manager.update_rule("FPS过低", threshold=25.0, severity=AlertSeverity.ERROR) is True
        rule = self.manager.rules[0]
        assert rule.threshold == 25.0
        assert rule.severity == AlertSeverity.ERROR

        assert self.manager.update_rule("不存在的规则", threshold=10.0) is False

    def test_enable_disable_rule(self):
        """测试启用/禁用规则"""
        assert self.manager.disable_rule("FPS过低") is True
        rule = next(r for r in self.manager.rules if r.name == "FPS过低")
        assert rule.enabled is False

        assert self.manager.enable_rule("FPS过低") is True
        assert rule.enabled is True

    def test_check_metrics_fps_alert(self):
        """测试 FPS 过低告警"""
        alerts = self.manager.check_metrics({"fps": 25.0})
        assert len(alerts) >= 1
        assert alerts[0].metric_key == "fps"

    def test_check_metrics_cpu_alert(self):
        """测试 CPU 过载告警"""
        alerts = self.manager.check_metrics({"cpu_total": 90.0})
        assert len(alerts) == 1
        assert alerts[0].rule_name == "CPU过载"

    def test_check_metrics_no_alert(self):
        """测试正常指标不触发告警"""
        alerts = self.manager.check_metrics({
            "fps": 60.0,
            "cpu_total": 30.0,
            "memory_pss": 500.0,
        })
        assert len(alerts) == 0

    def test_alert_suppression(self):
        """测试告警防抖抑制"""
        self.manager._suppress_seconds = 0.1  # 设置短抑制时间便于测试

        # 第一次触发（仅触发 FPS过低，不触发严重掉帧）
        alerts1 = self.manager.check_metrics({"fps": 25.0})
        assert len(alerts1) == 1  # FPS过低

        # 第二次立即触发相同指标（应被抑制）
        alerts2 = self.manager.check_metrics({"fps": 25.0})
        assert len(alerts2) == 0  # 被抑制

        # 等待抑制时间后再次触发
        time.sleep(0.15)
        alerts3 = self.manager.check_metrics({"fps": 25.0})
        assert len(alerts3) == 1

    def test_multi_metric_alert(self):
        """测试多指标同时告警"""
        alerts = self.manager.check_metrics({
            "fps": 15.0,          # 触发 严重掉帧
            "cpu_total": 85.0,     # 触发 CPU过载
            "temperature_cpu": 80.0,  # 触发 CPU过热
        })

        rule_names = {a.rule_name for a in alerts}
        assert "严重掉帧" in rule_names
        assert "CPU过载" in rule_names
        assert "CPU过热" in rule_names

    def test_alert_history(self):
        """测试告警历史记录"""
        self.manager.check_metrics({"fps": 25.0})
        self.manager.check_metrics({"cpu_total": 90.0})

        assert len(self.manager.alerts) == 2
        assert len(self.manager.get_alerts(count=1)) == 1
        assert len(self.manager.get_alerts(severity=AlertSeverity.WARNING)) >= 1

    def test_get_active_alerts(self):
        """测试获取活跃告警"""
        assert len(self.manager.get_active_alerts()) == 0

        self.manager.check_metrics({"fps": 20.0})
        alerts = self.manager.get_active_alerts()
        assert len(alerts) == 1

    def test_clear_alerts(self):
        """测试清除告警"""
        self.manager.check_metrics({"fps": 20.0})
        assert len(self.manager.alerts) > 0

        self.manager.clear_alerts()
        assert len(self.manager.alerts) == 0
        assert len(self.manager.get_alerts()) == 0

    def test_callback(self):
        """测试告警回调函数"""
        callback_results = []

        def test_callback(event):
            callback_results.append(event)

        self.manager.set_callback(test_callback)
        self.manager.check_metrics({"fps": 20.0})

        assert len(callback_results) == 1
        assert callback_results[0].rule_name == "FPS过低"

    def test_check_snapshot(self):
        """测试基于快照的告警检查"""
        from perfsun.core.data_point import MetricsSnapshot, FPSData

        snapshot = MetricsSnapshot(
            timestamp=1000.0,
            device_id="test",
            platform="android",
            fps=FPSData(fps=25.0),
        )

        alerts = self.manager.check_snapshot(snapshot)
        assert len(alerts) == 1  # 触发 FPS过低
        assert alerts[0].rule_name == "FPS过低"

    def test_get_stats(self):
        """测试获取告警统计"""
        self.manager.check_metrics({"fps": 20.0})
        self.manager.check_metrics({"cpu_total": 85.0})

        stats = self.manager.get_stats()
        assert stats["total_alerts"] >= 2
        assert stats["total_rules"] == 7
        assert "FPS过低" in stats["alert_counts"]
        assert "CPU过载" in stats["alert_counts"]

    def test_set_suppress_time(self):
        """测试设置抑制时间"""
        self.manager.set_suppress_time(10.0)
        assert self.manager._suppress_seconds == 10.0

        self.manager.set_suppress_time(-1.0)  # 负数应被截断为0
        assert self.manager._suppress_seconds == 0.0


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
