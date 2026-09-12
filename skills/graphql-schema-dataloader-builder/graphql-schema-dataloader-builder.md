---
id: graphql-schema-dataloader-builder
file_path: skills/graphql-schema-dataloader-builder/graphql-schema-dataloader-builder.md
name: GraphQL Schema & DataLoader Builder
category: backend
tags: [graphql, dataloader, apollo-server, schema]
author: opencode-core
version: 1.0.0
description: Designs performance-optimized GraphQL APIs with strict type definitions, clean Query/Mutation resolvers, and batching mechanisms to eliminate N+1 database queries.
---

# GraphQL Schema & DataLoader Builder

## 1. System Architecture & Prerequisites

- Node.js >= 18 LTS (runtime), npm >= 9 (package manager), TypeScript >= 5.5 compiler.
- Runtime deps: `@apollo/server@^4.11.0`, `graphql@^16.9.0`, `dataloader@^2.2.2`.
- Dev deps: `typescript@^5.5.2`, `tsx@^4.16.2`, `@types/node@^20.14.9`.
- The server uses Apollo Server 4's `startStandaloneServer` with an async `context` factory that creates fresh `DataLoader` instances per HTTP request so batched caches never leak across requests or sessions.
- The reference implementation uses an in-memory repository (`db.ts`) to remain fully runnable; swapping in a `pg`/Prisma/Knex repository keeps the loaders and resolvers unchanged.

## 2. Input/Output Data Contracts

### Execution inputs

- GraphQL query/mutation documents over SDL with types `User`, `Post`, `Comment`, interface `Node`, enum `SortOrder`, and `post`/`comment` input objects.
- `context` shape injected into every resolver: `{ loaders: Loaders }` where `Loaders` exposes `usersById`, `postsByAuthorId`, `commentsByPostId`, `commentsByAuthorId`, `postById`, `commentById` (each a `DataLoader<K, V>`).

### N+1 elimination contract

- Resolver fields that resolve related entities (`Post.author`, `Post.comments`, `Comment.author`, `User.posts`) MUST go through a per-request loader, never a raw repository call in a loop.
- Any mutation that writes to a collection served by a loader MUST call `loader.clear(key)` after the write so cached rows stay consistent within the in-flight request.

### Output artifact paths

- `skills/graphql-schema-dataloader-builder/src/schema.ts` (SDL type definitions)
- `skills/graphql-schema-dataloader-builder/src/resolvers.ts` (typed resolvers)
- `skills/graphql-schema-dataloader-builder/src/loaders.ts` (`createLoaders` factory)
- `skills/graphql-schema-dataloader-builder/src/db.ts` (in-memory repository with seed data)
- `skills/graphql-schema-dataloader-builder/src/server.ts` (Apollo Server 4 bootstrap)
- `skills/graphql-schema-dataloader-builder/package.json`, `tsconfig.json`

## 3. Production Reference Implementation

```json
// package.json
{
  "name": "graphql-dataloader-api",
  "version": "1.0.0",
  "private": true,
  "type": "module",
  "scripts": {
    "dev": "tsx watch src/server.ts",
    "start": "tsx src/server.ts"
  },
  "dependencies": {
    "@apollo/server": "^4.11.0",
    "dataloader": "^2.2.2",
    "graphql": "^16.9.0"
  },
  "devDependencies": {
    "@types/node": "^20.14.9",
    "tsx": "^4.16.2",
    "typescript": "^5.5.2"
  }
}
```

```json
// tsconfig.json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "forceConsistentCasingInFileNames": true,
    "types": ["node"],
    "noUnusedLocals": true,
    "noUnusedParameters": false
  },
  "include": ["src/**/*.ts"]
}
```

