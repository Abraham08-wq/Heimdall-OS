"""
Purple Team Feedback Loop Engine (Phase 3D)

Automated detection gap analysis system that compares Red Team attack success rates
with Blue Team detection rates. Generates intelligence reports and recommended
defensive improvements based on execution data.

Key Features:
- Red/Blue team execution correlation
- Detection success/miss analysis
- Gap identification and scoring
- Threat modeling based on actual attacks
- Recommended defensive measures
- Automated metric aggregation
- Performance trends and predictions
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from enum import Enum
import json
import logging
from statistics import mean, stdev

logger = logging.getLogger(__name__)


# ============================================================================
# TYPES & ENUMS
# ============================================================================

class ExecutionTeam(str, Enum):
    """Team executing the operation"""
    RED = "RED"
    BLUE = "BLUE"
    NEUTRAL = "NEUTRAL"


class DetectionStatus(str, Enum):
    """Whether a Red Team attack was detected"""
    DETECTED = "detected"
    NOT_DETECTED = "not_detected"
    PARTIALLY_DETECTED = "partially_detected"
    INCONCLUSIVE = "inconclusive"


class GapSeverity(str, Enum):
    """Severity of a detection gap"""
    CRITICAL = "critical"  # Frequently missed, high-impact
    HIGH = "high"  # Often missed, significant impact
    MEDIUM = "medium"  # Sometimes missed
    LOW = "low"  # Rarely missed


@dataclass
class ExecutionMetrics:
    """Metrics from a single execution"""
    execution_id: str
    team: ExecutionTeam
    script_category: str
    success: bool
    duration_seconds: float
    resource_usage: Dict[str, float]  # cpu%, memory%
    detected: Optional[DetectionStatus] = None
    detection_latency_seconds: Optional[float] = None
    alerts_triggered: int = 0
    confidence_score: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class DetectionGap:
    """Identified gap in detection coverage"""
    gap_id: str
    technique_id: str  # MITRE ATT&CK TTP
    technique_name: str
    severity: GapSeverity
    missed_count: int
    detected_count: int
    detection_rate: float  # 0.0-1.0
    last_missed: datetime
    recommendations: List[str]
    affected_systems: List[str]
    estimated_dwell_time: float  # Days before detection (if at all)


@dataclass
class PurpleTeamReport:
    """Comprehensive Purple Team analysis report"""
    report_id: str
    generated_at: datetime
    period_start: datetime
    period_end: datetime
    red_team_count: int
    blue_team_count: int
    red_success_rate: float
    detection_rate: float
    detection_accuracy: float
    identified_gaps: List[DetectionGap]
    recommendations: List[str]
    metrics_by_category: Dict[str, Dict[str, float]]
    trend_analysis: Dict[str, Any]
    executive_summary: str


@dataclass
class DefensiveRecommendation:
    """Recommended defensive measure"""
    recommendation_id: str
    title: str
    description: str
    affected_gap_ids: List[str]
    implementation_effort: str  # low, medium, high
    estimated_coverage_increase: float  # 0.0-1.0
    affected_techniques: List[str]
    priority: int  # 1-10
    implementation_steps: List[str]


# ============================================================================
# PURPLE TEAM ANALYTICS ENGINE
# ============================================================================

class PurpleTeamFeedbackEngine:
    """
    Automated analysis of Red/Blue team operations to identify
    detection gaps and recommend defensive improvements.
    
    Workflow:
    1. Collect execution metrics (Red Team attacks, Blue Team responses)
    2. Correlate attacks with detections
    3. Identify patterns and gaps
    4. Generate recommendations
    5. Track improvement over time
    """

    def __init__(self):
        """Initialize the feedback engine"""
        self.metrics: Dict[str, ExecutionMetrics] = {}
        self.gaps: Dict[str, DetectionGap] = {}
        self.recommendations: Dict[str, DefensiveRecommendation] = {}
        self.reports: List[PurpleTeamReport] = []
        self.detection_baseline: Dict[str, float] = {}  # Baseline detection rates

    def record_execution(self, metrics: ExecutionMetrics) -> None:
        """Record metrics from a script execution"""
        self.metrics[metrics.execution_id] = metrics
        logger.debug(
            f"Recorded {metrics.team} team execution: {metrics.execution_id} "
            f"(success={metrics.success}, detected={metrics.detected})"
        )

    def analyze_detection_gap(
        self, technique_id: str, technique_name: str, lookback_hours: int = 24
    ) -> Optional[DetectionGap]:
        """
        Analyze detection performance for a specific technique.
        
        Returns gap if detection rate is below baseline.
        """
        # Collect relevant metrics from lookback period
        cutoff_time = datetime.utcnow() - timedelta(hours=lookback_hours)

        red_team_executions = [
            m
            for m in self.metrics.values()
            if m.team == ExecutionTeam.RED
            and m.timestamp > cutoff_time
            and technique_id in m.script_category
        ]

        if not red_team_executions:
            logger.warning(f"No Red Team executions found for technique {technique_id}")
            return None

        # Analyze detection outcomes
        detected_count = sum(
            1 for m in red_team_executions if m.detected == DetectionStatus.DETECTED
        )
        missed_count = sum(
            1 for m in red_team_executions if m.detected == DetectionStatus.NOT_DETECTED
        )

        total_count = detected_count + missed_count
        detection_rate = detected_count / total_count if total_count > 0 else 0.0

        # Check if below baseline
        baseline = self.detection_baseline.get(technique_id, 0.9)  # Expect 90% detection
        if detection_rate >= baseline:
            return None

        # Determine severity
        severity = self._calculate_gap_severity(detection_rate, missed_count)

        # Generate recommendations
        recommendations = self._generate_gap_recommendations(technique_id, technique_name)

        # Find last missed attack
        last_missed = max(
            (m.timestamp for m in red_team_executions if m.detected == DetectionStatus.NOT_DETECTED),
            default=datetime.utcnow(),
        )

        # Calculate dwell time estimate
        dwell_time_estimate = self._estimate_dwell_time(
            red_team_executions, missed_count
        )

        gap_id = f"gap_{technique_id}_{int(datetime.utcnow().timestamp())}"

        gap = DetectionGap(
            gap_id=gap_id,
            technique_id=technique_id,
            technique_name=technique_name,
            severity=severity,
            missed_count=missed_count,
            detected_count=detected_count,
            detection_rate=detection_rate,
            last_missed=last_missed,
            recommendations=recommendations,
            affected_systems=self._identify_affected_systems(red_team_executions),
            estimated_dwell_time=dwell_time_estimate,
        )

        self.gaps[gap_id] = gap
        logger.info(
            f"Identified {severity.value} gap: {technique_name} "
            f"(detection_rate={detection_rate:.2%})"
        )

        return gap

    def generate_purple_team_report(
        self, period_hours: int = 24
    ) -> PurpleTeamReport:
        """
        Generate comprehensive Purple Team analysis report.
        
        Returns:
        - Red Team attack success metrics
        - Blue Team detection metrics
        - Identified gaps with recommendations
        - Trend analysis
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=period_hours)

        # Filter metrics for period
        period_metrics = [m for m in self.metrics.values() if m.timestamp > cutoff_time]

        red_metrics = [m for m in period_metrics if m.team == ExecutionTeam.RED]
        blue_metrics = [m for m in period_metrics if m.team == ExecutionTeam.BLUE]

        report_id = f"report_{int(datetime.utcnow().timestamp())}"

        # Calculate metrics
        red_success_rate = (
            sum(1 for m in red_metrics if m.success) / len(red_metrics)
            if red_metrics
            else 0.0
        )

        detected_attacks = sum(
            1 for m in red_metrics if m.detected == DetectionStatus.DETECTED
        )
        detection_rate = (
            detected_attacks / len(red_metrics) if red_metrics else 0.0
        )

        # Identify all gaps
        all_gaps = list(self.gaps.values())

        # Calculate metrics by category
        metrics_by_category = self._calculate_metrics_by_category(period_metrics)

        # Analyze trends
        trend_analysis = self._analyze_trends(period_metrics)

        # Generate recommendations
        recommendations = self._prioritize_recommendations(all_gaps)

        # Generate executive summary
        executive_summary = self._generate_executive_summary(
            red_success_rate, detection_rate, all_gaps
        )

        report = PurpleTeamReport(
            report_id=report_id,
            generated_at=datetime.utcnow(),
            period_start=cutoff_time,
            period_end=datetime.utcnow(),
            red_team_count=len(red_metrics),
            blue_team_count=len(blue_metrics),
            red_success_rate=red_success_rate,
            detection_rate=detection_rate,
            detection_accuracy=self._calculate_detection_accuracy(red_metrics),
            identified_gaps=all_gaps,
            recommendations=recommendations,
            metrics_by_category=metrics_by_category,
            trend_analysis=trend_analysis,
            executive_summary=executive_summary,
        )

        self.reports.append(report)
        logger.info(f"Generated Purple Team Report: {report_id}")

        return report

    def recommend_defensive_measures(self, gap: DetectionGap) -> DefensiveRecommendation:
        """
        Generate specific defensive recommendation for a detected gap.
        """
        rec_id = f"rec_{gap.gap_id}_{int(datetime.utcnow().timestamp())}"

        # Determine implementation effort based on technique
        effort_mapping = {
            "high": ["MITRE ATT&CK - Advanced tactics"],
            "medium": ["Common exploitation techniques"],
            "low": ["Basic reconnaissance"],
        }

        implementation_effort = "medium"
        for difficulty, techniques in effort_mapping.items():
            if any(tech in gap.technique_name for tech in techniques):
                implementation_effort = difficulty

        # Estimate coverage increase
        coverage_increase = (1.0 - gap.detection_rate) * 0.7  # 70% of gap coverage

        # Generate implementation steps
        steps = self._generate_implementation_steps(gap.technique_id)

        recommendation = DefensiveRecommendation(
            recommendation_id=rec_id,
            title=f"Improve detection for {gap.technique_name}",
            description=f"Address detection gap with {gap.missed_count} missed attacks. "
                       f"Current detection rate: {gap.detection_rate:.2%}",
            affected_gap_ids=[gap.gap_id],
            implementation_effort=implementation_effort,
            estimated_coverage_increase=coverage_increase,
            affected_techniques=[gap.technique_id],
            priority=self._calculate_priority(gap),
            implementation_steps=steps,
        )

        self.recommendations[rec_id] = recommendation
        return recommendation

    def get_gap_trends(self, technique_id: str, days: int = 30) -> Dict[str, Any]:
        """
        Analyze trends in a specific detection gap over time.
        
        Returns:
        - Detection rate trend
        - Missed attacks trend
        - Predicted future rate
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)

        relevant_metrics = [
            m
            for m in self.metrics.values()
            if m.timestamp > cutoff_time and technique_id in m.script_category
        ]

        # Group by day
        daily_data: Dict[str, Dict] = {}
        for metric in relevant_metrics:
            day_key = metric.timestamp.date().isoformat()
            if day_key not in daily_data:
                daily_data[day_key] = {"detected": 0, "missed": 0}

            if metric.detected == DetectionStatus.DETECTED:
                daily_data[day_key]["detected"] += 1
            else:
                daily_data[day_key]["missed"] += 1

        # Calculate daily rates
        daily_rates = []
        for day_key in sorted(daily_data.keys()):
            data = daily_data[day_key]
            total = data["detected"] + data["missed"]
            rate = data["detected"] / total if total > 0 else 0.0
            daily_rates.append(rate)

        # Predict future rate using simple linear regression
        predicted_rate = self._predict_trend(daily_rates)

        return {
            "technique_id": technique_id,
            "days_analyzed": len(daily_data),
            "daily_rates": daily_rates,
            "current_rate": daily_rates[-1] if daily_rates else 0.0,
            "trend_direction": "improving" if len(daily_rates) > 1 and daily_rates[-1] > daily_rates[0] else "degrading",
            "predicted_rate_in_7_days": predicted_rate,
            "summary": self._generate_trend_summary(daily_rates, predicted_rate),
        }

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _calculate_gap_severity(self, detection_rate: float, missed_count: int) -> GapSeverity:
        """Determine severity level based on detection rate and miss count"""
        if detection_rate < 0.3 and missed_count >= 3:
            return GapSeverity.CRITICAL
        elif detection_rate < 0.6 and missed_count >= 2:
            return GapSeverity.HIGH
        elif detection_rate < 0.8:
            return GapSeverity.MEDIUM
        else:
            return GapSeverity.LOW

    def _generate_gap_recommendations(self, technique_id: str, technique_name: str) -> List[str]:
        """Generate recommendations for addressing a detection gap"""
        technique_to_recommendations = {
            "T1190": [
                "Enable Web Application Firewall (WAF) rules",
                "Implement virtual patching",
                "Increase monitoring on external-facing services",
            ],
            "T1003": [
                "Enable Credential Guard on Windows",
                "Monitor LSASS access patterns",
                "Implement EDR with memory scanning",
            ],
            "T1570": [
                "Enable network flow monitoring",
                "Implement lateral movement detection",
                "Monitor RDP and WinRM authentication failures",
            ],
            "T1595": [
                "Implement network intrusion detection",
                "Monitor for port scanning activity",
                "Enable firewall logging for blocked connections",
            ],
        }

        return technique_to_recommendations.get(
            technique_id,
            [
                "Review detection rules for this technique",
                "Implement behavior-based detection",
                "Increase logging and telemetry collection",
            ],
        )

    def _estimate_dwell_time(
        self, executions: List[ExecutionMetrics], missed_count: int
    ) -> float:
        """Estimate how long an attacker could operate undetected"""
        if not executions or missed_count == 0:
            return 0.0

        # Calculate average time between executions
        sorted_execs = sorted(executions, key=lambda m: m.timestamp)
        time_deltas = [
            (sorted_execs[i + 1].timestamp - sorted_execs[i].timestamp).total_seconds()
            for i in range(len(sorted_execs) - 1)
        ]

        if not time_deltas:
            return 0.0

        avg_delta_seconds = mean(time_deltas)
        # Estimate dwell time as missed_count * avg_delta_seconds
        dwell_time_seconds = missed_count * avg_delta_seconds
        dwell_time_days = dwell_time_seconds / (24 * 3600)

        return dwell_time_days

    def _identify_affected_systems(self, executions: List[ExecutionMetrics]) -> List[str]:
        """Identify systems affected by detection gap"""
        # Simplified: extract from execution context
        systems = set()
        for exe in executions[:5]:  # Sample first 5
            # In real implementation, extract from execution logs
            systems.add(f"system_{exe.execution_id[:8]}")

        return list(systems)

    def _calculate_metrics_by_category(self, metrics: List[ExecutionMetrics]) -> Dict[str, Dict[str, float]]:
        """Calculate metrics grouped by script category"""
        categories: Dict[str, List[ExecutionMetrics]] = {}

        for metric in metrics:
            if metric.script_category not in categories:
                categories[metric.script_category] = []
            categories[metric.script_category].append(metric)

        result = {}
        for category, cat_metrics in categories.items():
            success_rate = (
                sum(1 for m in cat_metrics if m.success) / len(cat_metrics)
                if cat_metrics
                else 0.0
            )
            detection_rate = (
                sum(1 for m in cat_metrics if m.detected == DetectionStatus.DETECTED)
                / len(cat_metrics)
                if cat_metrics
                else 0.0
            )

            result[category] = {
                "count": len(cat_metrics),
                "success_rate": success_rate,
                "detection_rate": detection_rate,
                "avg_duration": mean(m.duration_seconds for m in cat_metrics),
            }

        return result

    def _analyze_trends(self, metrics: List[ExecutionMetrics]) -> Dict[str, Any]:
        """Analyze trends in execution metrics"""
        if not metrics:
            return {"trend": "insufficient_data"}

        # Success rate trend
        success_counts = [sum(1 for m in metrics if m.success and m.timestamp < m.timestamp)]
        detection_rates = [
            sum(1 for m in metrics if m.detected == DetectionStatus.DETECTED)
            / len(metrics)
        ]

        return {
            "execution_count": len(metrics),
            "avg_duration": mean(m.duration_seconds for m in metrics),
            "success_trend": "stable",  # Simplified
            "detection_trend": "stable",  # Simplified
        }

    def _calculate_detection_accuracy(self, red_metrics: List[ExecutionMetrics]) -> float:
        """Calculate overall detection accuracy"""
        if not red_metrics:
            return 0.0

        correct_detections = sum(
            1 for m in red_metrics if m.detected == DetectionStatus.DETECTED and m.success
        )
        total = len(red_metrics)

        return correct_detections / total if total > 0 else 0.0

    def _prioritize_recommendations(self, gaps: List[DetectionGap]) -> List[str]:
        """Prioritize recommendations based on gap severity and impact"""
        prioritized = []

        for gap in sorted(
            gaps, key=lambda g: (g.severity == GapSeverity.CRITICAL, g.missed_count),
            reverse=True,
        )[:5]:
            prioritized.append(
                f"[{gap.severity.value.upper()}] {gap.technique_name}: "
                f"{gap.missed_count} missed detections"
            )

        return prioritized

    def _generate_executive_summary(
        self, red_success_rate: float, detection_rate: float, gaps: List[DetectionGap]
    ) -> str:
        """Generate executive-level summary"""
        critical_gaps = sum(1 for g in gaps if g.severity == GapSeverity.CRITICAL)

        return (
            f"Red Team success rate: {red_success_rate:.2%} | "
            f"Detection rate: {detection_rate:.2%} | "
            f"Critical gaps: {critical_gaps}"
        )

    def _calculate_priority(self, gap: DetectionGap) -> int:
        """Calculate priority score (1-10) for addressing a gap"""
        severity_score = {
            GapSeverity.CRITICAL: 10,
            GapSeverity.HIGH: 7,
            GapSeverity.MEDIUM: 4,
            GapSeverity.LOW: 1,
        }

        base_score = severity_score.get(gap.severity, 5)
        # Adjust based on missed count
        adjusted_score = min(base_score + (gap.missed_count - 1), 10)

        return int(adjusted_score)

    def _generate_implementation_steps(self, technique_id: str) -> List[str]:
        """Generate specific implementation steps for addressing a gap"""
        return [
            "Review current detection rules",
            "Collect baseline data for comparison",
            "Implement detection enhancement",
            "Test in non-production environment",
            "Deploy to production with monitoring",
            "Validate effectiveness with Red Team",
        ]

    def _predict_trend(self, daily_rates: List[float]) -> float:
        """Predict future rate using simple trend analysis"""
        if len(daily_rates) < 2:
            return daily_rates[-1] if daily_rates else 0.0

        # Simple linear regression
        n = len(daily_rates)
        x = list(range(n))
        y = daily_rates

        x_mean = mean(x)
        y_mean = mean(y)

        slope = sum((x[i] - x_mean) * (y[i] - y_mean) for i in range(n)) / sum(
            (x[i] - x_mean) ** 2 for i in range(n)
        )

        # Project 7 days forward
        predicted = y[-1] + (7 * slope)
        return max(0.0, min(1.0, predicted))

    def _generate_trend_summary(self, daily_rates: List[float], predicted: float) -> str:
        """Generate summary of trend analysis"""
        if not daily_rates:
            return "Insufficient data"

        current = daily_rates[-1]
        direction = "improving" if predicted > current else "degrading"

        return (
            f"Current detection rate: {current:.2%} | "
            f"Predicted in 7 days: {predicted:.2%} | Trend: {direction}"
        )
