---
name: Next.js App Router Scaffolder
description: Automatically scaffolds production-ready Next.js App Router directory structures, isolating React Server Components (RSC) from Client Components, configuring standardized layout boundaries, error handlers, and loading states.
metadata:
  source: skills/nextjs-app-router-scaffolder/nextjs-app-router-scaffolder.md
---

# Next.js App Router Scaffolder

## 1. System Architecture & Prerequisites
- Runtime: Node.js >= 20.11.0 (LTS). The App Router requires a modern JS runtime for `next dev`, `next build`, and `next start`; edge/middleware run on the Next.js edge runtime.
- Package manager: any of npm >= 10, pnpm >= 9, yarn >= 4, or bun >= 1.1. All commands below use npm.
- Runtime dependencies: `next@15.1.6`, `react@19.0.0`, `react-dom@19.0.0`, `zod@^3.24.1`.
- Dev dependencies: `typescript@^5.7.3`, `@types/node@^22.10.7`, `@types/react@^19.0.7`, `@types/react-dom@^19.0.3`.
- Architecture rules enforced by this blueprint:
  - Server Components own the page tree and data access. Files without a `"use client"` directive are RSC and run only on the server.
  - The client boundary is explicit: only files under `app/components/` that declare `"use client"` render interactivity.
  - Server Actions live in `app/actions/` and always respond with the `ServerActionResponse<T>` discriminated union so any caller can switch on `ok`.
  - `generateMetadata` is exported as a typed async function following the Next.js Metadata API.
- Definition of done: every file type-checks with `tsc --noEmit` and builds with `next build` with zero warnings.

## 2. Input/Output Data Contracts
JSON Schema for the scaffolder input parameters:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "projectRoot": { "type": "string", "minLength": 1 },
    "packageManager": { "enum": ["npm", "pnpm", "yarn", "bun"] },
    "typescript": { "type": "boolean", "default": true },
    "font": { "type": "string", "default": "Inter" },
    "defaultLocale": { "type": "string", "default": "en-US" }
  },
  "required": ["projectRoot"]
}
```

Output artifacts (exact paths):
- `package.json`, `tsconfig.json`
- `app/layout.tsx` (metadata title template, Inter font, `lang="en-US"`)
- `app/page.tsx` (RSC page with typed `generateMetadata` + server action call)
- `app/error.tsx` (client error boundary), `app/loading.tsx` (fallback), `app/not-found.tsx` (404 UI)
- `app/globals.css` (design tokens + reset)
- `app/actions/schema.ts` (zod schemas + `ServerActionResponse<T>` type)
- `app/actions/user.ts` (`"use server"` actions)
- `app/components/UserForm.tsx` (client boundary)
- `next-env.d.ts` (regenerated automatically by the first `next dev` or `next build`)

Server Action response contract (discriminated union, consumed by the client):

```ts
type ServerActionResponse<T> =
  | { ok: true; data: T }
  | { ok: false; error: { message: string; code: string; fieldErrors?: Record<string, string[]> } };
```

## 3. Production Reference Implementation
One complete, self-contained implementation. Every file below is final and runnable:

```
# =========================================================
# FILE: package.json
# =========================================================
{
  "name": "next-app-router-scaffold",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "next": "15.1.6",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "zod": "^3.24.1"
  },
  "devDependencies": {
    "@types/node": "^22.10.7",
    "@types/react": "^19.0.7",
    "@types/react-dom": "^19.0.3",
    "typescript": "^5.7.3"
  }
}

# =========================================================
# FILE: tsconfig.json
# =========================================================
{
  "compilerOptions": {
    "target": "ES2017",
    "lib": ["dom", "dom.iterable", "esnext"],
    "allowJs": true,
    "skipLibCheck": true,
    "strict": true,
    "noEmit": true,
    "esModuleInterop": true,
    "module": "esnext",
    "moduleResolution": "bundler",
    "resolveJsonModule": true,
    "isolatedModules": true,
    "jsx": "preserve",
    "incremental": true,
    "plugins": [{ "name": "next" }],
    "paths": { "@/*": ["./*"] }
  },
  "include": ["next-env.d.ts", "**/*.ts", "**/*.tsx", ".next/types/**/*.ts"],
  "exclude": ["node_modules"]
}

# =========================================================
# FILE: app/layout.tsx
# =========================================================
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter"
});

export const metadata: Metadata = {
  title: {
    default: "Scaffold",
    template: "%s | Scaffold"
  },
  description: "Production-ready Next.js App Router scaffold",
  robots: { index: true, follow: true }
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en-US">
      <body className={`${inter.variable} font-sans antialiased`}>{children}</body>
    </html>
  );
}

# =========================================================
# FILE: app/page.tsx
# =========================================================
import type { Metadata } from "next";
import { createUser, listUsers } from "./actions/user";
import { UserForm } from "./components/UserForm";

