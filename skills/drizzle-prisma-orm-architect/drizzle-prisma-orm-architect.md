---
id: drizzle-prisma-orm-architect
file_path: skills/drizzle-prisma-orm-architect/drizzle-prisma-orm-architect.md
name: Drizzle & Prisma ORM Architect
category: database
tags: [drizzle, prisma, postgresql, migrations]
author: opencode-core
version: 1.0.0
description: Architect relational database schemas, model complex entity relationships, optimize query execution, and generate zero-downtime database migration files.
---

# Drizzle & Prisma ORM Architect

## 1. System Architecture & Prerequisites

This skill covers end-to-end PostgreSQL schema design and ORM layer implementation using **Prisma** and **Drizzle ORM** side-by-side on the same e-commerce domain model. The architecture enforces:

- **1:1** User → UserProfile
- **1:N** Category → Products, User → Orders, User → Reviews, Order → OrderItems
- **M:N** Product ↔ Category via Prisma implicit many-to-many and Drizzle manual junction table
- **Soft-delete** via `deletedAt` column with automatic filtering middleware
- **Composite indexes** for high-throughput query patterns

**Prerequisites:**

- Node.js ≥ 18
- PostgreSQL 14+
- `prisma` CLI (`npm i -D prisma`)
- `drizzle-kit` CLI (`npm i -D drizzle-kit`)
- `drizzle-orm` runtime (`npm i drizzle-orm`)

## 2. Input/Output Data Contracts

**Input — Environment Variables:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["DATABASE_URL"],
  "properties": {
    "DATABASE_URL": {
      "type": "string",
      "description": "PostgreSQL connection string",
      "pattern": "^postgresql://"
    }
  }
}
```

**Output Artifacts:**

| Path | Description |
|---|---|
| `prisma/schema.prisma` | Prisma schema definition |
| `prisma/migrations/` | Auto-generated Prisma migration SQL |
| `src/drizzle/schema.ts` | Drizzle table definitions |
| `src/drizzle/migrations/` | Auto-generated Drizzle migration SQL |
| `drizzle.config.ts` | Drizzle Kit configuration |
| `src/lib/prisma-client.ts` | Prisma client singleton + soft-delete middleware |
| `src/lib/drizzle-client.ts` | Drizzle client + helper utilities |
| `src/repositories/prisma-repo.ts` | Prisma CRUD repository |
| `src/repositories/drizzle-repo.ts` | Drizzle CRUD repository |

## 3. Production Reference Implementation

### 3A — Prisma Variant

```prisma
// prisma/schema.prisma
generator client {
  provider = "prisma-client-js"
}

datasource db {
  provider = "postgresql"
  url      = env("DATABASE_URL")
}

model User {
  id        String   @id @default(cuid())
  email     String   @unique
  name      String
  role      Role     @default(CUSTOMER)
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  deletedAt DateTime?

  profile   UserProfile?
  orders    Order[]
  reviews   Review[]
  cartItems CartItem[]

  @@index([email])
  @@index([role])
  @@map("users")
}

model UserProfile {
  id        String  @id @default(cuid())
  userId    String  @unique
  avatar    String?
  bio       String?
  phone     String?
  address   Json?

  user User @relation(fields: [userId], references: [id], onDelete: Cascade)

  @@map("user_profiles")
}

model Category {
  id        String   @id @default(cuid())
  name      String   @unique
  slug      String   @unique
  parentId  String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  deletedAt DateTime?

  parent   Category?  @relation("CategoryTree", fields: [parentId], references: [id])
  children Category[] @relation("CategoryTree")
  products Product[]

  @@index([parentId])
  @@index([slug])
  @@map("categories")
}

model Product {
  id          String   @id @default(cuid())
  name        String
  slug        String   @unique
  description String?
  price       Decimal  @db.Decimal(10, 2)
  sku         String   @unique
  stock       Int      @default(0)
  isActive    Boolean  @default(true)
  createdAt   DateTime @default(now())
  updatedAt   DateTime @updatedAt
  deletedAt   DateTime?

  categoryIds String[]
  categories  Category[]
  orderItems  OrderItem[]
  cartItems   CartItem[]
  reviews     Review[]

  @@index([sku])
  @@index([slug])
  @@index([isActive, price])
  @@map("products")
}

