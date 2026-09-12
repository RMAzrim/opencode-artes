---
id: type-definition-generator
file_path: skills/type-definition-generator/type-definition-generator.md
name: Type Definition Generator
category: core-coding
tags: [typescript, type-definitions, python, json-schema, static-typing]
author: opencode-core
version: 1.0.0
description: Convert untyped JavaScript, Python dicts, or raw JSON payloads into strict TypeScript interfaces or Type Hint annotations.
---

# Type Definition Generator

## Prerequisites & Dependencies
- Node.js 18+ or Python 3.10+
- `npm i -g quicktype` or `pip install pydantic mypy` for code generation
- Sample untyped JSON payloads or Python dicts to generate types from
- Optional: `npm i ajv` for JSON Schema validation, `pip install marshmallow` for Python

## Execution Steps
1. Collect a representative set of JSON examples (ideally 10–20) covering all branches, nulls, nested objects, and arrays
2. Run a code generator:
   - **Quicktype**: `quicktype input.json -l typescript` → produces `.d.ts` interfaces with JSON Schema annotations
   - **Pydantic/Marshmallow**: `python generate.py` → produces `class User(BaseModel): ...` or schema fields
3. Review the generated types for correctness: verify union types, required/optional markers, enum values
4. Apply the types in the project: import interfaces in TypeScript, use Pydantic models in Python APIs
5. Run type checking: `npx tsc --noEmit` or `mypy pipeline.py` to catch mismatches early
6. Iterate: add more JSON samples or adjust generator flags (`--enum-as-string`, `--just-types`) until the output matches the project's typing style

```bash
# Quicktype: generate TypeScript interfaces from JSON
quicktype src/payloads/user.json -l typescript -o src/types/user.d.ts

# Pydantic example: from dict to typed model
from pydantic import BaseModel, EmailStr

class User(BaseModel):
    id: int
    name: str
    email: EmailStr
    is_active: bool = True

user = User(**{"id": 1, "name": "Alice", "email": "alice@example.com"})
```