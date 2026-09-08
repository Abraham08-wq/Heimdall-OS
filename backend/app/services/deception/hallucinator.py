import logging
from typing import Dict, Any, List
import random
import uuid
import json

from app.core.llm_client import llm_client

logger = logging.getLogger(__name__)

class HallucinationEngine:
    """
    Sovereign Weapon: Deception Engine (Ghost Protocol).
    Uses Generative AI to spin up hyper-realistic, structurally valid but entirely fake
    data sets tailored to an attacker's TTPs within a shadow sandbox.
    """
    
    def __init__(self):
        self._fallback_env_file = f"""
# MOCK PRODUCTION ENVIRONMENT VARIABLES
# DO NOT COMMIT
DEBUG=False
JWT_SECRET_KEY=dj_{uuid.uuid4().hex}
DATABASE_URL=postgres://app_user:s3cr3t_pass_{random.randint(1000,9999)}@10.0.1.55:5432/production
REDIS_URL=redis://10.0.1.60:6379/1
STRIPE_SECRET_KEY=sk_live_{uuid.uuid4().hex[:20]}
AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
        """.strip()
        
        self._fallback_db_records = {
            "users": [
                {
                    "id": i + 1,
                    "email": f"user{random.randint(1000,9999)}@corporate.internal",
                    "password_hash": f"$2y$10${uuid.uuid4().hex[:22]}",
                    "role": "admin" if i == 0 else "user",
                    "mfa_enabled": False
                } for i in range(5)
            ],
            "api_keys": [
                {
                    "id": i + 1,
                    "service": random.choice(["stripe", "twilio", "aws", "sendgrid"]),
                    "key_material": f"live_key_{uuid.uuid4().hex}",
                    "is_active": True
                } for i in range(5)
            ],
            "default": [{"id": i + 1, "data": str(uuid.uuid4()), "status": "processed"} for i in range(5)]
        }

    async def generate_mock_env_file(self, target_ip: str, tenant_id: str) -> str:
        """
        Creates a juicy .env file specifically designed to lure the attacker further in.
        Uses an LLM in production, with a static fallback on failure.
        """
        logger.info(f"[GHOST PROTOCOL] Hallucinating target-specific .env for attacker {target_ip}")

        system_prompt = (
            "You are a security testing assistant. Your task is to generate realistic but entirely fake data for a "
            "simulated environment. Respond only with the requested data artifact, without any surrounding text, "
            "explanations, or markdown formatting."
        )
        user_prompt = (
            "Generate a realistic-looking .env file for a web application. It should include common variables like "
            "JWT_SECRET_KEY, DATABASE_URL, REDIS_URL, and some fake API keys for services like AWS or Stripe."
        )
        
        llm_result = await llm_client.complete(prompt=user_prompt, system=system_prompt)

        if not llm_result or llm_result.startswith("[LLM"):
            logger.warning(f"[GHOST PROTOCOL] LLM generation failed or unavailable ({llm_result}). Using fallback .env file.")
            return self._fallback_env_file + f"\nTENANT_ID={tenant_id}\nCLUSTER_ID=us-east-1-prod-core"

        return llm_result + f"\n\n# DEPLOYMENT\nTENANT_ID={tenant_id}\nCLUSTER_ID=us-east-1-prod-core"

    async def generate_mock_database_records(self, table_name: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Hallucinates SQL/NoSQL rows on the fly.
        Uses an LLM to generate realistic data, with a fallback on failure.
        """
        logger.info(f"[GHOST PROTOCOL] Hallucinating {limit} rows for table '{table_name}'")
        fallback_records = self._fallback_db_records.get(table_name, self._fallback_db_records["default"])

        system_prompt = (
            "You are a security testing assistant. Your task is to generate realistic but entirely fake data for a "
            "simulated environment. Respond ONLY with a valid, minified JSON array of objects. Do not include any "
            "explanations, comments, or markdown formatting."
        )
        user_prompt = f"Generate a JSON array containing {limit} fake records for a database table named '{table_name}'. The records should be plausible for such a table."

        llm_result = await llm_client.complete(prompt=user_prompt, system=system_prompt)

        if not llm_result or llm_result.startswith("[LLM"):
            logger.warning(f"[GHOST PROTOCOL] LLM generation failed for table '{table_name}' ({llm_result}). Using fallback records.")
            return fallback_records[:limit]

        try:
            records = json.loads(llm_result)
            if isinstance(records, list):
                return records
            else:
                logger.error(f"[GHOST PROTOCOL] LLM returned valid JSON, but it was not a list for table '{table_name}'. Using fallback.")
                return fallback_records[:limit]
        except json.JSONDecodeError:
            logger.error(f"[GHOST PROTOCOL] Failed to decode LLM JSON response for table '{table_name}'. Using fallback.")
            return fallback_records[:limit]

    async def spin_up_deception_lattice(self, attacker_ip: str, tenant_id: str) -> Dict[str, Any]:
        """
        Calls all generative primitives to populate a fresh sandbox environment.
        """
        env_file = await self.generate_mock_env_file(attacker_ip, tenant_id)
        mock_users = await self.generate_mock_database_records("users")
        mock_keys = await self.generate_mock_database_records("api_keys")
        
        deception_manifest = {
            "virtual_file_system": {
                "/var/www/app/.env": env_file,
                "/root/.ssh/id_rsa": f"-----BEGIN OPENSSH PRIVATE KEY-----\nb3BlbnNzaC...[TRUNCATED]...\n-----END OPENSSH PRIVATE KEY-----"
            },
            "virtual_database": {
                "users": mock_users,
                "api_keys": mock_keys
            }
        }
        
        logger.warning(f"[GHOST PROTOCOL] Deception Lattice constructed for {attacker_ip}. Ready for eBPF routing.")
        return deception_manifest

hallucination_engine = HallucinationEngine()
