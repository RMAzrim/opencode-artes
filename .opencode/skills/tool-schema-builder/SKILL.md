---
name: Tool Schema Builder
description: Convert standard code functions into JSON schema format for AI function calling.
metadata:
  source: skills/tool-schema-builder/tool-schema-builder.md
---

# Tool Schema Builder

## Prerequisites & Dependencies
- Python 3.10+ with `inspect` / Node 18+ for runtime introspection (JSDoc, TypeScript `reflect-metadata`)
- Optional converters: `pip install pydantic docstring-parser` or `npm i zod zod-to-json-schema`
- No API keys required; optionally a model endpoint for a smoke-test call

## Execution Steps
1. Extract the function name, signature (parameter names, types, defaults), and docstring summary/description.
2. Map language types to JSON Schema: `str→string`, `int/float→number|integer`, `bool→boolean`, `list→array`, `dict/TypedDict→object`, `Optional[X]` excluded from `required`.
3. Encode constraints: enums, min/max values, patterns; add a one-line action-oriented description with units and expected format for each parameter.
4. Wrap in the provider's tool-calling envelope: `"type": "function"`, `"function": { "name": "...", "description": "...", "parameters": { ... } }` with `$schema: https://json-schema.org/draft/07/schema` and `additionalProperties: false`.
5. Validate the generated schema against JSON Schema meta-schema; round-trip a sample payload to verify completeness.
6. Wire the dispatcher: parse model tool call, validate arguments against the schema, and invoke the underlying function with typed validation errors on mismatch.

```python
from pydantic import BaseModel, Field, TypeAdapter

def get_weather(city: str, units: str = "celsius") -> dict:
    """Return the current weather for a city."""

class GetWeather(BaseModel):
    """Return the current weather for a city."""
    city: str = Field(description="City name, e.g. 'Berlin'")
    units: str = Field(default="celsius", pattern="^(celsius|fahrenheit)$")

tool = {
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": GetWeather.__doc__,
        "parameters": TypeAdapter(GetWeather).json_schema(),
    },
}
```