model Order {
  id          String      @id @default(cuid())
  userId      String
  status      OrderStatus @default(PENDING)
  total       Decimal     @db.Decimal(10, 2)
  createdAt   DateTime    @default(now())
  updatedAt   DateTime    @updatedAt
  deletedAt   DateTime?

  user  User        @relation(fields: [userId], references: [id])
  items OrderItem[]

  @@index([userId, status])
  @@index([createdAt])
  @@map("orders")
}

model OrderItem {
  id        String  @id @default(cuid())
  orderId   String
  productId String
  quantity  Int
  unitPrice Decimal @db.Decimal(10, 2)

  order   Order   @relation(fields: [orderId], references: [id], onDelete: Cascade)
  product Product @relation(fields: [productId], references: [id])

  @@index([orderId])
  @@index([productId])
  @@map("order_items")
}

model Review {
  id        String   @id @default(cuid())
  userId    String
  productId String
  rating    Int
  title     String?
  body      String?
  createdAt DateTime @default(now())
  updatedAt DateTime @updatedAt
  deletedAt DateTime?

  user    User    @relation(fields: [userId], references: [id])
  product Product @relation(fields: [productId], references: [id])

  @@unique([userId, productId])
  @@index([productId, rating])
  @@map("reviews")
}

model CartItem {
  id        String  @id @default(cuid())
  userId    String
  productId String
  quantity  Int     @default(1)

  user    User    @relation(fields: [userId], references: [id], onDelete: Cascade)
  product Product @relation(fields: [productId], references: [id])

  @@unique([userId, productId])
  @@map("cart_items")
}

enum Role {
  CUSTOMER
  ADMIN
  VENDOR
}

enum OrderStatus {
  PENDING
  CONFIRMED
  SHIPPED
  DELIVERED
  CANCELLED
}
```

```typescript
// src/lib/prisma-client.ts
import { PrismaClient, Prisma } from "@prisma/client";

const globalForPrisma = globalThis as unknown as { prisma: PrismaClient };

function createPrismaClient(): PrismaClient {
  const client = new PrismaClient({
    log:
      process.env.NODE_ENV === "development"
        ? ["query", "error", "warn"]
        : ["error"],
  });

  // Soft-delete middleware: automatically filters out deleted records
  client.$use(async (params, next) => {
    const skipPaths = ["$connect", "$disconnect", "$transaction"];

    if (skipPaths.includes(params.action)) {
      return next(params);
    }

    const modelName = params.model ?? "";

    if (params.action === "findFirst" || params.action === "findMany" || params.action === "count" || params.action === "aggregate") {
      params.args.where = {
        ...params.args.where,
        deletedAt: null,
      };
    }

    if (params.action === "findUnique") {
      params.action = "findFirst";
      params.args.where = {
        ...params.args.where,
        deletedAt: null,
      };
    }

    if (params.action === "update") {
      params.action = "updateMany";
      params.args.where = {
        ...params.args.where,
        deletedAt: null,
      };
    }

    if (params.action === "delete") {
      // Convert to soft-delete
      params.action = "updateMany";
      params.args.data = {
        deletedAt: new Date(),
        updatedAt: new Date(),
      };
    }

    return next(params);
  });

  // Query logging in development
  client.$on("query", (e) => {
    if (e.duration > 200) {
      console.warn(`[SLOW QUERY] ${e.query} (${e.duration}ms)`);
    }
  });

  return client;
}

export const prisma = globalForPrisma.prisma ?? createPrismaClient();

if (process.env.NODE_ENV !== "production") {
  globalForPrisma.prisma = prisma;
}

// Soft-delete helper: allows querying deleted records when needed
export function withDeletedArgs<T extends Record<string, unknown>>(
  args: T
): T & { deletedAt?: null } {
  const { deletedAt: _, ...rest } = args as { deletedAt?: unknown };
  return rest as T;
}

