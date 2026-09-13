---
name: OpenAPI Spec Writer
description: Extract backend API code into OpenAPI/Swagger 3.0 documentation.
metadata:
  source: skills/openapi-spec-writer/openapi-spec-writer.md
---

# OpenAPI Spec Writer

## Prerequisites & Dependencies
- Read access to the backend source: router/controller + validation/schema annotations
- Node 18+ with `npm i -g @redocly/cli` or `@stoplight/spectral-cli` for lint/preview
- Framework-generated annotations (FastAPI, NestJS, SpringDoc) as ground-truth DTO references if available

## Execution Steps
1. Inventory all routes: HTTP method, path (convert framework placeholders to `{param}`), assigned tags, and auth requirements from middleware/decorators.
2. Extract request contracts: path/query/header parameters, request body schema, content types — read from validators or DTOs, never guess.
3. Extract response contracts: status codes, response shapes, error envelope structure; promote reused models to `components/schemas`.
4. Document auth under `components/securitySchemes` and indicate global vs per-operation security requirements.
5. Assemble `openapi.yaml` (3.0.3) with `info`, `servers` (dev/staging/prod), consistent `operationId`s, and full path/item documentation.
6. Lint and fix: `spectral lint openapi.yaml`; preview with `redocly preview-docs` and verify all operations render correctly.

```yaml
openapi: 3.0.3
info: { title: Orders API, version: 1.2.0 }
servers: [{ url: https://api.example.com/v1 }]
paths:
  /orders/{id}:
    get:
      operationId: getOrder
      tags: [orders]
      security: [{ bearerAuth: [] }]
      parameters:
        - { name: id, in: path, required: true, schema: { type: string, format: uuid } }
      responses:
        "200": { description: OK, content: { application/json: { schema: { $ref: "#/components/schemas/Order" } } } }
        "404": { $ref: "#/components/responses/NotFound" }
components:
  securitySchemes: { bearerAuth: { type: http, scheme: bearer, bearerFormat: JWT } }
  schemas:
    Order:
      type: object
      required: [id, status]
      properties: { id: { type: string, format: uuid }, status: { type: string, enum: [open, paid, shipped] } }
```

```bash
spectral lint openapi.yaml
redocly preview-docs openapi.yaml
```
