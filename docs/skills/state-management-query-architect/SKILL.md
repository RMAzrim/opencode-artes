---
name: State Management & Query Architect
description: Establishes a clean separation between global client UI state and asynchronous server state management using Zustand and TanStack Query (React Query).
metadata:
  source: skills/state-management-query-architect/state-management-query-architect.md
---

# State Management & Query Architect

## 1. System Architecture & Prerequisites
- Runtime: Node.js >= 20.11.0, npm >= 10.
- Framework: Next.js 15.1.6 with React 19. TanStack Query and Zustand are renderer-agnostic; the compiled direction here is Next.js App Router.
- Dependencies: `@tanstack/react-query@^5.66.0`, `zustand@^5.0.3`, `next@15.1.6`, `react@19.0.0`, `react-dom@19.0.0`.
- Dev dependencies: `typescript@^5.7.3`, `@types/react@^19.0.7`, `@types/react-dom@^19.0.3`, `@types/node@^22.10.7`.
- Architecture rules enforced by this blueprint:
  - Zustand owns ephemeral, cross-component client UI state (auth session, theme, cart) and persists it through the `persist` middleware with `createJSONStorage(() => localStorage)`.
  - TanStack Query owns all asynchronous server state. No fetched data is ever copied into a Zustand store.
  - Server mutations are optimistic: snapshot the cache in `onMutate`, roll back in `onError`, and invalidate the query key in `onSettled`.
  - A single `QueryClient` is created lazily inside `QueryProvider` (per-hydration, not per-render) with production `defaultOptions`: `staleTime: 30_000`, `gcTime: 5 * 60_000`, `retry: 2`.

## 2. Input/Output Data Contracts
JSON Schema for the store and query configuration inputs:

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "additionalProperties": false,
  "properties": {
    "persistStores": {
      "type": "array",
      "items": { "enum": ["auth", "theme", "cart"] },
      "default": ["auth", "theme", "cart"]
    },
    "queryDefaultOptions": {
      "type": "object",
      "properties": {
        "staleTimeMs": { "type": "integer", "default": 30000 },
        "gcTimeMs": { "type": "integer", "default": 300000 },
        "retry": { "type": "integer", "default": 2 }
      }
    },
    "apiBaseUrl": { "type": "string", "format": "uri" }
  },
  "required": ["persistStores"]
}
```

Output artifacts (exact paths):
- `stores/authStore.ts`, `stores/themeStore.ts`, `stores/cartStore.ts` (Zustand stores + selectors)
- `providers/QueryProvider.tsx` (QueryClientProvider wrapper)
- `hooks/useTodos.ts` (query factory + optimistic mutations)
- `app/api/todos/route.ts` (in-memory REST endpoints the hooks call)
- `components/TodoApp.tsx` (consumer wiring both layers)
- `app/layout.tsx`, `app/page.tsx`, `package.json`

Domain types shared across the contracts:

```ts
type Todo = { id: string; title: string; done: boolean; createdAt: string };
type CreateTodoInput = { title: string };
type CartItem = { productId: string; name: string; quantity: number; unitPrice: number };
```

## 3. Production Reference Implementation
One complete, self-contained implementation. Every file is final and runnable:

```
# =========================================================
# FILE: package.json
# =========================================================
{
  "name": "state-query-architect",
  "version": "0.1.0",
  "private": true,
  "scripts": {
    "dev": "next dev",
    "build": "next build",
    "start": "next start",
    "typecheck": "tsc --noEmit"
  },
  "dependencies": {
    "@tanstack/react-query": "^5.66.0",
    "next": "15.1.6",
    "react": "19.0.0",
    "react-dom": "19.0.0",
    "zustand": "^5.0.3"
  },
  "devDependencies": {
    "@types/node": "^22.10.7",
    "@types/react": "^19.0.7",
    "@types/react-dom": "^19.0.3",
    "typescript": "^5.7.3"
  }
}

# =========================================================
# FILE: stores/authStore.ts
# =========================================================
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type AuthUser = { id: string; email: string; name: string };

