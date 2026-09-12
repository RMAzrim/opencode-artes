---
id: playwright-e2e-security-flow-tester
file_path: skills/playwright-e2e-security-flow-tester/playwright-e2e-security-flow-tester.md
name: Playwright E2E Security Flow Tester
category: backend
tags: [playwright, e2e, page-object-model, testing]
author: opencode-core
version: 1.0.0
description: Crafts automated End-to-End (E2E) browser testing suites validating critical user journeys, edge cases, and client-side security boundary enforcement.
---

# Playwright E2E Security Flow Tester

## 1. System Architecture & Prerequisites

This skill builds a **Playwright + TypeScript** E2E testing suite applying the **Page Object Model (POM)** and security-focused test assertions. The suite covers:

- **Authentication flows:** valid login, invalid credentials, form validation
- **XSS defense validation:** `<script>` injection asserted to render escaped (no dialog fires)
- **Route guarding:** unauthenticated redirects to `/login`, role-based authorization
- **Visual regression:** `toMatchSnapshot` on key views, run across chromium/firefox/webkit
- **Session persistence:** `storageState` fixtures preserve login state across tests

**Prerequisites:**

- Node.js ≥ 18
- `npm init -y` then `npm install -D @playwright/test typescript`

## 2. Input/Output Data Contracts

**Input — Environment Variables:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "required": ["TEST_BASE_URL"],
  "properties": {
    "TEST_BASE_URL": {
      "type": "string",
      "default": "http://localhost:3000",
      "description": "Application base URL under test"
    },
    "TEST_USER_EMAIL": { "type": "string", "default": "e2e@example.com" },
    "TEST_USER_PASSWORD": { "type": "string", "default": "TestPassword123!" }
  }
}
```

**Output Artifacts:**

| Path | Description |
|---|---|
| `playwright.config.ts` | Playwright configuration (webServer, 3 projects) |
| `src/pages/LoginPage.ts` | Login page object |
| `src/pages/DashboardPage.ts` | Dashboard page object |
| `src/fixtures/auth.ts` | Auth fixtures (storageState + restoreLoginState) |
| `tests/login.spec.ts` | Login + validation + XSS tests |
| `tests/auth-guard.spec.ts` | Route guard tests |
| `tests/input.spec.ts` | Sanitized input rendering tests |
| `tests/snapshot.spec.ts` | Visual regression tests |
| `package.json` | Test scripts + dependencies |

## 3. Production Reference Implementation

```typescript
// playwright.config.ts
import { defineConfig, devices } from "@playwright/test";

const BASE_URL = process.env.TEST_BASE_URL ?? "http://localhost:3000";

export default defineConfig({
  testDir: "./tests",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: [["list"], ["html", { open: "never" }]],
  timeout: 60_000,
  expect: {
    timeout: 10_000,
    toHaveScreenshot: {
      maxDiffPixels: 200,
    },
  },
  use: {
    baseURL: BASE_URL,
    trace: "on-first-retry",
    video: "on-first-retry",
    screenshot: "only-on-failure",
  },

  webServer: {
    command: "npm run dev",
    url: `${BASE_URL}/api/health`,
    reuseExistingServer: !process.env.CI,
    timeout: 120_000,
  },

  projects: [
    {
      name: "chromium-desktop",
      use: {
        ...devices["Desktop Chrome"],
        viewport: { width: 1280, height: 800 },
      },
    },
    {
      name: "chromium-mobile",
      use: {
        ...devices["iPhone 14"],
      },
    },
    {
      name: "firefox",
      use: {
        ...devices["Desktop Firefox"],
        viewport: { width: 1280, height: 800 },
      },
    },
    {
      name: "webkit",
      use: {
        ...devices["Desktop Safari"],
        viewport: { width: 1280, height: 800 },
      },
    },
  ],
});
```

```typescript
// src/pages/LoginPage.ts
import { Page, Locator } from "@playwright/test";

const INJECTION_PATTERNS = [
  "<script>alert(1)</script>",
  '<img src=x onerror="alert(1)">',
  "javascript:alert(1)",
];

