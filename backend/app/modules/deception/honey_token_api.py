import hmac
import hashlib
from typing import Dict, Any
from datetime import datetime, timedelta
from app.core.config import settings

class HoneyTokenGenerator:
    """
    Tier 1: Proactive Deception.
    Generates weaponized 'Honey-Tokens' (fake credentials, AWS keys, documents).
    When an adversary uses a token, it dials our FastAPI backend, revealing their infrastructure.
    """
    
    def __init__(self):
        # A master secret key used to cryptographically sign our honey-tokens.
        # This ensures we only respond to our *own* tokens being triggered, preventing alert fatigue.
        self.master_secret = settings.JWT_SECRET_KEY.encode('utf-8')

    def generate_aws_style_token(self, campaign_name: str, target_profile: str) -> Dict[str, str]:
        """
        Generates a fake AWS Access Key ID and Secret Access Key.
        The ID is structured to perfectly resemble a real AWS key, but contains encoded tracking data.
        """
        # Formulate the tracking payload
        payload = f"{campaign_name}:{target_profile}:{int(datetime.utcnow().timestamp())}"
        
        # Sign the payload (HMAC-SHA256)
        signature = hmac.new(self.master_secret, payload.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # Construct the fake AWS keys
        # We prefix with 'AKIA' as it's the standard AWS Access Key starting sequence
        access_key_id = f"AKIA{signature[:16].upper()}" 
        
        # We embed the actual tracking payload in the secret key so we can decode it when they attempt to use it
        import base64
        encoded_payload = base64.b64encode(payload.encode('utf-8')).decode('utf-8')
        secret_access_key = f"{encoded_payload}.{signature[16:40]}"
        
        return {
            "type": "AWS_CREDENTIALS",
            "campaign": campaign_name,
            "access_key_id": access_key_id,
            "secret_access_key": secret_access_key,
            "instructions": "Place these in a standard ~/.aws/credentials file within the Labyrinth."
        }

    def generate_document_beacon(self, file_name: str, target_adversary: str) -> str:
        """
        Generates a 1-pixel tracking image URL to embed inside a Word/PDF document.
        When the adversary opens the stolen document on their local machine, it dials home.
        """
        payload = f"DOC:{file_name}:{target_adversary}"
        signature = hmac.new(self.master_secret, payload.encode('utf-8'), hashlib.sha256).hexdigest()
        
        # Create a unique, signed webhook URL
        base_url = str(settings.FRONTEND_URL).rstrip("/")
        webhook_url = f"{base_url}/api/v1/ingest/beacon/{payload}?sig={signature[:16]}"
        return webhook_url

honey_token_ops = HoneyTokenGenerator()
