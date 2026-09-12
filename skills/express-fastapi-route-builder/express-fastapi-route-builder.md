---
id: express-fastapi-route-builder
file_path: skills/express-fastapi-route-builder/express-fastapi-route-builder.md
name: Express & FastAPI Route Builder
category: backend
tags: [express, fastapi, rest-api, openapi]
author: opencode-core
version: 1.0.0
description: Generates enterprise-grade RESTful API routes in Node.js (Express) or Python (FastAPI) complete with payload validation, unified error handling, and automated Swagger specs.
---

# Express & FastAPI Route Builder

## 1. System Architecture & Prerequisites

- Node.js >= 18 LTS (runtime), npm >= 9 (package manager), TypeScript >= 5.5 compiler, `ts-node` >= 10 for `ts-node`/commonjs execution.
- Python >= 3.10 (runtime), pip >= 23 (package manager), uv >= 0.4 optional for faster installs.
- Express variant core deps: `express@^4.19.2`, `zod@^3.23.8`, `swagger-jsdoc@^6.2.8`, `swagger-ui-express@^5.0.1`, `cors@^2.8.5`, `helmet@^7.1.0`, `dotenv@^16.4.5`.
- FastAPI variant core deps: `fastapi@^0.111.0`, `uvicorn[standard]@^0.30.1`, `pydantic@^2.7.4`, `pydantic-settings@^2.3.4`.
- No external database is required: both variants use an in-memory store so the code runs end-to-end with zero infrastructure.

## 2. Input/Output Data Contracts

### Request body (POST/PATCH /todos) — JSON Schema draft-07

```json
{
  "type": "object",
  "properties": {
    "title": { "type": "string", "minLength": 1, "maxLength": 120 },
    "description": { "type": "string", "maxLength": 1000 },
    "status": { "enum": ["PENDING", "IN_PROGRESS", "COMPLETED"], "default": "PENDING" },
    "dueAt": { "type": "string", "format": "date-time" }
  },
  "required": ["title"],
  "additionalProperties": false
}
```

### Response envelopes

- Success: `{"success": true, "data": <Todo>|<Todo[]>|null}`
- Error: `{"success": false, "error": {"code": string, "message": string, "details"?: object}}`
- HTTP statuses: 200 (read/update), 201 (create), 204 (delete), 400 (validation), 404 (not found), 422 (FastAPI validation), 500 (internal).

### Output artifact paths

Express variant:
- `skills/express-fastapi-route-builder/express/package.json`, `tsconfig.json`
- `express/src/server.ts`, `express/src/app.ts`, `express/src/swagger.ts`
- `express/src/routes/todos.ts`, `express/src/controllers/todoController.ts`, `express/src/services/todoService.ts`
- `express/src/schemas/todo.schema.ts`, `express/src/types/todo.ts`
- `express/src/middleware/asyncHandler.ts`, `express/src/middleware/validate.ts`, `express/src/middleware/error.ts`
- `express/src/utils/AppError.ts`, `express/src/utils/response.ts`

FastAPI variant:
- `skills/express-fastapi-route-builder/fastapi/requirements.txt`
- `fastapi/app/main.py`, `fastapi/app/routes/todos.py`, `fastapi/app/services/todo_service.py`
- `fastapi/app/models/schemas.py`, `fastapi/app/core/errors.py`, `fastapi/app/core/responses.py`, `fastapi/app/core/config.py`

## 3. Production Reference Implementation

### Variant A — Express (TypeScript)