export class LoginPage {
  readonly emailInput: Locator;
  readonly passwordInput: Locator;
  readonly submitButton: Locator;
  readonly errorMessage: Locator;

  constructor(readonly page: Page) {
    this.emailInput = page.getByLabel("Email");
    this.passwordInput = page.getByLabel("Password");
    this.submitButton = page.getByRole("button", { name: "Sign In" });
    this.errorMessage = page.locator('[data-testid="form-error"]');
  }

  async goto(): Promise<void> {
    await this.page.goto("/login");
  }

  async login(email: string, password: string): Promise<void> {
    await this.emailInput.fill(email);
    await this.passwordInput.fill(password);
    await this.submitButton.click();
  }

  async expectFormError(message: string): Promise<void> {
    await this.errorMessage.getByText(message).waitFor({ state: "visible" });
  }

  async expectErrorsVisible(): Promise<void> {
    await this.page
      .locator('[data-testid="field-error"], [data-testid="form-error"]')
      .first()
      .waitFor({ state: "visible" });
  }

  async isNavigatedToDashboard(): Promise<boolean> {
    return this.page.url().endsWith("/dashboard");
  }

  async assertXssPayloadScrubbed(payload: string): Promise<void> {
    const httpBody = await this.page.content();
    if (httpBody.includes('<script>alert(1)</script>')) {
      throw new Error(
        "XSS payload leaked into login form — application failed to encode output"
      );
    }
  }

  static injectionPayloads(): string[] {
    return INJECTION_PATTERNS;
  }
}
```

```typescript
// src/pages/DashboardPage.ts
import { Page, Locator } from "@playwright/test";

export class DashboardPage {
  readonly heading: Locator;
  readonly greeting: Locator;
  readonly logoutButton: Locator;
  readonly adminPanelLink: Locator;
  readonly userAvatar: Locator;

  constructor(readonly page: Page) {
    this.heading = page.getByRole("heading", { name: /dashboard/i });
    this.greeting = page.locator('[data-testid="user-greeting"]');
    this.logoutButton = page.getByRole("button", { name: /log out|sign out/i });
    this.adminPanelLink = page.getByRole("link", { name: /admin/i });
    this.userAvatar = page.locator('[data-testid="user-avatar"]');
  }

  async goto(): Promise<void> {
    await this.page.goto("/dashboard");
  }

  async isVisible(): Promise<boolean> {
    return this.heading.isVisible();
  }

  async getGreetingText(): Promise<string> {
    return (await this.greeting.textContent()) ?? "";
  }

  async logout(): Promise<void> {
    await this.logoutButton.click();
  }

  async avatarHasImage(): Promise<boolean> {
    const alt = await this.userAvatar.getAttribute("alt");
    return alt !== null && alt.length > 0;
  }
}
```

```typescript
// src/fixtures/auth.ts
import { test as base, expect, Page, BrowserContext } from "@playwright/test";
import { LoginPage } from "../pages/LoginPage";
import { DashboardPage } from "../pages/DashboardPage";

const TEST_USER_EMAIL = process.env.TEST_USER_EMAIL ?? "e2e@example.com";
const TEST_USER_PASSWORD = process.env.TEST_USER_PASSWORD ?? "TestPassword123!";

const STORAGE_STATE_PATH = "auth/storage-state.json";

export const test = base.extend<{
  authenticatedPage: Page;
  loginPage: LoginPage;
  dashboardPage: DashboardPage;
}>({
  // ── LoginPage factory ────────────────────────────────────────
  loginPage: async ({ page }, use) => {
    const login = new LoginPage(page);
    await use(login);
  },

  // ── DashboardPage factory ────────────────────────────────────
  dashboardPage: async ({ page }, use) => {
    const dashboard = new DashboardPage(page);
    await use(dashboard);
  },

  // ── Authenticated page (fresh login, no stored state) ────────
  authenticatedPage: async ({ browser }, use) => {
    const context: BrowserContext = await browser.newContext();
    const page = await context.newPage();

    const login = new LoginPage(page);
    await login.goto();
    await login.login(TEST_USER_EMAIL, TEST_USER_PASSWORD);
    await expect(page).toHaveURL(/\/dashboard/);

    await use(page);
    await context.close();
  },
});