// Hard-delete for admin operations
export async function hardDelete<T>(
  model: { delete: (args: { where: { id: string } }) => Promise<T> },
  id: string
): Promise<T> {
  return model.delete({ where: { id } });
}
```

```typescript
// src/repositories/prisma-repo.ts
import { prisma } from "../lib/prisma-client";
import {
  Prisma,
  User,
  Product,
  Order,
  Category,
  Review,
} from "@prisma/client";

// ── User Repository ──────────────────────────────────────────────

export async function findUserByEmail(email: string) {
  return prisma.user.findFirst({ where: { email } });
}

export async function createUser(data: Prisma.UserCreateInput) {
  return prisma.user.create({ data });
}

export async function findUserWithProfile(userId: string) {
  return prisma.user.findFirst({
    where: { id: userId },
    include: { profile: true },
  });
}

export async function updateUserProfile(
  userId: string,
  data: Prisma.UserProfileUpdateInput
) {
  return prisma.userProfile.upsert({
    where: { userId },
    update: data,
    create: { userId, ...data },
  });
}

// ── Product Repository ───────────────────────────────────────────

export async function listProducts(params: {
  skip?: number;
  take?: number;
  categoryId?: string;
  minPrice?: number;
  maxPrice?: number;
  search?: string;
}) {
  const { skip = 0, take = 20, categoryId, minPrice, maxPrice, search } = params;

  const where: Prisma.ProductWhereInput = {
    isActive: true,
  };

  if (categoryId) {
    where.categoryIds = { has: categoryId };
  }

  if (minPrice !== undefined || maxPrice !== undefined) {
    where.price = {};
    if (minPrice !== undefined) (where.price as Prisma.DecimalFilter).gte = minPrice;
    if (maxPrice !== undefined) (where.price as Prisma.DecimalFilter).lte = maxPrice;
  }

  if (search) {
    where.OR = [
      { name: { contains: search, mode: "insensitive" } },
      { description: { contains: search, mode: "insensitive" } },
    ];
  }

  const [products, total] = await Promise.all([
    prisma.product.findMany({
      where,
      skip,
      take,
      include: { categories: true },
      orderBy: { createdAt: "desc" },
    }),
    prisma.product.count({ where }),
  ]);

  return { products, total, hasMore: skip + take < total };
}

export async function createProduct(data: Prisma.ProductCreateInput) {
  return prisma.product.create({ data });
}

export async function updateProduct(
  id: string,
  data: Prisma.ProductUpdateInput
) {
  return prisma.product.update({ where: { id }, data });
}

export async function softDeleteProduct(id: string) {
  return prisma.product.update({
    where: { id },
    data: { deletedAt: new Date(), isActive: false },
  });
}

// ── Order Repository ─────────────────────────────────────────────

export async function createOrder(data: {
  userId: string;
  items: Array<{ productId: string; quantity: number; unitPrice: number }>;
}) {
  const total = data.items.reduce(
    (sum, item) => sum + item.unitPrice * item.quantity,
    0
  );

  return prisma.$transaction(async (tx) => {
    const order = await tx.order.create({
      data: {
        userId: data.userId,
        total,
        items: {
          create: data.items.map((item) => ({
            productId: item.productId,
            quantity: item.quantity,
            unitPrice: item.unitPrice,
          })),
        },
      },
      include: { items: true },
    });

    // Decrement stock for each product
    for (const item of data.items) {
      await tx.product.update({
        where: { id: item.productId },
        data: { stock: { decrement: item.quantity } },
      });
    }

    return order;
  });
}

export async function listOrdersByUser(userId: string) {
  return prisma.order.findMany({
    where: { userId },
    include: {
      items: {
        include: { product: true },
      },
    },
    orderBy: { createdAt: "desc" },
  });
}

// ── Category Repository ──────────────────────────────────────────

export async function getCategoryTree() {
  const categories = await prisma.category.findMany({
    where: { parentId: null },
    include: {
      children: {
        include: {
          children: true,
        },
      },
    },
  });
  return categories;
}

export async function createCategory(data: Prisma.CategoryCreateInput) {
  return prisma.category.create({ data });
}

// ── Review Repository ────────────────────────────────────────────

export async function getProductReviews(productId: string) {
  return prisma.review.findMany({
    where: { productId },
    include: { user: { select: { id: true, name: true, profile: { select: { avatar: true } } } } },
    orderBy: { createdAt: "desc" },
  });
}