```typescript
// src/db.ts
export interface User {
  id: string;
  username: string;
  email: string;
  bio: string | null;
}

export interface Post {
  id: string;
  authorId: string;
  title: string;
  body: string;
}

export interface Comment {
  id: string;
  postId: string;
  authorId: string;
  body: string;
  createdAt: string;
}

export const users: User[] = [
  { id: 'user-1', username: 'ada', email: 'ada@example.com', bio: 'First programmable computer pioneer.' },
  { id: 'user-2', username: 'grace', email: 'grace@example.com', bio: null },
  { id: 'user-3', username: 'alan', email: 'alan@example.com', bio: 'Works on formal verification.' }
];

export const posts: Post[] = [
  { id: 'post-1', authorId: 'user-1', title: 'Notes on the Analytical Engine', body: 'A sketch of the first algorithm.' },
  { id: 'post-2', authorId: 'user-1', title: 'On divisors', body: 'Contributions to the mathematical tables.' },
  { id: 'post-3', authorId: 'user-2', title: 'The future of computing', body: 'Stored-program machines and compilers.' },
  { id: 'post-4', authorId: 'user-3', title: 'Universal Turing test', body: 'Decidability and the halting problem.' }
];

export const comments: Comment[] = [
  { id: 'comment-1', postId: 'post-1', authorId: 'user-2', body: 'Groundbreaking for 1843!', createdAt: '2024-01-01T10:00:00Z' },
  { id: 'comment-2', postId: 'post-1', authorId: 'user-3', body: 'I traced the loop table by hand.', createdAt: '2024-01-02T11:30:00Z' },
  { id: 'comment-3', postId: 'post-3', authorId: 'user-1', body: 'COBOL still runs payroll today.', createdAt: '2024-02-01T09:00:00Z' },
  { id: 'comment-4', postId: 'post-4', authorId: 'user-2', body: 'You mean the busy beaver function.', createdAt: '2024-03-05T14:45:00Z' }
];
```

```typescript
// src/loaders.ts
import DataLoader from 'dataloader';
import * as db from './db';

export type Loaders = {
  usersById: DataLoader<string, db.User | null>;
  postsByAuthorId: DataLoader<string, db.Post[]>;
  commentsByPostId: DataLoader<string, db.Comment[]>;
  commentsByAuthorId: DataLoader<string, db.Comment[]>;
  postById: DataLoader<string, db.Post | null>;
  commentById: DataLoader<string, db.Comment | null>;
};

export function createLoaders(): Loaders {
  const usersById = new DataLoader<string, db.User | null>(
    async (ids: readonly string[]): Promise<Array<db.User | null>> =>
      ids.map((id) => db.users.find((u) => u.id === id) ?? null),
    { cache: true }
  );

  const postsByAuthorId = new DataLoader<string, db.Post[]>(
    async (authorIds: readonly string[]): Promise<db.Post[][]> =>
      authorIds.map((authorId) => db.posts.filter((p) => p.authorId === authorId)),
    { cache: true }
  );

  const commentsByPostId = new DataLoader<string, db.Comment[]>(
    async (postIds: readonly string[]): Promise<db.Comment[][]> =>
      postIds.map((postId) => db.comments.filter((c) => c.postId === postId)),
    { cache: true }
  );

  const commentsByAuthorId = new DataLoader<string, db.Comment[]>(
    async (authorIds: readonly string[]): Promise<db.Comment[][]> =>
      authorIds.map((authorId) => db.comments.filter((c) => c.authorId === authorId)),
    { cache: true }
  );

  const postById = new DataLoader<string, db.Post | null>(
    async (ids: readonly string[]): Promise<Array<db.Post | null>> =>
      ids.map((id) => db.posts.find((p) => p.id === id) ?? null),
    { cache: true }
  );

  const commentById = new DataLoader<string, db.Comment | null>(
    async (ids: readonly string[]): Promise<Array<db.Comment | null>> =>
      ids.map((id) => db.comments.find((c) => c.id === id) ?? null),
    { cache: true }
  );

  return { usersById, postsByAuthorId, commentsByPostId, commentsByAuthorId, postById, commentById };
}
```