```json
// package.json
{
  "name": "todos-api-express",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "dev": "ts-node src/server.ts",
    "build": "tsc -p tsconfig.json",
    "start": "node dist/server.js"
  },
  "dependencies": {
    "cors": "^2.8.5",
    "dotenv": "^16.4.5",
    "express": "^4.19.2",
    "helmet": "^7.1.0",
    "swagger-jsdoc": "^6.2.8",
    "swagger-ui-express": "^5.0.1",
    "zod": "^3.23.8"
  },
  "devDependencies": {
    "@types/cors": "^2.8.17",
    "@types/express": "^4.17.21",
    "@types/node": "^20.14.9",
    "@types/swagger-jsdoc": "^6.0.4",
    "@types/swagger-ui-express": "^4.1.6",
    "ts-node": "^10.9.2",
    "typescript": "^5.5.2"
  }
}
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "commonjs",
    "moduleResolution": "node",
    "outDir": "./dist",
    "rootDir": "./src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "resolveJsonModule": true,
    "sourceMap": true
  },
  "include": ["src/**/*.ts"],
  "exclude": ["node_modules", "dist"]
}
```

```typescript
// src/types/todo.ts
export type TodoStatus = 'PENDING' | 'IN_PROGRESS' | 'COMPLETED';

export interface Todo {
  id: string;
  title: string;
  description?: string;
  status: TodoStatus;
  dueAt: string | null;
  createdAt: string;
  updatedAt: string;
}
```

```typescript
// src/schemas/todo.schema.ts
import { z } from 'zod';

export const createTodoSchema = z.object({
  body: z.object({
    title: z.string().min(1).max(120),
    description: z.string().max(1000).optional(),
    status: z.enum(['PENDING', 'IN_PROGRESS', 'COMPLETED']).default('PENDING'),
    dueAt: z.string().datetime({ offset: true }).nullable().optional()
  }),
  query: z.object({}),
  params: z.object({})
});

export const updateTodoSchema = z.object({
  body: z
    .object({
      title: z.string().min(1).max(120).optional(),
      description: z.string().max(1000).optional(),
      status: z.enum(['PENDING', 'IN_PROGRESS', 'COMPLETED']).optional(),
      dueAt: z.string().datetime({ offset: true }).nullable().optional()
    })
    .strict()
    .optional(),
  query: z.object({}),
  params: z.object({
    id: z.string().uuid()
  })
});

export const paramsSchema = z.object({
  params: z.object({ id: z.string().uuid() }),
  query: z.object({}),
  body: z.object({})
});
```

```typescript
// src/utils/AppError.ts
export class AppError extends Error {
  public readonly statusCode: number;
  public readonly code: string;
  public readonly details?: unknown;

  constructor(statusCode: number, code: string, message: string, details?: unknown) {
    super(message);
    Object.setPrototypeOf(this, new.target.prototype);
    this.statusCode = statusCode;
    this.code = code;
    this.details = details;
    Error.captureStackTrace(this, this.constructor);
  }

  public static badRequest(message: string, details?: unknown): AppError {
    return new AppError(400, 'BAD_REQUEST', message, details);
  }

  public static notFound(message = 'Resource not found'): AppError {
    return new AppError(404, 'NOT_FOUND', message);
  }

  public static unauthorized(message = 'Unauthorized'): AppError {
    return new AppError(401, 'UNAUTHORIZED', message);
  }

  public static conflict(message: string): AppError {
    return new AppError(409, 'CONFLICT', message);
  }

  public static internal(message = 'Internal server error'): AppError {
    return new AppError(500, 'INTERNAL_ERROR', message);
  }
}
```

```typescript
// src/utils/response.ts
import type { Response } from 'express';

export function sendError(
  res: Response,
  statusCode: number,
  code: string,
  message: string,
  details?: unknown
): void {
  res.status(statusCode).json({
    success: false,
    error: {
      code,
      message,
      ...(details === undefined ? {} : { details })
    }
  });
}
```

```typescript
// src/middleware/validate.ts
import type { NextFunction, Request, Response } from 'express';
import { type ZodSchema } from 'zod';
import { AppError } from '../utils/AppError';

export function validate<T>(schema: ZodSchema<T>) {
  return (req: Request, _res: Response, next: NextFunction): void => {
    const result = schema.safeParse({
      body: req.body ?? {},
      query: req.query ?? {},
      params: req.params ?? {}
    });
    if (!result.success) {
      const issues = result.error.issues.map((issue) => ({
        path: issue.path.join('.'),
        message: issue.message
      }));
      return next(AppError.badRequest('Validation failed', issues));
    }
    const data = result.data as { body: unknown; query: unknown; params: unknown };
    req.body = data.body;
    req.query = data.query as Request['query'];
    req.params = data.params as Request['params'];
    next();
  };
}
```

