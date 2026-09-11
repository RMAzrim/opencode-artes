---
id: error-class-hierarchy-builder
name: error-class-hierarchy-builder
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: error-class-hierarchy-builder
file_path: skills/error-class-hierarchy-builder.md
name: Error Class Hierarchy Builder
category: core-coding
tags: [error-handling, custom-exceptions, hierarchy, typescript]
author: opencode-core
version: 1.0.0
description: Create domain-specific custom exception classes with standardized error codes, HTTP statuses, and metadata payloads.
---

# Error Class Hierarchy Builder

## Prerequisites & Dependencies
- Node.js 18+ or Python 3.10+, TypeScript strongly preferred
- Understanding of try/catch blocks and error propagation
- Optional: `npm i @types/node` for TS, or built-in `http`/`status` codes

## Execution Steps
1. Define a base custom error class that captures domain-wide concerns: `errorCode`, `httpStatus`, `metadata` (retry-after, correlation ID, etc.)
2. Extend the hierarchy for specific domains: validation errors, authentication failures, not-found resources, server errors
3. Standardize the constructor signature: `new AppError(message, httpStatus, metadata)` across all subclasses
4. Add helper methods: `isOperational`, `sendDev`, `sendProd` (different error output for dev vs prod)
5. Use the hierarchy consistently across the codebase, replacing generic `try/catch` with typed catches
6. Document the error taxonomy and ensure all team members throw/customize errors using the same pattern

```typescript
// Base AppError with code, status, and metadata
class AppError extends Error {
  public readonly errorCode: string;
  public readonly httpStatus: number;
  public readonly metadata: Record<string, unknown>;

  constructor(message: string, httpStatus = 500, metadata: Record<string, unknown> = {}) {
    super(message);
    this.name = 'AppError';
    this.errorCode = metadata.code || 'UNKNOWN_ERROR';
    this.httpStatus = httpStatus;
    this.metadata = metadata;
    Error.captureStackTrace(this, this.constructor);
  }
}

// Domain-specific subclasses
class ValidationError extends AppError {
  constructor(message: string, metadata?: Record<string, unknown>) {
    super(message, 400, metadata || { code: 'VALIDATION_ERROR' });
  }
}

class NotFoundError extends AppError {
  constructor(resource: string, id: string, metadata?: Record<string, unknown>) {
    super(` ${resource} with id ${id} not found`, 404, metadata || { code: 'NOT_FOUND' });
  }
}

// Usage in an Express handler
app.get('/users/:id', async (req, res, next) => {
  try {
    const user = await db.findById(req.params.id);
    if (!user) throw new NotFoundError('User', req.params.id);
    res.json(user);
  } catch (err) {
    next(err); // centralized error handler formats response
  }
});
```