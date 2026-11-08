"""Writes contract/schema.json (JSON Schema for every wire type) from the Pydantic models.

    python scripts/export_contract.py          # from backend/

The frontend generates contract/types.ts from this file, so the two sides can never drift.
Author: Saamarth Attray
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.contract import CONTRACT_VERSION, ContractBundle  # noqa: E402

out = Path(__file__).resolve().parents[2] / "contract" / "schema.json"
out.parent.mkdir(exist_ok=True)
schema = ContractBundle.model_json_schema(mode="serialization")
# Tighten for TypeScript: discriminators are always present, objects are closed (no index signatures).
for definition in [schema, *schema.get("$defs", {}).values()]:
    if definition.get("type") == "object":
        definition.setdefault("additionalProperties", False)
        if "type" in definition.get("properties", {}) and "const" in definition["properties"]["type"] or \
           "type" in definition.get("properties", {}) and "enum" in definition["properties"]["type"]:
            required = definition.setdefault("required", [])
            if "type" not in required:
                required.append("type")
schema["title"] = "ContractBundle"
schema["description"] = f"Swarm Dial wire contract v{CONTRACT_VERSION}"
out.write_text(json.dumps(schema, indent=2) + "\n")
print(f"wrote {out} ({len(schema.get('$defs', {}))} definitions)")