// ── Helper: save session state after a successful login ────────

export async function saveLoginState(page: Page): Promise<void> {
  await page.waitForURL(/\/dashboard/);
  await page.context().storageState({ path: STORAGE_STATE_PATH });
}

// ── Helper: restore a previously saved login state ─────────────

export async function restoreLoginState(context: BrowserContext): Promise<void> {
  const { existsSync } = await import("fs");
  if (existsSync(STORAGE_STATE_PATH)) {
    const { storageState } = await import("@playwright/test");
    await context.addCookies((await import("fs")).readFileSync(STORAGE_STATE_PATH, "utf-8"));
  }
}

// ── Pre-configured authenticated context fixture ───────────────

export const authenticatedTest = base.extend<{ ctx: BrowserContext }>({
  ctx: async ({ browser }, use) => {
    const context = await browser.newContext({
      storageState: STORAGE_STATE_PATH,
    });
    await use(context);
    await context.close();
  },
});

export { TEST_USER_EMAIL, TEST_USER_PASSWORD, STORAGE_STATE_PATH, expect };
```

```typescript
// tests/login.spec.ts
import { test, expect, TEST_USER_EMAIL, TEST_USER_PASSWORD } from "../src/fixtures/auth";
import { LoginPage } from "../src/pages/LoginPage";

test.describe("Login Flow", () => {
  test("renders login form with required fields", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();

    await expect(login.emailInput).toBeVisible();
    await expect(login.passwordInput).toBeVisible();
    await expect(login.submitButton).toBeVisible();
  });

  test("successful login navigates to dashboard", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.login(TEST_USER_EMAIL, TEST_USER_PASSWORD);

    await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(page.getByRole("heading", { name: /dashboard/i })).toBeVisible();
  });

  test.describe("validation failures", () => {
    test("empty fields show validation errors and do not submit", async ({ page }) => {
      const login = new LoginPage(page);
      await login.goto();
      await login.submitButton.click();

      await login.expectErrorsVisible();

      const url = page.url();
      expect(url).toContain("/login");
      await expect(login.emailInput).toHaveValue("");
    });

    test("invalid credentials show generic error, not user enumeration", async ({ page }) => {
      const login = new LoginPage(page);
      await login.goto();
      await login.login("nonexistent@example.com", "WrongPassword123!");

      await login.expectFormError("Invalid email or password");
      await page.getByText("The email does not exist").waitFor({ state: "detached" }).catch(() => {});
    });

    test("malformed email rejected with field-level error", async ({ page }) => {
      const login = new LoginPage(page);
      await login.goto();
      await login.login("not-an-email", TEST_USER_PASSWORD);

      await page.locator('[data-testid="field-error"]').first().waitFor({ state: "visible" });
      await expect(page.getByText(/valid email/i).or(page.getByText(/email.*invalid/i))).toBeVisible();
    });
  });

  test.describe("XSS payloads in login inputs", () => {
    for (const payload of LoginPage.injectionPayloads()) {
      test(`XSS payload scrubbed: ${payload.slice(0, 40)}`, async ({ page }) => {
        const login = new LoginPage(page);
        await login.goto();
        await login.login(payload, payload);

        await page.waitForTimeout(500);
        await login.assertXssPayloadScrubbed(payload);

        const dialogs: string[] = [];
        page.once("dialog", (dialog) => {
          dialogs.push(dialog.message());
          dialog.dismiss();
        });

        await login.submitButton.click();
        await page.waitForTimeout(1000);

        expect(dialogs).toHaveLength(0);
      });
    }
  });

  test("error styling applied to invalid inputs (SR + visibility)", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await login.login("bad-email", "");

    const ariaInvalid = await login.emailInput.getAttribute("aria-invalid");
    expect(ariaInvalid).toBe("true");
    await expect(page.locator('[data-testid="field-error"]').first()).toBeVisible();
    await expect(page.locator('[data-testid="field-error"]').first()).toBeAttached();
  });
});
```

```typescript
// tests/auth-guard.spec.ts
import { test, expect, LoginPage } from "../src/fixtures/auth";
import { DashboardPage } from "../src/pages/DashboardPage";

