"""
Intelligence Services - Phase 3 Modules

Exports all intelligence engines:
- Neural De-Masking (attacker profiling)
- Linguistic Mesh Translation (payload morphing)
- Digital Twin Snapshots (execution recovery)
- Purple Team Feedback (detection gap analysis)
"""

from .demasking import (
    NeuralDeMaskingEngine,
    ExecutionSignature,
    AttackerProfile,
    TTP,
)

from .translation import (
    LinguisticMeshEngine,
    TranslatedPayload,
    TranslationConfig,
    ObfuscationLevel,
    Language,
)

from .snapshots import (
    DigitalTwinEngine,
    SystemSnapshot,
    SnapshotDiff,
    RecoveryPoint,
)

from .purple_team import (
    PurpleTeamFeedbackEngine,
    PurpleTeamReport,
    DetectionGap,
    DefensiveRecommendation,
)

__all__ = [
    # De-Masking
    "NeuralDeMaskingEngine",
    "ExecutionSignature",
    "AttackerProfile",
    "TTP",
    # Translation
    "LinguisticMeshEngine",
    "TranslatedPayload",
    "TranslationConfig",
    "ObfuscationLevel",
    "Language",
    # Snapshots
    "DigitalTwinEngine",
    "SystemSnapshot",
    "SnapshotDiff",
    "RecoveryPoint",
    # Purple Team
    "PurpleTeamFeedbackEngine",
    "PurpleTeamReport",
    "DetectionGap",
    "DefensiveRecommendation",
]