export async function upsertReview(data: {
  userId: string;
  productId: string;
  rating: number;
  title?: string;
  body?: string;
}) {
  return prisma.review.upsert({
    where: {
      userId_productId: {
        userId: data.userId,
        productId: data.productId,
      },
    },
    update: {
      rating: data.rating,
      title: data.title,
      body: data.body,
    },
    create: data,
  });
}
```

### 3B — Drizzle Variant

```typescript
// drizzle.config.ts
import { defineConfig } from "drizzle-kit";

export default defineConfig({
  schema: "./src/drizzle/schema.ts",
  out: "./src/drizzle/migrations",
  dialect: "postgresql",
  dbCredentials: {
    url: process.env.DATABASE_URL!,
  },
  verbose: true,
  strict: true,
});
```

```typescript
// src/drizzle/schema.ts
import {
  pgTable,
  text,
  varchar,
  integer,
  decimal,
  boolean,
  timestamp,
  jsonb,
  uniqueIndex,
  index,
  primaryKey,
} from "drizzle-orm/pg-core";
import { relations } from "drizzle-orm";

// ── Users ────────────────────────────────────────────────────────

export const users = pgTable(
  "users",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    email: varchar("email", { length: 255 }).notNull().unique(),
    name: varchar("name", { length: 255 }).notNull(),
    role: varchar("role", { length: 50 }).notNull().default("CUSTOMER"),
    createdAt: timestamp("created_at", { withTimezone: true })
      .notNull()
      .defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
  },
  (table) => [
    index("idx_users_email").on(table.email),
    index("idx_users_role").on(table.role),
  ]
);

export const userProfiles = pgTable(
  "user_profiles",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id")
      .notNull()
      .unique()
      .references(() => users.id, { onDelete: "cascade" }),
    avatar: text("avatar"),
    bio: text("bio"),
    phone: varchar("phone", { length: 30 }),
    address: jsonb("address"),
  },
  (table) => [index("idx_user_profiles_user_id").on(table.userId)]
);

// ── Categories (self-referential tree) ───────────────────────────

export const categories = pgTable(
  "categories",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    name: varchar("name", { length: 255 }).notNull().unique(),
    slug: varchar("slug", { length: 255 }).notNull().unique(),
    parentId: text("parent_id").references((): any => categories.id, {
      onDelete: "set null",
    }),
    createdAt: timestamp("created_at", { withTimezone: true })
      .notNull()
      .defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
  },
  (table) => [
    index("idx_categories_parent_id").on(table.parentId),
    index("idx_categories_slug").on(table.slug),
  ]
);

// ── Products ─────────────────────────────────────────────────────

export const products = pgTable(
  "products",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    name: varchar("name", { length: 255 }).notNull(),
    slug: varchar("slug", { length: 255 }).notNull().unique(),
    description: text("description"),
    price: decimal("price", { precision: 10, scale: 2 }).notNull(),
    sku: varchar("sku", { length: 100 }).notNull().unique(),
    stock: integer("stock").notNull().default(0),
    isActive: boolean("is_active").notNull().default(true),
    createdAt: timestamp("created_at", { withTimezone: true })
      .notNull()
      .defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
  },
  (table) => [
    index("idx_products_sku").on(table.sku),
    index("idx_products_slug").on(table.slug),
    index("idx_products_active_price").on(table.isActive, table.price),
  ]
);

// ── Product ↔ Category junction (M:N) ───────────────────────────

export const productCategories = pgTable(
  "product_categories",
  {
    productId: text("product_id")
      .notNull()
      .references(() => products.id, { onDelete: "cascade" }),
    categoryId: text("category_id")
      .notNull()
      .references(() => categories.id, { onDelete: "cascade" }),
  },
  (t) => [primaryKey({ columns: [t.productId, t.categoryId] })]
);

// ── Orders ───────────────────────────────────────────────────────

export const orders = pgTable(
  "orders",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "restrict" }),
    status: varchar("status", { length: 50 }).notNull().default("PENDING"),
    total: decimal("total", { precision: 10, scale: 2 }).notNull(),
    createdAt: timestamp("created_at", { withTimezone: true })
      .notNull()
      .defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
  },
  (table) => [
    index("idx_orders_user_status").on(table.userId, table.status),
    index("idx_orders_created_at").on(table.createdAt),
  ]
);