type AuthState = {
  user: AuthUser | null;
  token: string | null;
  status: "idle" | "authenticating" | "authenticated" | "error";
  signIn: (credentials: { email: string; password: string }) => Promise<void>;
  signOut: () => void;
};

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      status: "idle",
      signIn: async (credentials) => {
        set({ status: "authenticating" });
        try {
          const response = await fetch("/api/auth/sign-in", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(credentials)
          });
          if (!response.ok) {
            throw new Error("Invalid credentials");
          }
          const user = (await response.json()) as AuthUser;
          set({ user, token: "issued-at-sign-in", status: "authenticated" });
        } catch {
          set({ user: null, token: null, status: "error" });
        }
      },
      signOut: () => set({ user: null, token: null, status: "idle" })
    }),
    {
      name: "auth-store",
      storage: createJSONStorage(() => localStorage),
      partialize: (state) => ({ user: state.user, token: state.token })
    }
  )
);

# =========================================================
# FILE: stores/themeStore.ts
# =========================================================
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type Theme = "light" | "dark" | "system";

type ThemeState = {
  theme: Theme;
  setTheme: (theme: Theme) => void;
};

export const useThemeStore = create<ThemeState>()(
  persist(
    (set) => ({
      theme: "system",
      setTheme: (theme) => set({ theme })
    }),
    {
      name: "theme-store",
      storage: createJSONStorage(() => localStorage)
    }
  )
);

# =========================================================
# FILE: stores/cartStore.ts
# =========================================================
import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";

export type CartItem = { productId: string; name: string; quantity: number; unitPrice: number };

type CartState = {
  items: CartItem[];
  addItem: (item: CartItem) => void;
  removeItem: (productId: string) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  clear: () => void;
};

export const useCartStore = create<CartState>()(
  persist(
    (set) => ({
      items: [],
      addItem: (item) =>
        set((state) => {
          const existing = state.items.find((candidate) => candidate.productId === item.productId);
          if (existing) {
            return {
              items: state.items.map((candidate) =>
                candidate.productId === item.productId
                  ? { ...candidate, quantity: candidate.quantity + item.quantity }
                  : candidate
              )
            };
          }
          return { items: [...state.items, item] };
        }),
      removeItem: (productId) =>
        set((state) => ({ items: state.items.filter((item) => item.productId !== productId) })),
      updateQuantity: (productId, quantity) =>
        set((state) => ({
          items:
            quantity <= 0
              ? state.items.filter((item) => item.productId !== productId)
              : state.items.map((item) =>
                  item.productId === productId ? { ...item, quantity } : item
                )
        })),
      clear: () => set({ items: [] })
    }),
    {
      name: "cart-store",
      storage: createJSONStorage(() => localStorage),
      version: 1
    }
  )
);

export function selectCartCount(state: CartState): number {
  return state.items.reduce((sum, item) => sum + item.quantity, 0);
}

export function selectCartTotal(state: CartState): number {
  return state.items.reduce((sum, item) => sum + item.quantity * item.unitPrice, 0);
}

# =========================================================
# FILE: providers/QueryProvider.tsx
# =========================================================
"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

export function QueryProvider({ children }: { children: ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 30_000,
            gcTime: 5 * 60_000,
            retry: 2,
            refetchOnWindowFocus: false
          },
          mutations: {
            retry: 0
          }
        }
      })
  );

  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

# =========================================================
# FILE: hooks/useTodos.ts
# =========================================================
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export type Todo = { id: string; title: string; done: boolean; createdAt: string };
export type CreateTodoInput = { title: string };

const todoKeys = {
  all: ["todos"] as const
};

export const todoApi = {
  async list(): Promise<Todo[]> {
    const response = await fetch("/api/todos");
    if (!response.ok) {
      throw new Error("Failed to load todos: " + response.status);
    }
    return response.json() as Promise<Todo[]>;
  },
  async create(input: CreateTodoInput): Promise<Todo> {
    const response = await fetch("/api/todos", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(input)
    });
    if (!response.ok) {
      throw new Error("Failed to create todo: " + response.status);
    }
    return response.json() as Promise<Todo>;
  },
  async toggle(id: string): Promise<Todo> {
    const response = await fetch("/api/todos", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ id })
    });
    if (!response.ok) {
      throw new Error("Failed to toggle todo: " + response.status);
    }
    return response.json() as Promise<Todo>;
  }
};