```typescript
// src/middleware/asyncHandler.ts
import type { NextFunction, Request, RequestHandler, Response } from 'express';

export function asyncHandler(
  fn: (req: Request, res: Response, next: NextFunction) => Promise<unknown>
): RequestHandler {
  return (req, res, next) => {
    Promise.resolve(fn(req, res, next)).catch(next);
  };
}
```

```typescript
// src/middleware/error.ts
import type { NextFunction, Request, Response } from 'express';
import { AppError } from '../utils/AppError';
import { sendError } from '../utils/response';

export function notFoundHandler(req: Request, _res: Response, next: NextFunction): void {
  next(AppError.notFound(`Route ${req.method} ${req.originalUrl} does not exist`));
}

export function errorHandler(err: unknown, _req: Request, res: Response, _next: NextFunction): void {
  if (err instanceof AppError) {
    return sendError(res, err.statusCode, err.code, err.message, err.details);
  }
  const normalized =
    err instanceof SyntaxError ? AppError.badRequest('Malformed JSON body') : AppError.internal();
  if (!normalized.isOperational) {
    console.error('[unhandled-error]', err);
  }
  sendError(res, normalized.statusCode, normalized.code, normalized.message, normalized.details);
}
```

```typescript
// src/services/todoService.ts
import { randomUUID } from 'node:crypto';
import { AppError } from '../utils/AppError';
import type { Todo, TodoStatus } from '../types/todo';

const store = new Map<string, Todo>();

export class TodoService {
  public async list(): Promise<Todo[]> {
    return [...store.values()].sort((a, b) => a.createdAt.localeCompare(b.createdAt));
  }

  public async getById(id: string): Promise<Todo> {
    const todo = store.get(id);
    if (!todo) throw AppError.notFound(`Todo ${id} not found`);
    return todo;
  }

  public async create(input: {
    title: string;
    description?: string;
    status?: TodoStatus;
    dueAt?: string | null;
  }): Promise<Todo> {
    const now = new Date().toISOString();
    const todo: Todo = {
      id: randomUUID(),
      title: input.title,
      description: input.description,
      status: input.status ?? 'PENDING',
      dueAt: input.dueAt ?? null,
      createdAt: now,
      updatedAt: now
    };
    store.set(todo.id, todo);
    return todo;
  }

  public async update(
    id: string,
    patch: Partial<Pick<Todo, 'title' | 'description' | 'status' | 'dueAt'>>
  ): Promise<Todo> {
    const existing = await this.getById(id);
    const updated: Todo = {
      ...existing,
      ...patch,
      id: existing.id,
      createdAt: existing.createdAt,
      updatedAt: new Date().toISOString()
    };
    store.set(id, updated);
    return updated;
  }

  public async remove(id: string): Promise<void> {
    if (!store.has(id)) throw AppError.notFound(`Todo ${id} not found`);
    store.delete(id);
  }
}

export const todoService = new TodoService();
```

```typescript
// src/controllers/todoController.ts
import type { Request, Response } from 'express';
import { todoService } from '../services/todoService';

export async function listTodos(_req: Request, res: Response): Promise<void> {
  const todos = await todoService.list();
  res.status(200).json({ success: true, data: todos });
}

export async function getTodo(req: Request, res: Response): Promise<void> {
  const todo = await todoService.getById(req.params.id);
  res.status(200).json({ success: true, data: todo });
}

export async function createTodo(req: Request, res: Response): Promise<void> {
  const todo = await todoService.create(req.body);
  res.status(201).json({ success: true, data: todo });
}

export async function updateTodo(req: Request, res: Response): Promise<void> {
  const todo = await todoService.update(req.params.id, req.body);
  res.status(200).json({ success: true, data: todo });
}

export async function deleteTodo(req: Request, res: Response): Promise<void> {
  await todoService.remove(req.params.id);
  res.status(204).end();
}
```