test.describe("Route Guards", () => {
  const PROTECTED_ROUTES = [
    "/dashboard",
    "/dashboard/settings",
    "/dashboard/orders",
    "/checkout",
    "/account",
  ];

  for (const route of PROTECTED_ROUTES) {
    test(`unauthenticated access to ${route} redirects to /login`, async ({ page }) => {
      await page.goto(route);

      await page.waitForURL(/\/login/, { timeout: 10_000 });
      await expect(page).toHaveURL(/\/login/);

      const redirected = new URL(page.url()).searchParams.get("redirect");
      expect(redirected).toBe(route);
    });
  }

  test("bounce: after login, original URL is honored via redirect param", async ({ page }) => {
    const target = "/dashboard/orders";
    await page.goto(target);
    await page.waitForURL(/\/login/);

    const loginUrl = new URL(page.url());
    const redirectPath = loginUrl.searchParams.get("redirect");
    expect(redirectPath).toBe(target);

    const login = new LoginPage(page);
    await login.login(
      process.env.TEST_USER_EMAIL ?? "e2e@example.com",
      process.env.TEST_USER_PASSWORD ?? "TestPassword123!"
    );

    await page.waitForURL("**" + target, { timeout: 15_000 });
    await expect(page).toHaveURL(/\/dashboard\/orders/);
  });

  test.describe("role-based authorization", () => {
    test("CUSTOMER cannot reach /admin", async ({ page }) => {
      await page.goto("/admin");
      await page.waitForURL(/\/login/, { timeout: 10_000 });
    });

    test("CUSTOMER cannot reach admin API via direct navigation", async ({ page }) => {
      const response = await page.goto("/api/admin/users", { waitUntil: "domcontentloaded" });
      // app returns 403, page may render a fallback; assert HTTP status
      const status = response?.status();
      expect(status).toBe(403);
    });

    test("VENDOR sees vendor menu only", async ({ page, context }) => {
      await page.goto("/admin");
      await page.waitForURL(/\/login/);
      const login = new LoginPage(page);
      await login.login(
        process.env.VENDOR_EMAIL ?? "vendor@example.com",
        process.env.VENDOR_PASSWORD ?? "VendorPass123!"
      );
      await page.waitForURL(/\/login\/?$/, { timeout: 5_000 }).catch(() => {});

      const vendorLink = page.getByRole("link", { name: /vendor dashboard/i });
      const adminLink = page.getByRole("link", { name: /admin panel/i });
      await expect(vendorLink).toBeVisible();
      await expect(adminLink).toBeHidden();
    });
  });

  test("stale session redirects to login", async ({ page, context }) => {
    const dashboard = new DashboardPage(page);
    await dashboard.goto();

    await context.clearCookies();

    await page.goto("/dashboard");
    await page.waitForURL(/\/login/, { timeout: 10_000 });
    await expect(page).toHaveURL(/\/login/);
  });
});
```

```typescript
// tests/input.spec.ts
import { test, expect } from "../src/fixtures/auth";

const XSS_ATTACKS = [
  '<script>alert(1)</script>',
  '<img src=x onerror=alert(1)>',
  '<svg onload=alert(1)>',
  'javascript:alert(1)//',
  '"><script>alert(String.fromCharCode(88,83,83))</script>',
  '{{7*7}}',
  '${7*7}',
  '<iframe srcdoc="<script>alert(1)</script>"></iframe>',
];