export function useTodos() {
  return useQuery({
    queryKey: todoKeys.all,
    queryFn: todoApi.list
  });
}

export function useCreateTodo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: todoApi.create,
    onMutate: async (input) => {
      await queryClient.cancelQueries({ queryKey: todoKeys.all });
      const previous = queryClient.getQueryData<Todo[]>(todoKeys.all);
      const optimistic: Todo = {
        id: "temp-" + Date.now(),
        title: input.title,
        done: false,
        createdAt: new Date().toISOString()
      };
      queryClient.setQueryData<Todo[]>(todoKeys.all, (old) => [optimistic, ...(old ?? [])]);
      return { previous };
    },
    onError: (_error, _input, context) => {
      if (context?.previous) {
        queryClient.setQueryData<Todo[]>(todoKeys.all, context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: todoKeys.all });
    }
  });
}

export function useToggleTodo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: todoApi.toggle,
    onMutate: async (id: string) => {
      await queryClient.cancelQueries({ queryKey: todoKeys.all });
      const previous = queryClient.getQueryData<Todo[]>(todoKeys.all);
      queryClient.setQueryData<Todo[]>(todoKeys.all, (old) =>
        (old ?? []).map((todo) => (todo.id === id ? { ...todo, done: !todo.done } : todo))
      );
      return { previous };
    },
    onError: (_error, _id, context) => {
      if (context?.previous) {
        queryClient.setQueryData<Todo[]>(todoKeys.all, context.previous);
      }
    },
    onSettled: () => {
      void queryClient.invalidateQueries({ queryKey: todoKeys.all });
    }
  });
}

# =========================================================
# FILE: app/api/todos/route.ts
# =========================================================
import { NextResponse } from "next/server";

type ApiTodo = { id: string; title: string; done: boolean; createdAt: string };

const todos: ApiTodo[] = [];

export async function GET() {
  return NextResponse.json(todos);
}

export async function POST(request: Request) {
  const body = (await request.json()) as Partial<ApiTodo>;
  const title = typeof body.title === "string" ? body.title.trim() : "";
  if (!title) {
    return NextResponse.json({ message: "title is required" }, { status: 400 });
  }
  const todo: ApiTodo = {
    id: crypto.randomUUID(),
    title,
    done: false,
    createdAt: new Date().toISOString()
  };
  todos.push(todo);
  return NextResponse.json(todo, { status: 201 });
}

export async function PATCH(request: Request) {
  const body = (await request.json()) as { id: string };
  const todo = todos.find((candidate) => candidate.id === body.id);
  if (!todo) {
    return NextResponse.json({ message: "not found" }, { status: 404 });
  }
  todo.done = !todo.done;
  return NextResponse.json(todo);
}

# =========================================================
# FILE: components/TodoApp.tsx
# =========================================================
"use client";

import { useState, type FormEvent } from "react";
import { useAuthStore } from "../stores/authStore";
import { selectCartCount, selectCartTotal, useCartStore } from "../stores/cartStore";
import { useCreateTodo, useTodos, useToggleTodo } from "../hooks/useTodos";