// ── Order Items ──────────────────────────────────────────────────

export const orderItems = pgTable(
  "order_items",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    orderId: text("order_id")
      .notNull()
      .references(() => orders.id, { onDelete: "cascade" }),
    productId: text("product_id")
      .notNull()
      .references(() => products.id, { onDelete: "restrict" }),
    quantity: integer("quantity").notNull(),
    unitPrice: decimal("unit_price", { precision: 10, scale: 2 }).notNull(),
  },
  (table) => [
    index("idx_order_items_order_id").on(table.orderId),
    index("idx_order_items_product_id").on(table.productId),
  ]
);

// ── Reviews ──────────────────────────────────────────────────────

export const reviews = pgTable(
  "reviews",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "restrict" }),
    productId: text("product_id")
      .notNull()
      .references(() => products.id, { onDelete: "restrict" }),
    rating: integer("rating").notNull(),
    title: varchar("title", { length: 255 }),
    body: text("body"),
    createdAt: timestamp("created_at", { withTimezone: true })
      .notNull()
      .defaultNow(),
    updatedAt: timestamp("updated_at", { withTimezone: true })
      .notNull()
      .defaultNow()
      .$onUpdate(() => new Date()),
    deletedAt: timestamp("deleted_at", { withTimezone: true }),
  },
  (table) => [
    uniqueIndex("idx_reviews_user_product").on(table.userId, table.productId),
    index("idx_reviews_product_rating").on(table.productId, table.rating),
  ]
);

// ── Cart Items ───────────────────────────────────────────────────

export const cartItems = pgTable(
  "cart_items",
  {
    id: text("id")
      .primaryKey()
      .$defaultFn(() => crypto.randomUUID()),
    userId: text("user_id")
      .notNull()
      .references(() => users.id, { onDelete: "cascade" }),
    productId: text("product_id")
      .notNull()
      .references(() => products.id, { onDelete: "cascade" }),
    quantity: integer("quantity").notNull().default(1),
  },
  (table) => [
    uniqueIndex("idx_cart_items_user_product").on(table.userId, table.productId),
  ]
);

// ── Relations ────────────────────────────────────────────────────

export const usersRelations = relations(users, ({ one, many }) => ({
  profile: one(userProfiles, {
    fields: [users.id],
    references: [userProfiles.userId],
  }),
  orders: many(orders),
  reviews: many(reviews),
  cartItems: many(cartItems),
}));

export const userProfilesRelations = relations(userProfiles, ({ one }) => ({
  user: one(users, {
    fields: [userProfiles.userId],
    references: [users.id],
  }),
}));

export const categoriesRelations = relations(categories, ({ one, many }) => ({
  parent: one(categories, {
    fields: [categories.parentId],
    references: [categories.id],
    relationName: "CategoryTree",
  }),
  children: many(categories, { relationName: "CategoryTree" }),
  productCategories: many(productCategories),
}));

export const productsRelations = relations(products, ({ many }) => ({
  productCategories: many(productCategories),
  orderItems: many(orderItems),
  reviews: many(reviews),
  cartItems: many(cartItems),
}));

export const productCategoriesRelations = relations(
  productCategories,
  ({ one }) => ({
    product: one(products, {
      fields: [productCategories.productId],
      references: [products.id],
    }),
    category: one(categories, {
      fields: [productCategories.categoryId],
      references: [categories.id],
    }),
  })
);

export const ordersRelations = relations(orders, ({ one, many }) => ({
  user: one(users, {
    fields: [orders.userId],
    references: [users.id],
  }),
  items: many(orderItems),
}));

export const orderItemsRelations = relations(orderItems, ({ one }) => ({
  order: one(orders, {
    fields: [orderItems.orderId],
    references: [orders.id],
  }),
  product: one(products, {
    fields: [orderItems.productId],
    references: [products.id],
  }),
}));