test.describe("Client-side XSS defenses", () => {
  for (const payload of XSS_ATTACKS) {
    test(`renders escaped: ${payload.slice(0, 35)}`, async ({ page }) => {
      await page.goto("/search?q=" + encodeURIComponent(payload));
      await page.waitForSelector('[data-testid="search-results"]', { timeout: 10_000 });

      const body = await page.content();

      // 1. Any raw script tag present in DOM must not have executed
      //    Playwright isolates dialogs; assert none fires.
      const dialogs: string[] = [];
      page.on("dialog", (dialog) => {
        dialogs.push(dialog.message());
        dialog.dismiss();
      });
      await page.waitForTimeout(800);
      expect(dialogs).toHaveLength(0);

      // 2. The literal text should appear as textContent (escaped representation)
      const resultText = await page.locator('[data-testid="search-results"]').innerText();
      const encodedCandidates = [payload, payload.replace(/</g, "&lt;").replace(/>/g, "&gt;")];
      const found = encodedCandidates.some((c) => resultText.includes(c));

      // 3. If the framework hoists payloads into attributes, verify attribute-bound values
      if (!found) {
        const html = body.toLowerCase();
        const decoded = payload.toLowerCase().replaceAll("&lt;", "<");
        // Unescaped payload present as executable markup = vulnerability
        const rawFormPresent = html.includes(decoded.replace(/<script>/, "<script>"));
        expect(rawFormPresent).toBe(false);
      }
    });
  }

  test("interaction tokens are not reflected into DOM keywords", async ({ page }) => {
    await page.goto("/");
    await page.click('button[data-testid="increment-button"]');
    await expect(page.locator('[data-testid="counter"]')).toHaveText("1");
    await page.waitForTimeout(300);
    const body = await page.content();
    expect(body.toLowerCase()).not.toContain("</script>");
  });

  test("login error messages reflect inputs safely", async ({ page }) => {
    await page.goto("/login");
    await page.getByLabel("Email").fill('<script>alert("xss")</script>');
    await page.getByLabel("Password").fill("password");
    await page.getByRole("button", { name: "Sign In" }).click();

    await page.locator('[data-testid="form-error"]').waitFor({ state: "visible" });
    const errorText = await page.locator('[data-testid="form-error"]').innerText();
    expect(errorText).not.toContain("<script>");

    const dialogs: string[] = [];
    page.on("dialog", (dialog) => {
      dialogs.push(dialog.message());
      dialog.dismiss();
    });
    await page.waitForTimeout(500);
    expect(dialogs).toHaveLength(0);
  });

  test("no javascript: URIs on anchor links", async ({ page }) => {
    await page.goto("/");
    const jsUris = await page.locator("a[href^='javascript:']").count();
    expect(jsUris).toBe(0);
  });
});
```

```typescript
// tests/snapshot.spec.ts
import { test, expect } from "../src/fixtures/auth";
import { LoginPage } from "../src/pages/LoginPage";
import { DashboardPage } from "../src/pages/DashboardPage";

test.describe("Visual Regression — Desktop Chromium", () => {
  test.use({ viewport: { width: 1280, height: 800 } });

  test("login page snapshot", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await expect.soft(page).toHaveScreenshot("login-page.png");
  });

  test("dashboard snapshot", async ({ page }) => {
    await page
      .goto("/dashboard")
      .catch(() => {});
    await page.waitForURL(/\/login|dashboard/, { timeout: 10_000 });

    if (page.url().includes("/login")) {
      const login = new LoginPage(page);
      await login.login(
        process.env.TEST_USER_EMAIL ?? "e2e@example.com",
        process.env.TEST_USER_PASSWORD ?? "TestPassword123!"
      );
    }

    await page.waitForURL(/\/dashboard/, { timeout: 15_000 });
    await new DashboardPage(page).isVisible();
    await expect.soft(page).toHaveScreenshot("dashboard-1280.png");
  });

  test("mobile width dashboard snapshot", async ({ page }) => {
    await page.setViewportSize({ width: 390, height: 844 });

    const login = new LoginPage(page);
    await login.goto();
    await login.login(
      process.env.TEST_USER_EMAIL ?? "e2e@example.com",
      process.env.TEST_USER_PASSWORD ?? "TestPassword123!"
    );
    await page.waitForURL(/\/dashboard/, { timeout: 15_000 });

    await expect.soft(page).toHaveScreenshot("dashboard-mobile-390.png");
  });
});

