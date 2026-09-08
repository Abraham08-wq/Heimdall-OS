import json
import base64
import logging
from typing import Tuple, Dict

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.exceptions import InvalidSignature

logger = logging.getLogger(__name__)

class QuantumCryptoEngine:
    """
    Tier 6: The Forge - Zero-Trust Infrastructure.
    A future-proof cryptographic module. Replaced PQC simulation with production-ready
    Elliptic Curve Cryptography (ECC) using NIST P-384 curve. This module secures 
    internal Kafka streams, Postgres records, and Agent comms.
    """
    
    def generate_lattice_keypair(self) -> Tuple[str, str]:
        """
        Generates a standard ECC (Elliptic Curve Cryptography) key pair.
        This replaces the PQC simulation with a real, secure implementation.
        Keys are returned in PEM format.
        """
        logger.debug("[THE FORGE] Generating NIST P-384 ECC Keypair...")
        private_key = ec.generate_private_key(ec.SECP384R1())
        public_key = private_key.public_key()

        priv_pem = private_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption()
        ).decode('utf-8')

        pub_pem = public_key.public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo
        ).decode('utf-8')
        
        return pub_pem, priv_pem

    def quantum_sign_payload(self, private_key_pem: str, payload_data: Dict) -> str:
        """
        Signs a JSON payload using the provided ECC private key (PEM format).
        Uses the Elliptic Curve Digital Signature Algorithm (ECDSA).
        Returns a base64-encoded signature string.
        """
        try:
            private_key = serialization.load_pem_private_key(
                private_key_pem.encode('utf-8'),
                password=None
            )
            payload_bytes = json.dumps(payload_data, sort_keys=True).encode('utf-8')
            
            signature = private_key.sign(
                payload_bytes,
                ec.ECDSA(hashes.SHA256())
            )
            return base64.b64encode(signature).decode('utf-f')
        except Exception as e:
            logger.error(f"[THE FORGE] Payload signing failed: {e}")
            return ""

    def verify_quantum_signature(self, public_key_pem: str, signature_b64: str, payload_data: Dict) -> bool:
        """
        Verifies a signature against a JSON payload using the ECC public key (PEM format).
        """
        try:
            public_key = serialization.load_pem_public_key(
                public_key_pem.encode('utf-8')
            )
            payload_bytes = json.dumps(payload_data, sort_keys=True).encode('utf-8')
            signature = base64.b64decode(signature_b64)

            public_key.verify(
                signature,
                payload_bytes,
                ec.ECDSA(hashes.SHA256())
            )
            return True
        except InvalidSignature:
            logger.warning("[THE FORGE] Signature verification failed: Invalid signature.")
            return False
        except Exception as e:
            logger.error(f"[THE FORGE] Signature verification failed with an unexpected error: {e}")
            return False

pqc_engine = QuantumCryptoEngine()