export const reviewsRelations = relations(reviews, ({ one }) => ({
  user: one(users, {
    fields: [reviews.userId],
    references: [users.id],
  }),
  product: one(products, {
    fields: [reviews.productId],
    references: [products.id],
  }),
}));

export const cartItemsRelations = relations(cartItems, ({ one }) => ({
  user: one(users, {
    fields: [cartItems.userId],
    references: [users.id],
  }),
  product: one(products, {
    fields: [cartItems.productId],
    references: [products.id],
  }),
}));
```

```typescript
// src/drizzle/client.ts
import { drizzle } from "drizzle-orm/node-postgres";
import { Pool } from "pg";
import * as schema from "./schema";

const globalForDrizzle = globalThis as unknown as { drizzlePool: Pool };

function createPool(): Pool {
  if (globalForDrizzle.drizzlePool) return globalForDrizzle.drizzlePool;

  const pool = new Pool({
    connectionString: process.env.DATABASE_URL,
    max: 20,
    idleTimeoutMillis: 30_000,
    connectionTimeoutMillis: 10_000,
  });

  pool.on("error", (err) => {
    console.error("[DRIZZLE POOL] Unexpected error on idle client:", err);
  });

  if (process.env.NODE_ENV !== "production") {
    globalForDrizzle.drizzlePool = pool;
  }

  return pool;
}

export const db = drizzle(createPool(), { schema });

// ── Soft-delete filter helper ────────────────────────────────────

import { eq, isNull, SQL, and } from "drizzle-orm";

type SoftDeletable = { deletedAt: any };

export function notDeleted<T extends SoftDeletable>(
  table: T
): SQL | undefined {
  return isNull(table.deletedAt);
}

export function softDeleteById<T extends { deletedAt: any; id: any }>(
  table: T,
  id: string
) {
  return db
    .update(table)
    .set({ deletedAt: new Date() } as any)
    .where(eq((table as any).id, id));
}
```

```typescript
// src/repositories/drizzle-repo.ts
import { db } from "../drizzle/client";
import { eq, desc, and, sql, isNull, inArray } from "drizzle-orm";
import {
  users,
  userProfiles,
  categories,
  products,
  productCategories,
  orders,
  orderItems,
  reviews,
} from "../drizzle/schema";

// ── User Repository ──────────────────────────────────────────────

export async function findUserByEmail(email: string) {
  const rows = await db
    .select()
    .from(users)
    .where(and(eq(users.email, email), isNull(users.deletedAt)))
    .limit(1);

  return rows[0] ?? null;
}

export async function createUser(data: typeof users.$inferInsert) {
  const [row] = await db.insert(users).values(data).returning();
  return row;
}

export async function findUserWithProfile(userId: string) {
  const rows = await db
    .select({
      user: users,
      profile: userProfiles,
    })
    .from(users)
    .leftJoin(userProfiles, eq(users.id, userProfiles.userId))
    .where(and(eq(users.id, userId), isNull(users.deletedAt)))
    .limit(1);

  if (rows.length === 0) return null;

  return { ...rows[0].user, profile: rows[0].profile };
}

export async function upsertUserProfile(
  userId: string,
  data: Partial<typeof userProfiles.$inferInsert>
) {
  const existing = await db
    .select({ id: userProfiles.id })
    .from(userProfiles)
    .where(eq(userProfiles.userId, userId))
    .limit(1);

  if (existing.length > 0) {
    const [row] = await db
      .update(userProfiles)
      .set(data)
      .where(eq(userProfiles.userId, userId))
      .returning();
    return row;
  }

  const [row] = await db
    .insert(userProfiles)
    .values({ userId, ...data } as typeof userProfiles.$inferInsert)
    .returning();
  return row;
}

// ── Product Repository ───────────────────────────────────────────