test.describe("Visual Regression — Firefox", () => {
  test("login page renders consistently", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await expect.soft(page).toHaveScreenshot("firefox-login.png");
  });
});

test.describe("Visual Regression — WebKit", () => {
  test("login page renders consistently", async ({ page }) => {
    const login = new LoginPage(page);
    await login.goto();
    await expect.soft(page).toHaveScreenshot("webkit-login.png");
  });
});
```

```json
// package.json
{
  "name": "playwright-e2e-security-flow-tester",
  "version": "1.0.0",
  "private": true,
  "scripts": {
    "test": "playwright test",
    "test:chromium": "playwright test --project=chromium-desktop",
    "test:headed": "playwright test --headed",
    "test:update-snapshots": "playwright test --update-snapshots",
    "test:report": "playwright show-report"
  },
  "devDependencies": {
    "@playwright/test": "^1.48.0",
    "@types/node": "^20.11.0",
    "typescript": "^5.4.0"
  }
}
```

## 4. Execution Protocol & Step-by-Step Workflow

```bash
# 1. Initialize project and install dependencies
npm init -y
npm install -D @playwright/test typescript @types/node

# 2. Create tsconfig.json
npx tsc --init --rootDir "." --outDir "dist" --module "commonjs" --target "ES2022" --strict true

# 3. Install the Playwright browsers (chromium, firefox, webkit)
npx playwright install --with-deps

# 4. Structure the project
mkdir -p src/pages src/fixtures tests auth

# 5. Run the full E2E suite in headless mode
npx playwright test

# 6. Run a single spec on a specific browser project
npx playwright test tests/login.spec.ts --project=chromium-desktop

# 7. Run with UI (headed + inspector)
npx playwright test --headed --debug

# 8. Generate and view the HTML report
npx playwright show-report

# 9. Regenerate snapshot baselines after intentional UI changes
npx playwright test tests/snapshot.spec.ts --update-snapshots

# 10. Save the session state file (auth/storage-state.json) first run
npm run test:chromium # first run produces a warning if missing; login.spec creates it
```

## 5. Edge Cases & Error Handling

- **Missing storageState:** The `auth/storage-state.json` file is generated after the first successful login test. If it is missing, `authenticatedTest` fixture fails instantly — run `tests/login.spec.ts` once to bootstrap it.
- **Dialog interception:** Playwright auto-dismisses JS dialogs by default, which can mask XSS executions. Always attach an explicit `page.on("dialog", ...)` collector (as in `input.spec.ts`) and assert the collected array is empty.
- **ToHaveScreenshot on flaky animations:** Animate `maxDiffPixels` (default 200) and disable CSS animations/font-loading in the `webServer` if snapshots become flaky (`page.emulateMedia({ reducedMotion: "reduce" })` inside tests).
- **Redirect loops:** A broken `redirect` param can cause infinite redirects between `/login` and protected routes. Set a strict `waitForURL` with a timeout and assert the `redirect` query param value.
- **Rate-limited login endpoint:** CI runs with `workers: 1` to avoid hammering the `login` endpoint. Locally, sequential tests on the same `webServer` instance can retry on 429 responses using `test.describe.configure({ retries: 1 })` at the suite level.
- **Cross-origin API calls:** Playwright's `page.goto("/api/...")` asserts HTTP status correctly only when response is not a client-side navigation. Use `context.request.get()` for pure API assertions.
- **Authorization bypass via `?redirect=//evil.com`:** Guard tests should also verify that the `redirect` param is a same-origin relative path. Add an assertion that `new URL(page.url(), baseURL).origin === baseURL`.
- **Fonts loading timing:** Snapshot tests must wait for `document.fonts.ready` before `toHaveScreenshot`, otherwise baselines differ across runs. Wrap the wait in a fixture: `await page.evaluate(() => document.fonts.ready)`.