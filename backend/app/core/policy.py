import logging
from enum import Enum
from typing import Dict, Any, Tuple

logger = logging.getLogger(__name__)

class EngagementReadiness(str, Enum):
    PASSIVE = "PASSIVE"
    DEFENSIVE = "DEFENSIVE"
    AGGRESSIVE = "AGGRESSIVE"

class EngagementPolicyEngine:
    """
    Sovereign Hardening: The Safety Interlock (Human-in-the-loop).
    Controls the autonomous lethality of the Unified Intelligence Chain.
    """

    def __init__(self):
        # Default readiness is passive to prevent business continuity disruption
        self.current_readiness: EngagementReadiness = EngagementReadiness.PASSIVE

    def set_readiness(self, level: str) -> None:
        """Dynamically updates the Rules of Engagement from the Situation Room."""
        try:
            self.current_readiness = EngagementReadiness(level.upper())
            logger.critical(f"WEAPON READINESS SHIFT: Rules of Engagement updated to {self.current_readiness.value}")
        except ValueError:
            logger.error(f"Invalid readiness level requested: {level}")

    def evaluate_action(self, proposed_action: str, target_ip: str, is_internal: bool = False) -> Tuple[bool, str]:
        """
        Evaluates whether an autonomous action is permitted under the current ROE.
        Returns Tuple(is_permitted: bool, reasoning: str)
        """
        if self.current_readiness == EngagementReadiness.PASSIVE:
             return False, "ROE is PASSIVE. Action suggested in terminal, but autonomous execution is disabled."
             
        if self.current_readiness == EngagementReadiness.DEFENSIVE:
             if is_internal:
                 return False, "ROE is DEFENSIVE. Target is internal asset; requires Human-in-the-loop permission to isolate."
             else:
                 return True, "ROE is DEFENSIVE. Target is external threat; autonomous isolation permitted."
                 
        if self.current_readiness == EngagementReadiness.AGGRESSIVE:
             return True, "ROE is AGGRESSIVE. Full autonomous containment authorized globally."
             
        return False, "Unknown ROE State. Defaulting to safe (Deny)."

roe_engine = EngagementPolicyEngine()