```typescript
// src/resolvers.ts
import { randomUUID } from 'node:crypto';
import * as db from './db';
import type { Loaders } from './loaders';

export interface ResolverContext {
  loaders: Loaders;
}

interface PostArgs {
  limit?: number;
  sort?: 'ASC' | 'DESC';
}

interface SliceArgs {
  limit?: number;
}

export const resolvers = {
  Node: {
    __resolveType(obj: db.User | db.Post | db.Comment): string {
      if ('username' in obj) return 'User';
      if ('authorId' in obj) return 'Post';
      return 'Comment';
    }
  },

  Query: {
    node: async (_parent: unknown, { id }: { id: string }, ctx: ResolverContext) => {
      const [user, post, comment] = await Promise.all([
        ctx.loaders.usersById.load(id),
        ctx.loaders.postById.load(id),
        ctx.loaders.commentById.load(id)
      ]);
      return user ?? post ?? comment ?? null;
    },
    users: (_parent: unknown, { ids }: { ids: string[] }, ctx: ResolverContext) =>
      ctx.loaders.usersById.loadMany(ids),
    posts: (_parent: unknown, { ids }: { ids: string[] }, ctx: ResolverContext) =>
      ctx.loaders.postById.loadMany(ids),
    user: (_parent: unknown, { id }: { id: string }, ctx: ResolverContext) =>
      ctx.loaders.usersById.load(id),
    post: (_parent: unknown, { id }: { id: string }, ctx: ResolverContext) =>
      ctx.loaders.postById.load(id),
    comment: (_parent: unknown, { id }: { id: string }, ctx: ResolverContext) =>
      ctx.loaders.commentById.load(id)
  },

  User: {
    posts: async (parent: db.User, args: PostArgs, ctx: ResolverContext) => {
      const all = await ctx.loaders.postsByAuthorId.load(parent.id);
      const sorted = [...all].sort((a, b) =>
        args.sort === 'ASC' ? a.id.localeCompare(b.id) : b.id.localeCompare(a.id)
      );
      return sorted.slice(0, args.limit ?? 10);
    },
    comments: (parent: db.User, args: SliceArgs, ctx: ResolverContext) =>
      ctx.loaders.commentsByAuthorId
        .load(parent.id)
        .then((all) => all.slice(0, args.limit ?? 20))
  },

  Post: {
    author: (parent: db.Post, _args: unknown, ctx: ResolverContext) =>
      ctx.loaders.usersById.load(parent.authorId),
    comments: (parent: db.Post, args: SliceArgs, ctx: ResolverContext) =>
      ctx.loaders.commentsByPostId
        .load(parent.id)
        .then((all) => all.slice(0, args.limit ?? 20)),
    commentCount: async (parent: db.Post, _args: unknown, ctx: ResolverContext) =>
      (await ctx.loaders.commentsByPostId.load(parent.id)).length
  },

  Comment: {
    post: (parent: db.Comment, _args: unknown, ctx: ResolverContext) =>
      ctx.loaders.postById.load(parent.postId),
    author: (parent: db.Comment, _args: unknown, ctx: ResolverContext) =>
      ctx.loaders.usersById.load(parent.authorId)
  },

  Mutation: {
    createPost: async (
      _parent: unknown,
      { input }: { input: { title: string; body: string } },
      ctx: ResolverContext
    ) => {
      const post: db.Post = { id: randomUUID(), authorId: 'user-1', title: input.title, body: input.body };
      db.posts.push(post);
      ctx.loaders.postsByAuthorId.clear('user-1');
      return post;
    },
    createComment: async (
      _parent: unknown,
      { input }: { input: { postId: string; body: string } },
      ctx: ResolverContext
    ) => {
      const post = await ctx.loaders.postById.load(input.postId);
      if (!post) throw new Error(`Post ${input.postId} does not exist`);
      const comment: db.Comment = {
        id: randomUUID(),
        postId: input.postId,
        authorId: 'user-2',
        body: input.body,
        createdAt: new Date().toISOString()
      };
      db.comments.push(comment);
      ctx.loaders.commentsByPostId.clear(input.postId);
      ctx.loaders.commentsByAuthorId.clear('user-2');
      return comment;
    }
  }
};
```

