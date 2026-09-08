import os
import shutil
import re
from pathlib import Path

backend_dir = Path("/home/bantu/Documents/ProjectXY/backend/app")

relocations = {
    "modules/defensive/services/threat_intel.py": "modules/intelligence/threat_intel.py",
    "modules/defensive/services/ai_scorer.py": "modules/defensive_ai/ai_scorer.py",
    "modules/defensive/services/ai_defense.py": "modules/defensive_ai/ai_defense.py",
    "modules/defensive/services/deception.py": "modules/deception/deception.py",
    "modules/defensive/services/zero_trust.py": "modules/zero_trust/zero_trust.py"
}

# 1. Move the files
print("Moving files...")
for src_rel, dest_rel in relocations.items():
    src_path = backend_dir / src_rel
    dest_path = backend_dir / dest_rel
    if src_path.exists():
        dest_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src_path, dest_path)
        print(f"Moved {src_rel} to {dest_rel}")
    else:
        print(f"WARNING: Source {src_rel} not found.")

# 2. Update imports globally in Python files
import_replacements = {
    "app.modules.defensive.services.threat_intel": "app.modules.intelligence.threat_intel",
    "app.modules.defensive.services.ai_scorer": "app.modules.defensive_ai.ai_scorer",
    "app.modules.defensive.services.ai_defense": "app.modules.defensive_ai.ai_defense",
    "app.modules.defensive.services.deception": "app.modules.deception.deception",
    "app.modules.defensive.services.zero_trust": "app.modules.zero_trust.zero_trust",
}

print("Refactoring imports...")
for py_file in backend_dir.rglob("*.py"):
    with open(py_file, "r") as f:
        content = f.read()

    modified = False
    for old_import, new_import in import_replacements.items():
        if old_import in content:
            content = content.replace(old_import, new_import)
            modified = True

    if modified:
        with open(py_file, "w") as f:
            f.write(content)
        print(f"Updated imports in {py_file.name}")

print("Refactoring complete.")
