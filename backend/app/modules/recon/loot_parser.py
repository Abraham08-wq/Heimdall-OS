import re
import logging
from sqlalchemy.orm import Session
from app.models.models import Loot

logger = logging.getLogger(__name__)

class LootParser:
    """
    Automated extraction of credentials and secrets from raw Operator shell output.
    """
    
    PATTERNS = {
        "AWS_KEY": re.compile(r'\b(AKIA[0-9A-Z]{16})\b'),
        "STRIPE_KEY": re.compile(r'\b((?:sk|rk)_(?:live|test)_[0-9a-zA-Z]{24})\b'),
        "SSH_PRIVATE_KEY": re.compile(
            r'(-----BEGIN (?P<keytype>RSA |OPENSSH |)PRIVATE KEY-----.*?-----END (?P=keytype)PRIVATE KEY-----)',
            re.DOTALL,
        ),
        "GENERIC_PASSWORD": re.compile(r'(?i)\b(?:password|passwd|pwd)\s*[=:]\s*([^\s;\'"]+)')
    }

    @classmethod
    def parse_and_store(cls, context_text: str, db: Session, tenant_id: str = None, operator_id: str = None, source: str = None) -> int:
        """
        Parses context_text, stores extracted matches into the Loot database table.
        Returns the number of looted items found.
        """
        if not context_text:
            return 0
            
        found_items = []
        
        for loot_type, pattern in cls.PATTERNS.items():
            matches = pattern.finditer(context_text)
            for match in matches:
                # the match can be the whole string or the first group if a group is defined
                content = match.group(1) if match.lastindex else match.group(0)
                
                # Check for uniqueness to avoid flooding DB with duplicate parsed keys in a single stroke
                if content not in found_items:
                    found_items.append(content)
                    
                    loot = Loot(
                        tenant_id=tenant_id,
                        operator_id=operator_id,
                        source=source,
                        loot_type=loot_type,
                        content=content
                    )
                    db.add(loot)
                    logger.info(f"🦇 Captured {loot_type} from {source or 'unknown stream'}")
                    
        if found_items:
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"Failed to save parsed Loot: {e}")
                
        return len(found_items)

loot_parser = LootParser()