```typescript
// src/schema.ts
export const typeDefs = `#graphql
  interface Node {
    id: ID!
  }

  enum SortOrder {
    ASC
    DESC
  }

  type User implements Node {
    id: ID!
    username: String!
    email: String!
    bio: String
    posts(limit: Int = 10, sort: SortOrder = DESC): [Post!]!
    comments(limit: Int = 20): [Comment!]!
  }

  type Post implements Node {
    id: ID!
    author: User!
    title: String!
    body: String!
    comments(limit: Int = 20): [Comment!]!
    commentCount: Int!
  }

  type Comment implements Node {
    id: ID!
    post: Post!
    author: User!
    body: String!
    createdAt: String!
  }

  input PostInput {
    title: String!
    body: String!
  }

  input CommentInput {
    postId: ID!
    body: String!
  }

  type Query {
    node(id: ID!): Node
    users(ids: [ID!]!): [User]!
    posts(ids: [ID!]!): [Post]!
    post(id: ID!): Post
    user(id: ID!): User
    comment(id: ID!): Comment
  }

  type Mutation {
    createPost(input: PostInput!): Post!
    createComment(input: CommentInput!): Comment!
  }
`;
```

```typescript
// src/server.ts
import { ApolloServer } from '@apollo/server';
import { startStandaloneServer } from '@apollo/server/standalone';
import { typeDefs } from './schema';
import { resolvers } from './resolvers';
import { createLoaders } from './loaders';

export const server = new ApolloServer({
  typeDefs,
  resolvers,
  introspection: true
});

const { url } = await startStandaloneServer(server, {
  context: async ({ req }) => ({
    loaders: createLoaders(),
    requestId: typeof req.headers['x-request-id'] === 'string' ? req.headers['x-request-id'] : null
  }),
  listen: { port: 4000 }
});

console.log(`GraphQL server ready at ${url}`);
```

## 4. Execution Protocol & Step-by-Step Workflow

1. Scaffold: create the project directory and copy all files from section 3 (package.json, tsconfig.json, `src/*`).
2. Install: run `npm install`.
3. Run: execute `npm start`; the endpoint is `http://localhost:4000/graphql`.
4. Verify SDL auto-documentation: open `http://localhost:4000/graphql` (Apollo Sandbox) and confirm `User`, `Post`, `Comment`, `Node`, `SortOrder`, `Query`, and `Mutation` appear in the schema reference.
5. Verify N+1 elimination: execute the query below and confirm via server logs/query profiling that all authors resolve in a single batched load and all comment lookups in a second batch (never one query per row).
6. Verify mutations: run `createPost`, then re-query `User.posts` for `user-1` and confirm the new post appears because `postsByAuthorId.clear('user-1')` invalidated the stale cache.
7. Verify interface resolution: query `node(id: "comment-2") { id ... on Comment { body } }` and confirm `__resolveType` routes to `Comment`.

```graphql
query {
  posts(ids: ["post-1", "post-3"]) {
    title
    author { username }
    comments { body author { username } }
  }
}
```

## 5. Edge Cases & Error Handling

- Loaders are created per-request in `context` so user-specific caching and batching never bleed between requests or authenticated sessions.
- `loadMany` preserves the input order even when some ids are missing (`null` entries), keeping positional resolver indices aligned; nullable list items in SDL (`[User]!`) allow graceful nulls.
- Mutations invalidate the affected loader keys (`clear`) immediately after writes; skipping this step leaves stale rows cached for the remainder of the request.
- A resolver error on any nested field is propagated by Apollo into the `errors` array with an `extensions.code` per GraphQL spec; the field resolves to `null` while sibling fields still execute, so a single failed author lookup never fails the whole graph.
- `new Error` in mutations aborts the mutation atomically (no partial writes) and surfaces as a `GRAPHQL_VALIDATION_FAILED`-style client error; production deployments should map it through custom `formatError` to standardized codes such as `BAD_USER_INPUT`.
- If the repository is swapped for a real database, keep batch functions single-query (`WHERE id = ANY($1)` style) — an implementation that loops inside the batch function reintroduces N+1 inside the "batch".
- In multi-instance deployments, per-request in-memory loader caches remain correct by construction; cross-instance cache coherence is out of scope for loaders and must be handled by the repository layer, not by sharing loader instances.