export function TodoApp() {
  const [draft, setDraft] = useState("");
  const { data: todos, isLoading, isError, error } = useTodos();
  const createTodo = useCreateTodo();
  const toggleTodo = useToggleTodo();
  const user = useAuthStore((state) => state.user);
  const cartCount = useCartStore(selectCartCount);
  const cartTotal = useCartStore(selectCartTotal);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const title = draft.trim();
    if (!title) {
      return;
    }
    createTodo.mutate({ title });
    setDraft("");
  }

  return (
    <section className="mx-auto max-w-xl p-6">
      <header className="flex items-center justify-between">
        <h1 className="text-xl font-bold">Todos</h1>
        <div className="text-sm">
          <span>{user ? "Hello " + user.name : "Signed out"}</span>
          <span aria-hidden="true"> | </span>
          <span>Cart {cartCount} items - ${cartTotal.toFixed(2)}</span>
        </div>
      </header>

      <form onSubmit={handleSubmit} className="mt-4 flex gap-2">
        <input
          value={draft}
          onChange={(event) => setDraft(event.target.value)}
          placeholder="Add a todo..."
          className="flex-1 rounded-md border px-3 py-2"
        />
        <button
          type="submit"
          disabled={createTodo.isPending}
          className="rounded-md bg-indigo-600 px-4 py-2 text-white disabled:opacity-60"
        >
          {createTodo.isPending ? "Saving..." : "Add"}
        </button>
      </form>

      {isLoading ? <p role="status">Loading todos...</p> : null}
      {isError ? <p role="alert">Failed to load: {error?.message}</p> : null}

      <ul className="mt-4 space-y-2">
        {(todos ?? []).map((todo) => (
          <li key={todo.id} className="flex items-center gap-3 rounded-md border px-3 py-2">
            <input
              type="checkbox"
              checked={todo.done}
              onChange={() => toggleTodo.mutate(todo.id)}
              aria-label={'Mark "' + todo.title + '" ' + (todo.done ? "not" : "") + " done"}
            />
            <span className={todo.done ? "line-through opacity-60" : ""}>{todo.title}</span>
          </li>
        ))}
      </ul>
    </section>
  );
}

# =========================================================
# FILE: app/layout.tsx
# =========================================================
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { QueryProvider } from "../providers/QueryProvider";

export const metadata: Metadata = {
  title: "State & Query Architect",
  description: "Zustand client state and TanStack Query server state"
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}

# =========================================================
# FILE: app/page.tsx
# =========================================================
import { TodoApp } from "../components/TodoApp";

export default function HomePage() {
  return <TodoApp />;
}
```

## 4. Execution Protocol & Step-by-Step Workflow
```bash
# 1. Scaffold the project and install dependencies
mkdir state-query-architect
cd state-query-architect
npm install

# 2. Write the Zustand stores (auth, theme, cart) with persist middleware
# 3. Write providers/QueryProvider.tsx wrapping the app in QueryClientProvider
# 4. Write hooks/useTodos.ts (query factory + optimistic mutations)
# 5. Write app/api/todos/route.ts backing endpoints
# 6. Write components/TodoApp.tsx consuming both layers
# 7. Wire app/layout.tsx + app/page.tsx

# 8. Type-check and build
npm run typecheck
npm run build

# 9. Runtime verification
npm run dev
curl -s -X POST http://localhost:3000/api/todos \
  -H "Content-Type: application/json" -d '{"title":"Buy milk"}'
#    Open http://localhost:3000: the todo appears optimistically (temp-id),
#    the server confirms it after PATCH/invalidate, and the cart counter
#    persists across a full page reload (localStorage).
```

## 5. Edge Cases & Error Handling
- SSR with `localStorage`: `createJSONStorage(() => localStorage)` catches the missing-global error internally and returns a disabled storage, so hydration never throws on the server. Never read the hydrated store synchronously during render; expose it through selectors after mount.
- Stale optimistic data: `onMutate` must first `cancelQueries` on the key so an in-flight refetch cannot overwrite the snapshot; `onSettled` invalidates even when there is no error.
- Failed mutation rollback: if `previous` is undefined (first fetch still pending), skip `setQueryData`; do not tamper with the key.
- Persist version drift (cart `version: 1`): bump the version and provide a `migrate` function when the shape changes; otherwise legacy payloads deserialize into `undefined` items.
- 404/5xx from the API: `retry: 2` + `refetchOnWindowFocus: false` limits silent retry storms; the route handler sets explicit status codes so hooks surface readable messages.
- Query identity: always use the shared `todoKeys.all` object in query keys, mutation `onMutate`, and `invalidateQueries`; never inline a fresh array literal in more than one place or invalidation diverges.
- Rollback: the reference API (`/api/todos`) is in-memory; restarting the dev server resets the dataset. Point `todoApi` at a real backend without touching the store or hook contracts.
