---
id: structured-output-enforcer
file_path: skills/structured-output-enforcer.md
name: Structured Output Enforcer
category: ai-ops
tags: [zod, json-schema, llm-output, validation, typescript]
author: opencode-core
version: 1.0.0
description: Convert unstructured LLM output into validated JSON adhering to strict Zod or JSON Schema rules.
---

# Structured Output Enforcer

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm
- Mandatory packages: `npm i zod` for runtime validation and type inference, or `npm i jsonschema` for pure JSON Schema validation
- Optional: `npm i ai-sdk` or `npm i openai` to integrate with LLM APIs
- TypeScript for type-safe Zod schemas (highly recommended)

## Execution Steps
1. Define a Zod schema (or JSON Schema) that describes the expected output structure: required fields, types, enums, arrays, and nested objects
2. Call the LLM with a prompt that instructs it to output JSON matching the schema (e.g., `Output valid JSON only, matching this schema:...`)
3. Parse the LLM's raw response as JSON (strip markdown fences if needed)
4. Validate the parsed object against the Zod schema using `z.parse(data)` or `schema.safeParse(data)`
5. If validation fails, retry with a refined prompt that includes the error details and schema excerpt
6. On success, return the validated JSON object to the caller; log and discard invalid attempts after N retries
7. Optionally generate TypeScript types from the Zod schema: `z.infer<typeof schema>` for end-to-end type safety

```typescript
// Example: Zod schema for LLM-structured output
import { z } from 'zod';

const UserProfileSchema = z.object({
  name: z.string().min(1, 'Name is required'),
  age: z.number().int().min(13).max(120, 'Age must be between 13 and 120'),
  email: z.string().email('Invalid email address'),
  role: z.enum(['admin', 'user', 'guest'], 'Role must be admin, user, or guest'),
  preferences: z.object({
    theme: z.enum(['light', 'dark', 'system']),
    notifications: z.boolean(),
  }),
});

type UserProfile = z.infer<typeof UserProfileSchema>;

// Simulated LLM output (would come from OpenAI/Anthropic API call)
const rawLLMOutput = `{
  "name": "Alice",
  "age": 30,
  "email": "alice@example.com",
  "role": "user",
  "preferences": {
    "theme": "dark",
    "notifications": true
  }
}`;

try {
  const parsed = UserProfileSchema.parse(JSON.parse(rawLLMOutput));
  console.log('Validated user profile:', parsed);
} catch (error) {
  console.error('Validation errors:', error.errors);
}
```

```bash
npm i zod
npm i -D @types/zod
```