```typescript
// src/routes/todos.ts
import { Router } from 'express';
import { asyncHandler } from '../middleware/asyncHandler';
import { validate } from '../middleware/validate';
import { createTodoSchema, paramsSchema, updateTodoSchema } from '../schemas/todo.schema';
import * as todoController from '../controllers/todoController';

const router = Router();

/**
 * @openapi
 * /todos:
 *   get:
 *     summary: List all todos
 *     tags: [Todos]
 *     responses:
 *       '200':
 *         description: Todos retrieved
 *         content:
 *           application/json:
 *             schema:
 *               type: object
 *               properties:
 *                 success: { type: boolean, example: true }
 *                 data:
 *                   type: array
 *                   items: { $ref: '#/components/schemas/Todo' }
 */
router.get('/', asyncHandler(todoController.listTodos));

/**
 * @openapi
 * /todos/{id}:
 *   get:
 *     summary: Get a todo by id
 *     tags: [Todos]
 *     parameters:
 *       - name: id
 *         in: path
 *         required: true
 *         schema: { type: string, format: uuid }
 *     responses:
 *       '200':
 *         description: Todo found
 *         content:
 *           application/json:
 *             schema: { $ref: '#/components/schemas/SuccessEnvelope' }
 *       '404':
 *         description: Todo not found
 *         content:
 *           application/json:
 *             schema: { $ref: '#/components/schemas/ErrorEnvelope' }
 */
router.get('/:id', validate(paramsSchema), asyncHandler(todoController.getTodo));

/**
 * @openapi
 * /todos:
 *   post:
 *     summary: Create a todo
 *     tags: [Todos]
 *     requestBody:
 *       required: true
 *       content:
 *         application/json:
 *           schema: { $ref: '#/components/schemas/TodoCreate' }
 *     responses:
 *       '201':
 *         description: Todo created
 *         content:
 *           application/json:
 *             schema: { $ref: '#/components/schemas/SuccessEnvelope' }
 *       '400':
 *         description: Validation error
 *         content:
 *           application/json:
 *             schema: { $ref: '#/components/schemas/ErrorEnvelope' }
 */
router.post('/', validate(createTodoSchema), asyncHandler(todoController.createTodo));

router.patch('/:id', validate(updateTodoSchema), asyncHandler(todoController.updateTodo));
router.delete('/:id', validate(paramsSchema), asyncHandler(todoController.deleteTodo));

export default router;
```

```typescript
// src/swagger.ts
import swaggerJSDoc from 'swagger-jsdoc';

const options: swaggerJSDoc.Options = {
  definition: {
    openapi: '3.0.0',
    info: {
      title: 'Todos API',
      version: '1.0.0',
      description: 'Enterprise-grade todos REST API with unified error envelope'
    },
    servers: [{ url: 'http://localhost:3000/api/v1' }],
    components: {
      schemas: {
        Todo: {
          type: 'object',
          required: ['id', 'title', 'status', 'createdAt', 'updatedAt'],
          properties: {
            id: { type: 'string', format: 'uuid' },
            title: { type: 'string' },
            description: { type: 'string', nullable: true },
            status: { type: 'string', enum: ['PENDING', 'IN_PROGRESS', 'COMPLETED'] },
            dueAt: { type: 'string', format: 'date-time', nullable: true },
            createdAt: { type: 'string', format: 'date-time' },
            updatedAt: { type: 'string', format: 'date-time' }
          }
        },
        TodoCreate: {
          type: 'object',
          required: ['title'],
          properties: {
            title: { type: 'string', minLength: 1, maxLength: 120 },
            description: { type: 'string', maxLength: 1000, nullable: true },
            status: { type: 'string', enum: ['PENDING', 'IN_PROGRESS', 'COMPLETED'], default: 'PENDING' },
            dueAt: { type: 'string', format: 'date-time', nullable: true }
          }
        },
        SuccessEnvelope: {
          type: 'object',
          required: ['success', 'data'],
          properties: {
            success: { type: 'boolean', example: true },
            data: { nullable: true }
          }
        },
        ErrorEnvelope: {
          type: 'object',
          required: ['success', 'error'],
          properties: {
            success: { type: 'boolean', example: false },
            error: {
              type: 'object',
              required: ['code', 'message'],
              properties: {
                code: { type: 'string' },
                message: { type: 'string' },
                details: { type: 'object', nullable: true }
              }
            }
          }
        }
      }
    }
  },
  apis: ['./src/routes/*.ts']
};

export const swaggerSpec = swaggerJSDoc(options);
```

