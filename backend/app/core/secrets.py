import os
import asyncio
from typing import Dict, Optional

import json

class SecretManager:
    """In-memory secret manager that fetches secrets from a cloud secrets provider.

    By default attempts AWS Secrets Manager via boto3. All secrets are kept in memory
    and never written to disk. Falls back to environment variables when
    ENVIRONMENT=development.
    """

    def __init__(self, provider: str = 'aws', aws_region: Optional[str] = None):
        self.provider = provider
        self.aws_region = aws_region or os.getenv('AWS_REGION')
        self._secrets: Dict[str, str] = {}

    async def load(self) -> Dict[str, str]:
        env = os.getenv('ENVIRONMENT', 'development')
        if env == 'development':
            # In development, read from env vars as fallback
            self._secrets = {
                'DATABASE_URL': os.getenv('DATABASE_URL', ''),
                'NEO4J_PASSWORD': os.getenv('NEO4J_PASSWORD', ''),
                'JWT_SECRET_KEY': os.getenv('JWT_SECRET_KEY', ''),
            }
            return self._secrets

        if self.provider == 'aws':
            # Use boto3 synchronously inside a thread to avoid blocking event loop
            try:
                import boto3

                def _fetch():
                    client = boto3.client('secretsmanager', region_name=self.aws_region)
                    # secret names expected in env or defaults
                    mapping = {
                        'DATABASE_URL': os.getenv('SECRETS_DATABASE_URL', 'projectxy/database'),
                        'NEO4J_PASSWORD': os.getenv('SECRETS_NEO4J_PASSWORD', 'projectxy/neo4j'),
                        'JWT_SECRET_KEY': os.getenv('SECRETS_JWT_SECRET', 'projectxy/jwt'),
                    }
                    out = {}
                    for k, name in mapping.items():
                        try:
                            resp = client.get_secret_value(SecretId=name)
                            secret = resp.get('SecretString')
                            if secret:
                                try:
                                    parsed = json.loads(secret)
                                    # adopt common keys
                                    out[k] = parsed.get(k) or parsed.get(k.lower()) or parsed
                                    if isinstance(out[k], dict):
                                        out[k] = json.dumps(out[k])
                                except Exception:
                                    out[k] = secret
                            else:
                                out[k] = ''
                        except Exception:
                            out[k] = ''

                    return out

                result = await asyncio.to_thread(_fetch)
                # sanitize and set
                for kk, vv in result.items():
                    if isinstance(vv, (dict, list)):
                        self._secrets[kk] = json.dumps(vv)
                    else:
                        self._secrets[kk] = vv or ''

                return self._secrets
            except Exception:
                # fallback to env if provider failed
                self._secrets = {
                    'DATABASE_URL': os.getenv('DATABASE_URL', ''),
                    'NEO4J_PASSWORD': os.getenv('NEO4J_PASSWORD', ''),
                    'JWT_SECRET_KEY': os.getenv('JWT_SECRET_KEY', ''),
                }
                return self._secrets

        # Generic fallback
        self._secrets = {
            'DATABASE_URL': os.getenv('DATABASE_URL', ''),
            'NEO4J_PASSWORD': os.getenv('NEO4J_PASSWORD', ''),
            'JWT_SECRET_KEY': os.getenv('JWT_SECRET_KEY', ''),
        }
        return self._secrets

    def get(self, key: str) -> Optional[str]:
        return self._secrets.get(key)