export async function generateMetadata(): Promise<Metadata> {
  return {
    title: "User Directory",
    description: "Lists users and demonstrates a type-safe create-user server action."
  };
}

export default async function HomePage() {
  const result = await listUsers();

  if (!result.ok) {
    return (
      <main className="mx-auto max-w-2xl p-8">
        <h1>User Directory</h1>
        <p role="alert">{result.error.message}</p>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-2xl space-y-8 p-8">
      <h1>User Directory</h1>
      <UserForm action={createUser} />
      <section aria-labelledby="users-heading">
        <h2 id="users-heading">Registered users</h2>
        <ul>
          {result.data.map((user) => (
            <li key={user.id}>
              {user.name} - {user.email} (age {user.age})
            </li>
          ))}
        </ul>
      </section>
    </main>
  );
}

# =========================================================
# FILE: app/error.tsx
# =========================================================
"use client";

import { useEffect } from "react";

type ErrorBoundaryProps = {
  error: Error & { digest?: string };
  reset: () => void;
};

export default function GlobalErrorBoundary({ error, reset }: ErrorBoundaryProps) {
  useEffect(() => {
    console.error("App router error boundary caught:", error);
  }, [error]);

  return (
    <main role="alert" className="mx-auto max-w-xl space-y-4 p-8">
      <h2>Something went wrong</h2>
      <p>{error.message}</p>
      <button type="button" onClick={() => reset()}>
        Try again
      </button>
    </main>
  );
}

# =========================================================
# FILE: app/loading.tsx
# =========================================================
export default function Loading() {
  return <p role="status">Loading...</p>;
}

# =========================================================
# FILE: app/not-found.tsx
# =========================================================
import Link from "next/link";

export default function NotFound() {
  return (
    <main className="mx-auto max-w-xl space-y-4 p-8">
      <p className="text-lg font-semibold">404</p>
      <h1>Page not found</h1>
      <p>The page you are looking for does not exist or has been moved.</p>
      <Link href="/">Back to home</Link>
    </main>
  );
}

# =========================================================
# FILE: app/globals.css
# =========================================================
:root {
  --background: #ffffff;
  --foreground: #171717;
  --font-inter: "Inter", system-ui, sans-serif;
}

@media (prefers-color-scheme: dark) {
  :root {
    --background: #0a0a0a;
    --foreground: #ededed;
  }
}

html,
body {
  max-width: 100vw;
  min-height: 100vh;
  overflow-x: hidden;
  margin: 0;
}

body {
  background: var(--background);
  color: var(--foreground);
  font-family: var(--font-inter);
  -webkit-font-smoothing: antialiased;
}

button {
  cursor: pointer;
}

[role="alert"] {
  color: #ef4444;
}

# =========================================================
# FILE: app/actions/schema.ts
# =========================================================
import { z } from "zod";

export const ACTION_ERROR_CODES = {
  validation: "VALIDATION_ERROR",
  conflict: "RESOURCE_CONFLICT",
  notFound: "RESOURCE_NOT_FOUND",
  internal: "INTERNAL_ERROR"
} as const;

export type ActionErrorCode = (typeof ACTION_ERROR_CODES)[keyof typeof ACTION_ERROR_CODES];

export type ServerActionResponse<T> =
  | { ok: true; data: T }
  | {
      ok: false;
      error: {
        message: string;
        code: ActionErrorCode;
        fieldErrors?: Record<string, string[]>;
      };
    };

export const createUserSchema = z.object({
  name: z.string().trim().min(2, "Name must be at least 2 characters").max(80, "Name is too long"),
  email: z.string().trim().max(254).email("A valid email is required"),
  age: z.coerce.number().int("Age must be a whole number").min(18, "You must be at least 18").max(120, "Age is out of range")
});

export type CreateUserInput = z.infer<typeof createUserSchema>;

# =========================================================
# FILE: app/actions/user.ts
# =========================================================
"use server";

import {
  ACTION_ERROR_CODES,
  createUserSchema,
  type CreateUserInput,
  type ServerActionResponse
} from "./schema";

type StoredUser = { id: string; name: string; email: string; age: number };

const users: StoredUser[] = [
  { id: crypto.randomUUID(), name: "Ada Lovelace", email: "ada@example.com", age: 36 }
];

export async function createUser(
  input: CreateUserInput
): Promise<ServerActionResponse<{ id: string }>> {
  const parsed = createUserSchema.safeParse(input);
  if (!parsed.success) {
    const fieldErrors: Record<string, string[]> = {};
    for (const [key, messages] of Object.entries(parsed.error.flatten().fieldErrors)) {
      if (messages && messages.length > 0) {
        fieldErrors[key] = messages;
      }
    }
    return {
      ok: false,
      error: {
        message: "One or more fields are invalid.",
        code: ACTION_ERROR_CODES.validation,
        fieldErrors
      }
    };
  }

  const { name, email, age } = parsed.data;

  if (users.some((user) => user.email.toLowerCase() === email.toLowerCase())) {
    return {
      ok: false,
      error: {
        message: "A user with this email already exists.",
        code: ACTION_ERROR_CODES.conflict
      }
    };
  }

  const user: StoredUser = { id: crypto.randomUUID(), name, email, age };
  users.push(user);

  return { ok: true, data: { id: user.id } };
}

export async function listUsers(): Promise<ServerActionResponse<StoredUser[]>> {
  return { ok: true, data: users };
}

export async function getUserById(id: string): Promise<ServerActionResponse<StoredUser>> {
  const user = users.find((candidate) => candidate.id === id);
  if (!user) {
    return {
      ok: false,
      error: { message: "User not found.", code: ACTION_ERROR_CODES.notFound }
    };
  }
  return { ok: true, data: user };
}

# =========================================================
# FILE: app/components/UserForm.tsx
# =========================================================
"use client";

import type { FormEvent } from "react";
import { useState } from "react";
import type { CreateUserInput, ServerActionResponse } from "../actions/schema";

type UserFormProps = {
  action: (input: CreateUserInput) => Promise<ServerActionResponse<{ id: string }>>;
};

export function UserForm({ action }: UserFormProps) {
  const [pending, setPending] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<Record<string, string[]>>({});
  const [createdId, setCreatedId] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const formData = new FormData(event.currentTarget);
    const input: CreateUserInput = {
      name: String(formData.get("name") ?? ""),
      email: String(formData.get("email") ?? ""),
      age: Number(formData.get("age") ?? 0)
    };

    setPending(true);
    setFormError(null);
    setFieldErrors({});
    setCreatedId(null);

    try {
      const response = await action(input);
      if (!response.ok) {
        setFormError(response.error.message);
        setFieldErrors(response.error.fieldErrors ?? {});
        return;
      }
      setCreatedId(response.data.id);
      event.currentTarget.reset();
    } finally {
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4" noValidate>
      <h2>Create user</h2>

      <p>
        <label htmlFor="name">Name</label>
        <input id="name" name="name" minLength={2} required />
      </p>
      <p>
        <label htmlFor="email">Email</label>
        <input id="email" name="email" type="email" required />
      </p>
      <p>
        <label htmlFor="age">Age</label>
        <input id="age" name="age" type="number" min={18} max={120} required />
      </p>

      <button type="submit" disabled={pending}>
        {pending ? "Creating..." : "Create user"}
      </button>

      {formError ? <p role="alert">{formError}</p> : null}
      {createdId ? <p>Created user with id {createdId}</p> : null}
      {Object.entries(fieldErrors).map(([field, messages]) => (
        <p key={field} role="alert">
          {field}: {messages.join(", ")}
        </p>
      ))}
    </form>
  );
}
```

## 4. Execution Protocol & Step-by-Step Workflow
```bash
# 1. Verify the toolchain
node --version            # must be >= 20.11.0
npm --version             # must be >= 10

# 2. Create the project root
mkdir next-app-router-scaffold
cd next-app-router-scaffold

# 3. Write package.json and tsconfig.json, then install dependencies
npm install

# 4. Scaffold the app/ tree:
#    app/layout.tsx, app/page.tsx, app/error.tsx,
#    app/loading.tsx, app/not-found.tsx, app/globals.css

# 5. Scaffold the server-action layer:
#    app/actions/schema.ts, app/actions/user.ts

# 6. Scaffold the client boundary:
#    app/components/UserForm.tsx

# 7. Type-check the full project
npm run typecheck

# 8. Production build (generates next-env.d.ts and .next/)
npm run build

# 9. Smoke-test interactively
npm run dev
#    Open http://localhost:3000 -> page renders, form submits against createUser.
#    Open http://localhost:3000/this-does-not-exist -> not-found.tsx renders.
```

## 5. Edge Cases & Error Handling
- Unsupported Node < 20.11.0: fail fast with a clear error message and instruct the user to install the LTS via nvm/fnm. Never transpile around the runtime requirement.
- Missing `next-env.d.ts`: it is generated by the first `next dev` or `next build`. Run `npm run build` once before `npm run typecheck` to avoid spurious TS failures.
- `"use server"` placement: it must be the literal first directive of `app/actions/user.ts`. Imports, comments, or whitespace above it disable the server boundary at build time.
- `crypto.randomUUID()` requires a secure context and Node >= 19. On legacy runtimes, fall back to `crypto.randomBytes(16).toString("hex")` behind a feature detection check.
- Cross-boundary exceptions: server actions must return the `{ ok: false, error }` discriminated union instead of throwing; an unhandled throw surfaces as an opaque 500 to the client and bypasses field-level rendering.
- Security: treat every server action as an unauthenticated entry point. Re-validate all input server-side with zod even if the client already validated, and explicitly deduplicate email lookups before inserting.
- Rollback: the scaffold is deterministic. On any failed step, delete the generated tree and re-run from step 4.