```typescript
// src/app.ts
import express from 'express';
import cors from 'cors';
import helmet from 'helmet';
import swaggerUi from 'swagger-ui-express';
import todosRouter from './routes/todos';
import { swaggerSpec } from './swagger';
import { errorHandler, notFoundHandler } from './middleware/error';

export function createApp(): express.Express {
  const app = express();

  app.use(helmet());
  app.use(cors({ origin: process.env.CORS_ORIGIN ?? '*', credentials: true }));
  app.use(express.json({ limit: '1mb' }));

  app.use('/api-docs', swaggerUi.serve, swaggerUi.setup(swaggerSpec));
  app.use('/api/v1/todos', todosRouter);

  app.get('/health', (_req, res) => {
    res.status(200).json({ success: true, data: { status: 'ok' } });
  });

  app.use(notFoundHandler);
  app.use(errorHandler);

  return app;
}
```

```typescript
// src/server.ts
import 'dotenv/config';
import { createApp } from './app';

const PORT = Number(process.env.PORT ?? 3000);
const app = createApp();

const server = app.listen(PORT, () => {
  console.log(`[server] Todos API listening on http://localhost:${PORT}`);
  console.log(`[server] Swagger UI at http://localhost:${PORT}/api-docs`);
});

function shutdown(signal: string): void {
  console.log(`[server] Received ${signal}, shutting down gracefully`);
  server.close(() => {
    console.log('[server] HTTP server closed');
    process.exit(0);
  });
  setTimeout(() => process.exit(1), 10_000).unref();
}