export async function listProducts(params: {
  skip?: number;
  take?: number;
  categoryId?: string;
  minPrice?: number;
  maxPrice?: number;
  search?: string;
}) {
  const { skip = 0, take = 20, categoryId, minPrice, maxPrice, search } = params;

  const conditions = [isNull(products.deletedAt), eq(products.isActive, true)];

  if (minPrice !== undefined) {
    conditions.push(sql`${products.price} >= ${minPrice.toString()}`);
  }
  if (maxPrice !== undefined) {
    conditions.push(sql`${products.price} <= ${maxPrice.toString()}`);
  }
  if (search) {
    conditions.push(
      sql`(${products.name} ILIKE ${`%${search}%`} OR ${products.description} ILIKE ${`%${search}%`})`
    );
  }

  const rows = await db
    .select()
    .from(products)
    .where(and(...conditions))
    .orderBy(desc(products.createdAt))
    .limit(take)
    .offset(skip);

  const countRows = await db
    .select({ count: sql<number>`count(*)::int` })
    .from(products)
    .where(and(...conditions));

  const total = countRows[0]?.count ?? 0;

  // Attach categories for each product
  if (rows.length > 0) {
    const productIds = rows.map((p) => p.id);
    const catRows = await db
      .select({
        productId: productCategories.productId,
        category: categories,
      })
      .from(productCategories)
      .innerJoin(categories, eq(productCategories.categoryId, categories.id))
      .where(inArray(productCategories.productId, productIds));

    const catMap = new Map<string, typeof categories.$inferSelect[]>();
    for (const row of catRows) {
      const list = catMap.get(row.productId) ?? [];
      list.push(row.category);
      catMap.set(row.productId, list);
    }

    for (const product of rows) {
      (product as any).categories = catMap.get(product.id) ?? [];
    }
  }

  return { products: rows, total, hasMore: skip + take < total };
}

export async function createProduct(data: typeof products.$inferInsert) {
  const [row] = await db.insert(products).values(data).returning();
  return row;
}

export async function addProductCategory(
  productId: string,
  categoryId: string
) {
  return db
    .insert(productCategories)
    .values({ productId, categoryId })
    .onConflictDoNothing();
}

export async function softDeleteProduct(id: string) {
  const [row] = await db
    .update(products)
    .set({ deletedAt: new Date(), isActive: false })
    .where(eq(products.id, id))
    .returning();
  return row;
}

// ── Order Repository ─────────────────────────────────────────────

export async function createOrder(data: {
  userId: string;
  items: Array<{ productId: string; quantity: number; unitPrice: number }>;
}) {
  return db.transaction(async (tx) => {
    const total = data.items
      .reduce((sum, i) => sum + Number(i.unitPrice) * i.quantity, 0)
      .toString();

    const [order] = await tx
      .insert(orders)
      .values({ userId: data.userId, total })
      .returning();

    const items = await tx
      .insert(orderItems)
      .values(
        data.items.map((item) => ({
          orderId: order.id,
          productId: item.productId,
          quantity: item.quantity,
          unitPrice: item.unitPrice.toString(),
        }))
      )
      .returning();

    for (const item of data.items) {
      await tx
        .update(products)
        .set({ stock: sql`${products.stock} - ${item.quantity}` })
        .where(eq(products.id, item.productId));
    }

    return { ...order, items };
  });
}

export async function listOrdersByUser(userId: string) {
  const orderRows = await db
    .select()
    .from(orders)
    .where(and(eq(orders.userId, userId), isNull(orders.deletedAt)))
    .orderBy(desc(orders.createdAt));

  const orderIds = orderRows.map((o) => o.id);
  if (orderIds.length === 0) return [];

  const itemRows = await db
    .select({
      orderItem: orderItems,
      product: products,
    })
    .from(orderItems)
    .innerJoin(products, eq(orderItems.productId, products.id))
    .where(inArray(orderItems.orderId, orderIds));

  const itemsMap = new Map<string, typeof itemRows>();
  for (const row of itemRows) {
    const list = itemsMap.get(row.orderItem.orderId) ?? [];
    list.push(row);
    itemsMap.set(row.orderItem.orderId, list);
  }

  return orderRows.map((order) => ({
    ...order,
    items: itemsMap.get(order.id) ?? [],
  }));
}

// ── Category Repository ──────────────────────────────────────────

export async function getCategoryTree() {
  const all = await db
    .select()
    .from(categories)
    .where(isNull(categories.deletedAt))
    .orderBy(categories.name);

  const map = new Map<string, any>();
  const roots: any[] = [];

  for (const cat of all) {
    map.set(cat.id, { ...cat, children: [] });
  }

  for (const cat of all) {
    const node = map.get(cat.id)!;
    if (cat.parentId && map.has(cat.parentId)) {
      map.get(cat.parentId)!.children.push(node);
    } else {
      roots.push(node);
    }
  }

  return roots;
}

