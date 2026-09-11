---
id: graphql-schema-designer
name: graphql-schema-designer
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: graphql-schema-designer
file_path: skills/graphql-schema-designer.md
name: GraphQL Schema Designer
category: api
tags: [graphql, schema, type-definitions, resolvers, apollo]
author: opencode-core
version: 1.0.0
description: Design GraphQL type definitions, query/mutation schemas, and resolver boilerplate code.
---

# GraphQL Schema Designer

## Prerequisites & Dependencies
- Node.js 18+ with npm or pnpm
- GraphQL tooling: `npm i graphql` and `npm i -D graphql-cli` for validation
- Optional: `npm i @apollo/server` for Node 16+ server setup, or `npm i express-graphql` for Express integration
- Text editor with GraphQL schema syntax highlighting

## Execution Steps
1. Define the root-level schema using SDL (Schema Definition Language): type `Query`, `Mutation`, and custom types
2. Create scalar types or enums for constrained domains (e.g., `Status: PENDING | ACTIVE | ARCHIVED`)
3. Design `Query` type with fields that fetch single records or lists, using arguments for filtering/pagination
4. Design `Mutation` type for create, update, and delete operations, specifying input types via `input` blocks
4. Write resolver skeleton code that delegates to data sources (databases, APIs, in-memory stores)
5. Add pagination support using `connection` pattern or `first/last` + `after/before` cursor arguments
6. Validate the schema: `graphql schema validate schema.graphql` or integrate with Apollo Studio
7. Generate resolver boilerplate and wire it to the Apollo Server or Express middleware

```graphql
# schema.graphql
type Query {
  hello: String
  user(id: ID!): User
  posts(
    first: Int
    after: String
  ): PostConnection
}

type Mutation {
  createPost(input: CreatePostInput!): Post
  updatePostStatus(id: ID!, status: Status!): Post
}

input CreatePostInput {
  title: String!
  content: String!
  published: Boolean
}

type User {
  id: ID!
  name: String!
  email: String!
  posts: [Post!]!
}

type Post {
  id: ID!
  title: String!
  content: String
  published: Boolean!
  author: User!
}

enum Status {
  PENDING
  ACTIVE
  ARCHIVED
}

type PostConnection {
  totalCount: Int!
  edges: [PostEdge!]!
  pageInfo: PageInfo!
}

type PostEdge {
  cursor: String!
  node: Post!
}

type PageInfo {
  hasNextPage: Boolean!
  hasPreviousPage: Boolean!
  startCursor: String
  endCursor: String
}
```

```javascript
// resolver skeleton (Node.js with @apollo/server)
const { ApolloServer } = require('@apollo/server');
const { startServerAndCreateHandler } = require('@apollo/server/express4');

const startApolloServer = async () => {
  const server = new ApolloServer({
    typeDefs: './schema.graphql',
    resolvers: {
      Query: {
        hello: () => 'World',
        user: async (_, { id }) => { /* fetch from DB */ },
        posts: async (_, { first, after }) => { /* fetch with pagination */ },
      },
      Mutation: {
        createPost: async (_, { input }) => { /* create and return post */ },
      },
    },
  });

  await startServerAndCreateHandler(server).then((handler) => {
    const express = require('express');
    const app = express();
    app.use('/graphql', handler);
    app.listen(4000, () => console.log('🚀 Server ready at http://localhost:4000/graphql'));
  });
};

startApolloServer();
```