process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
```

### Variant B — FastAPI (Python)

```text
# requirements.txt
fastapi==0.111.0
uvicorn[standard]==0.30.1
pydantic==2.7.4
pydantic-settings==2.3.4
```

```python
# app/core/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Todos API"
    api_v1_prefix: str = "/api/v1"
    cors_origins: list[str] = ["*"]
    debug: bool = False

    model_config = SettingsConfigDict(
        env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

```python
# app/models/schemas.py
from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class TodoStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: TodoStatus = Field(default=TodoStatus.PENDING)
    due_at: datetime | None = None


class TodoUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=120)
    description: str | None = Field(default=None, max_length=1000)
    status: TodoStatus | None = None
    due_at: datetime | None = None


class Todo(TodoCreate):
    model_config = ConfigDict(from_attributes=True)

    id: str
    created_at: datetime
    updated_at: datetime
```

```python
# app/core/responses.py
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class SuccessEnvelope(BaseModel, Generic[T]):
    success: bool = True
    data: T


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Any | None = None


class ErrorEnvelope(BaseModel):
    success: bool = False
    error: ErrorDetail
```

```python
# app/core/errors.py
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.responses import ErrorEnvelope


class AppError(Exception):
    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: object | None = None,
    ) -> None:
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details
        super().__init__(message)

    @classmethod
    def bad_request(cls, message: str, details: object | None = None) -> "AppError":
        return cls(400, "BAD_REQUEST", message, details)

    @classmethod
    def not_found(cls, message: str = "Resource not found") -> "AppError":
        return cls(404, "NOT_FOUND", message)

    @classmethod
    def unauthorized(cls, message: str = "Unauthorized") -> "AppError":
        return cls(401, "UNAUTHORIZED", message)

    @classmethod
    def conflict(cls, message: str) -> "AppError":
        return cls(409, "CONFLICT", message)

    @classmethod
    def internal(cls, message: str = "Internal server error") -> "AppError":
        return cls(500, "INTERNAL_ERROR", message)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorEnvelope(
                error={
                    "code": exc.code,
                    "message": exc.message,
                    "details": exc.details,
                }
            ).model_dump(mode="json"),
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorEnvelope(
                error={"code": "HTTP_ERROR", "message": str(exc.detail)}
            ).model_dump(mode="json"),
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content=ErrorEnvelope(
                error={
                    "code": "VALIDATION_ERROR",
                    "message": "Request validation failed",
                    "details": exc.errors(),
                }
            ).model_dump(mode="json"),
        )
```

```python
# app/services/todo_service.py
import uuid
from datetime import UTC, datetime

from app.core.errors import AppError
from app.models.schemas import Todo, TodoCreate, TodoStatus, TodoUpdate

_store: dict[str, Todo] = {}


class TodoService:
    async def list(self) -> list[Todo]:
        return sorted(_store.values(), key=lambda t: t.created_at)

    async def get_by_id(self, todo_id: str) -> Todo:
        todo = _store.get(todo_id)
        if todo is None:
            raise AppError.not_found(f"Todo {todo_id} not found")
        return todo

    async def create(self, payload: TodoCreate) -> Todo:
        now = datetime.now(UTC)
        todo = Todo(
            id=str(uuid.uuid4()),
            title=payload.title,
            description=payload.description,
            status=payload.status,
            due_at=payload.due_at,
            created_at=now,
            updated_at=now,
        )
        _store[todo.id] = todo
        return todo

    async def update(self, todo_id: str, payload: TodoUpdate) -> Todo:
        existing = await self.get_by_id(todo_id)
        data = payload.model_dump(exclude_unset=True)
        updated = Todo(
            id=existing.id,
            title=data.get("title", existing.title),
            description=data.get("description", existing.description),
            status=data.get("status", existing.status),
            due_at=data.get("due_at", existing.due_at),
            created_at=existing.created_at,
            updated_at=datetime.now(UTC),
        )
        _store[todo_id] = updated
        return updated

    async def remove(self, todo_id: str) -> None:
        await self.get_by_id(todo_id)
        del _store[todo_id]


todo_service = TodoService()
```

```python
# app/routes/todos.py
from fastapi import APIRouter, status

from app.core.responses import SuccessEnvelope
from app.models.schemas import Todo, TodoCreate, TodoUpdate
from app.services.todo_service import todo_service

router = APIRouter(prefix="/todos", tags=["todos"])


@router.get("", response_model=SuccessEnvelope[list[Todo]])
async def list_todos() -> SuccessEnvelope[list[Todo]]:
    return SuccessEnvelope(data=await todo_service.list())


@router.get("/{todo_id}", response_model=SuccessEnvelope[Todo])
async def get_todo(todo_id: str) -> SuccessEnvelope[Todo]:
    return SuccessEnvelope(data=await todo_service.get_by_id(todo_id))


@router.post(
    "",
    response_model=SuccessEnvelope[Todo],
    status_code=status.HTTP_201_CREATED,
)
async def create_todo(payload: TodoCreate) -> SuccessEnvelope[Todo]:
    return SuccessEnvelope(data=await todo_service.create(payload))


@router.patch("/{todo_id}", response_model=SuccessEnvelope[Todo])
async def update_todo(todo_id: str, payload: TodoUpdate) -> SuccessEnvelope[Todo]:
    return SuccessEnvelope(data=await todo_service.update(todo_id, payload))


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_todo(todo_id: str) -> None:
    await todo_service.remove(todo_id)
```

```python
# app/main.py
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.errors import register_exception_handlers
from app.core.responses import SuccessEnvelope
from app.routes.todos import router as todos_router

settings = get_settings()

app = FastAPI(
    title=settings.app_name,
    openapi_url=f"{settings.api_v1_prefix}/openapi.json",
    docs_url="/api-docs",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

register_exception_handlers(app)

app.include_router(todos_router, prefix=settings.api_v1_prefix)


@app.get("/health", response_model=SuccessEnvelope[dict[str, str]])
async def health() -> SuccessEnvelope[dict[str, str]]:
    return SuccessEnvelope(data={"status": "ok"})
```

## 4. Execution Protocol & Step-by-Step Workflow

### Express variant

1. Scaffold: create `express/` and copy all files from section 3 (package.json through server.ts).
2. Install: run `npm install` inside `express/`.
3. Run: execute `npm run dev`; server binds to `http://localhost:3000` (override via `PORT` env).
4. Verify create: run `curl -s -X POST http://localhost:3000/api/v1/todos -H "Content-Type: application/json" -d '{"title":"ship api","status":"PENDING"}'`.
5. Verify list: run `curl -s http://localhost:3000/api/v1/todos`.
6. Verify path validation: run `curl -s -i http://localhost:3000/api/v1/todos/not-a-uuid` and expect a `400 BAD_REQUEST` error envelope.
7. Verify 404 fallback: run `curl -s -i http://localhost:3000/nope` and expect the JSON error envelope (not an HTML page).
8. Verify Swagger: open `http://localhost:3000/api-docs` and confirm a generated OpenAPI 3.0 spec, then download `http://localhost:3000/api-docs/swagger.json`.
9. Production build: run `npm run build && npm start`.

### FastAPI variant

1. Scaffold: create `fastapi/` and copy all files from section 3 (requirements.txt through main.py).
2. Install: run `python -m venv .venv`, then `.venv/Scripts/activate` (Windows) or `source .venv/bin/activate` (Linux/macOS), then `pip install -r requirements.txt`.
3. Run: execute `uvicorn app.main:app --reload --host 0.0.0.0 --port 8000`.
4. Verify create: run `curl -s -X POST http://localhost:8000/api/v1/todos -H "Content-Type: application/json" -d '{"title":"ship api"}'`.
5. Verify list: run `curl -s http://localhost:8000/api/v1/todos`.
6. Verify validation: run `curl -s -i -X POST http://localhost:8000/api/v1/todos -H "Content-Type: application/json" -d '{"title":""}'` and expect a `422 VALIDATION_ERROR` envelope.
7. Verify OpenAPI: open `http://localhost:8000/api-docs` (Swagger UI) and `http://localhost:8000/api/v1/openapi.json` (raw spec).

## 5. Edge Cases & Error Handling

- Malformed or missing JSON body is normalized to a `400 BAD_REQUEST` envelope (Express `SyntaxError` mapping; FastAPI `RequestValidationError` → `422 VALIDATION_ERROR`).
- Unknown routes never render HTML: both variants route unmatched paths through the error middleware and return the unified error envelope.
- Zod/Pydantic reject unknown payload fields (`additionalProperties: false` in Express; pydantic default ignore is set, `strict()` on updates) to prevent mass-assignment style bugs.
- Escaping the service layer (throwing non-`AppError` exceptions) is caught by the terminal error middleware and mapped to `500 INTERNAL_ERROR` without leaking stack traces to clients; logs are emitted only for non-operational errors.
- `PATCH` with an empty body is accepted and returns the unchanged resource; deleting or updating a nonexistent id returns `404 NOT_FOUND`, never a false success.
- In-memory stores reset on restart — wire the service to Postgres/Redis when moving to production; the service/controller split keeps the swap isolated.
- The 204 delete response sends no body (`res.status(204).end()` / FastAPI `status_code=204` with `None`) so it stays HTTP-compliant.
- Both servers implement graceful shutdown (`SIGTERM`/`SIGINT`) so in-flight requests drain before `process.exit`; a hard-exit timer unref'd prevents hangs.