export async function createCategory(data: typeof categories.$inferInsert) {
  const [row] = await db.insert(categories).values(data).returning();
  return row;
}

// ── Review Repository ────────────────────────────────────────────

export async function getProductReviews(productId: string) {
  const rows = await db
    .select({
      review: reviews,
      user: { id: users.id, name: users.name },
      profile: { avatar: userProfiles.avatar },
    })
    .from(reviews)
    .innerJoin(users, eq(reviews.userId, users.id))
    .leftJoin(userProfiles, eq(users.id, userProfiles.userId))
    .where(
      and(eq(reviews.productId, productId), isNull(reviews.deletedAt))
    )
    .orderBy(desc(reviews.createdAt));

  return rows.map((row) => ({
    ...row.review,
    user: { ...row.user, profile: row.profile },
  }));
}

export async function upsertReview(data: {
  userId: string;
  productId: string;
  rating: number;
  title?: string;
  body?: string;
}) {
  const existing = await db
    .select({ id: reviews.id })
    .from(reviews)
    .where(
      and(eq(reviews.userId, data.userId), eq(reviews.productId, data.productId))
    )
    .limit(1);

  if (existing.length > 0) {
    const [row] = await db
      .update(reviews)
      .set({
        rating: data.rating,
        title: data.title ?? null,
        body: data.body ?? null,
      })
      .where(eq(reviews.id, existing[0].id))
      .returning();
    return row;
  }

  const [row] = await db.insert(reviews).values(data).returning();
  return row;
}
```

## 4. Execution Protocol & Step-by-Step Workflow

### Prisma Setup

```bash
# 1. Install dependencies
npm install prisma @prisma/client
npm install -D typescript @types/node tsx

# 2. Initialize Prisma (creates prisma/ directory)
npx prisma init --datasource-provider postgresql

# 3. Apply schema (writes migration SQL)
npx prisma migrate dev --name init

# 4. Generate Prisma Client
npx prisma generate

# 5. Run project
npx tsx src/index.ts

# 6. View data in browser
npx prisma studio
```

### Drizzle Setup

```bash
# 1. Install dependencies
npm install drizzle-orm pg
npm install -D drizzle-kit @types/pg typescript tsx

# 2. Configure (already written to drizzle.config.ts)
# drizzle.config.ts is placed at project root

# 3. Generate migration files
npx drizzle-kit generate

# 4. Push schema directly to database (skip migrations for dev)
npx drizzle-kit push

# 5. Open Drizzle Studio for visual inspection
npx drizzle-kit studio

# 6. Run project
npx tsx src/index.ts
```

## 5. Edge Cases & Error Handling

- **Concurrent soft-deletes:** Two users may soft-delete the same record; the `updatedAt` field acts as a conflict detector — always check `updatedAt` before proceeding with updates.
- **Circular category references:** The self-referential `parentId` can form cycles; validate in application code before inserting. Consider adding a maximum depth check (e.g., 5 levels).
- **Prisma middleware ordering:** The soft-delete middleware must be registered before any queries execute — place it at client creation time, not per-request.
- **Drizzle transaction isolation:** Use `db.transaction()` for multi-table writes (order + items + stock) to ensure atomicity; Prisma handles this with `$transaction`.
- **Migration conflicts:** When both ORMs modify the same table, use `--create-only` flags and review generated SQL before applying; never auto-push to production.
- **Decimal precision:** PostgreSQL `DECIMAL(10,2)` truncates beyond 2 decimal places; always round in application code before writing to avoid silent data loss.
- **Stock race conditions:** Use `UPDATE ... WHERE stock >= quantity` with returned row-count to detect overselling rather than blind decrement.
- **Schema drift:** Periodically run `npx prisma validate` and `npx drizzle-kit check` to detect drift between ORM definitions and actual database state.
- **Performance:** The composite index `@@index([userId, status])` on orders is critical for the order-listing query pattern — without it, a full table scan occurs at scale.
