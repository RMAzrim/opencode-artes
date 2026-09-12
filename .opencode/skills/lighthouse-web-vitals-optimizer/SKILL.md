---
name: Lighthouse & Web Vitals Optimizer
description: Audits web performance metrics, optimizes client-side bundle footprints, and refactors resource delivery to achieve maximum Core Web Vitals scores.
metadata:
  source: skills/lighthouse-web-vitals-optimizer/lighthouse-web-vitals-optimizer.md
---

# Lighthouse & Web Vitals Optimizer

## 1. System Architecture & Prerequisites

This skill implements a **complete performance optimization pipeline** for a Next.js application:

1. **Headless Lighthouse audits** — config-driven CLI runs generating JSON + HTML reports
2. **Bundle footprint analysis** — `@next/bundle-analyzer` for client bundle sizing
3. **Code-level optimizations** — `React.lazy` + `Suspense`, `next/image` with WebP/AVIF, critical CSS inlining, font-display swap
4. **Core Web Vitals instrumentation** — `web-vitals` package reporting LCP, CLS, INP with `performance.now()` timestamps

**Prerequisites:**

- Next.js ≥ 14 (App Router or Pages Router)
- Chrome/Chromium installed (used by Lighthouse + bundle analyzer)
- `npm install -D lighthouse chrome-launcher @next/bundle-analyzer webpack-bundle-analyzer`
- `npm install web-vitals`

## 2. Input/Output Data Contracts

**Input — Environment Variables:**

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "type": "object",
  "properties": {
    "LH_BASE_URL": {
      "type": "string",
      "default": "http://localhost:3000",
      "description": "URL to audit with Lighthouse"
    },
    "LH_CHROME_PATH": {
      "type": "string",
      "description": "Path to Chrome executable (auto-detected if omitted)"
    },
    "LH_VIEWPORT": {
      "type": "string",
      "default": "1350,940",
      "description": "Desktop viewport for audits"
    },
    "LH_THROTTLING_MOBILE": {
      "type": "boolean",
      "default": true,
      "description": "Apply mobile throttling presets"
    }
  }
}
```

**Output Artifacts:**

| Path | Description |
|---|---|
| `lighthouse/lighthouse.config.ts` | Lighthouse audit configuration |
| `scripts/perf-audit.ps1` | Audit runner (headless, reports to `lighthouse-reports/`) |
| `next.config.ts` | Instrumented output — bundle analyzer + web vitals |
| `src/components/LazyChart.tsx` | `React.lazy` + `Suspense` example |
| `src/lib/reportWebVitals.ts` | CWV instrumentation with `performance.now()` |

## 3. Production Reference Implementation

```typescript
// lighthouse/lighthouse.config.ts
import type { Config } from "lighthouse";

const BASE_URL = process.env.LH_BASE_URL ?? "http://localhost:3000";
const CHROME_PATH =
  process.env.LH_CHROME_PATH ?? // e.g. "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe"
  (() => {
    // Auto-discovery fallbacks
    const candidates = [
      "/usr/bin/google-chrome",
      "/usr/bin/google-chrome-stable",
      "/usr/bin/chromium-browser",
      "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
      "C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
      "C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
      "C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
    ];
    const { existsSync } = require("fs");
    for (const candidate of candidates) {
      if (existsSync(candidate)) return candidate;
    }
    return undefined;
  })();

export interface LighthouseRunOptions {
  url?: string;
  outputDir?: string;
  categories?: Array<"performance" | "a11y" | "best-practices" | "seo" | "pwa">;
}

export function buildLighthouseConfig(
  options: LighthouseRunOptions = {}
): Config {
  const url = options.url ?? `${BASE_URL}/`;

  const categories = options.categories ?? [
    "performance",
    "a11y",
    "best-practices",
    "seo",
  ];

  return {
    extends: "lighthouse:default",
    settings: {
      onlyCategories: categories,
      maxWaitForFcp: 30_000,
      maxWaitForLoad: 45_000,
      throttling: {
        rttMs: process.env.LH_THROTTLING_MOBILE === "false" ? 40 : 150,
        throughputKbps: process.env.LH_THROTTLING_MOBILE === "false" ? 16384 : 1638.4,
        cpuSlowdownMultiplier: process.env.LH_THROTTLING_MOBILE === "false" ? 1 : 4,
        requestLatencyMs: process.env.LH_THROTTLING_MOBILE === "false" ? 0 : 562.5,
        downloadThroughputKbps: process.env.LH_THROTTLING_MOBILE === "false" ? 0 : 1474.6,
        uploadThroughputKbps: process.env.LH_THROTTLING_MOBILE === "false" ? 0 : 675,
      },
      formFactor: process.env.LH_THROTTLING_MOBILE === "false" ? "desktop" : "mobile",
      screenEmulation: {
        mobile: process.env.LH_THROTTLING_MOBILE !== "false",
        width: 360,
        height: 640,
        deviceScaleFactor: 2,
        disabled: false,
      },
      emulatedUserAgent:
        process.env.LH_THROTTLING_MOBILE === "false"
          ? undefined
          : "Mozilla/5.0 (Linux; Android 11; Pixel 5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36",
      throttlingMethod: "simulate",
      auditsDisabled: ["no-unload-listeners"],
      output: ["json", "html"],
      preset: "perf" as unknown as undefined,
    },
    audits: [],
    categories: {
      performance: {
        title: "Performance",
        supportedModes: ["navigation"],
        auditRefs: [
          { id: "first-contentful-paint", weight: 10 },
          { id: "largest-contentful-paint", weight: 25 },
          { id: "total-blocking-time", weight: 30 },
          { id: "cumulative-layout-shift", weight: 25 },
          { id: "speed-index", weight: 10 },
        ],
      },
      a11y: {
        title: "Accessibility",
        supportedModes: ["navigation"],
        auditRefs: [],
      },
      "best-practices": {
        title: "Best Practices",
        supportedModes: ["navigation"],
        auditRefs: [],
      },
      seo: {
        title: "SEO",
        supportedModes: ["navigation"],
        auditRefs: [],
      },
    },
  };
}

export { CHROME_PATH, BASE_URL };
```

```powershell
# scripts/perf-audit.ps1
# Usage: .\scripts\perf-audit.ps1 [--mobile] [--url http://localhost:3000]
param(
  [switch]$Mobile,
  [string]$Url,
  [string]$ChromePath,
  [string]$OutputDir
)

$ErrorActionPreference = "Stop"

$BASE_URL = if ($Url) { $Url } else { $env:LH_BASE_URL ?? "http://localhost:3000" }
$CHROME = if ($ChromePath) { $ChromePath } else { $env:LH_CHROME_PATH }
$OUT = if ($OutputDir) { $OutputDir } else { "lighthouse-reports" }

# Create report directory
New-Item -ItemType Directory -Path $OUT -Force | Out-Null

# Resolve chrome path from common locations
if (-not $CHROME) {
  $candidates = @(
    "$env:ProgramFiles\Google\Chrome\Application\chrome.exe",
    "${env:ProgramFiles(x86)}\Google\Chrome\Application\chrome.exe",
    "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe",
    "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
  )
  foreach ($c in $candidates) {
    if (Test-Path $c) { $CHROME = $c; break }
  }
}

if (-not $CHROME) {
  Write-Host "[perf-audit] ERROR: Chrome not found. Set LH_CHROME_PATH." -ForegroundColor Red
  exit 1
}

Write-Host "`n[perf-audit] Auditing $BASE_URL"
Write-Host "[perf-audit] Chrome: $CHROME"
Write-Host "[perf-audit] Mode: $(if ($Mobile) { 'mobile' } else { 'desktop' })`n"

$categories = "performance,a11y,best-practices,seo"
$modeFlag = if (-not $Mobile) { "--preset=desktop" } else { "" }

$stamp = Get-Date -Format "yyyyMMdd-HHmmss"
$suffix = if ($Mobile) { "mobile" } else { "desktop" }

$urlSafeName = $BASE_URL -replace '[^a-zA-Z0-9]', '_'

# Run Lighthouse
npx lighthouse `
  $BASE_URL `
  --form-factor=$(if ($Mobile) { "mobile" } else { "desktop" }) `
  --output=json `
  --output=html `
  --output-path="$OUT\$urlSafeName-$suffix-$stamp" `
  --quiet `
  --chrome-flags="--headless --no-sandbox --disable-dev-shm-usage" `
  --chrome-path="$CHROME" `
  --only-categories=$categories `
  $modeFlag

if ($LASTEXITCODE -ne 0) {
  Write-Host "[perf-audit] ERROR: Lighthouse exited with code $LASTEXITCODE" -ForegroundColor Red
  exit $LASTEXITCODE
}

# Parse the JSON report
$jsonPath = "$OUT\$urlSafeName-$suffix-$stamp.report.json"
if (Test-Path $jsonPath) {
  $report = Get-Content $jsonPath | ConvertFrom-Json

  Write-Host "`n=== Lighthouse Audit Summary ===" -ForegroundColor Cyan
  foreach ($cat in @("performance", "accessibility", "best-practices", "seo")) {
    $score = $report.categories.$cat.score
    $pct = [math]::Round($score * 100)
    $color = if ($pct -ge 90) { "Green" } elseif ($pct -ge 50) { "Yellow" } else { "Red" }
    Write-Host ("{0,-16} {1,3}/100" -f $cat, $pct) -ForegroundColor $color
  }

  Write-Host "`n=== Core Web Vitals ===" -ForegroundColor Cyan
  $audits = $report.audits
  Write-Host ("{0,-28} {1}" -f "Largest Contentful Paint:", $audits."largest-contentful-paint".displayValue)
  Write-Host ("{0,-28} {1}" -f "Cumulative Layout Shift:", $audits."cumulative-layout-shift".displayValue)
  Write-Host ("{0,-28} {1}" -f "Total Blocking Time:", $audits."total-blocking-time".displayValue)
  Write-Host ("{0,-28} {1}" -f "First Contentful Paint:", $audits."first-contentful-paint".displayValue)
}

Write-Host "`n[perf-audit] Reports written to: $OUT`n" -ForegroundColor Green
```

```typescript
// next.config.ts
import type { NextConfig } from "next";

const withBundleAnalyzer = require("@next/bundle-analyzer")({
  enabled: process.env.ANALYZE === "true",
  openAnalyzer: false,
  analyzerMode: "static",
  reportFilename: "../../reports/bundle-[name].html",
});

const nextConfig: NextConfig = {
  output: "standalone",
  reactStrictMode: true,
  poweredByHeader: false,
  compress: false, // handled by reverse proxy (gzip) — Lighthouse measures unzipped cost
  experimental: {
    optimizePackageImports: ["lucide-react", "date-fns", "recharts"],
  },
  images: {
    formats: ["image/avif", "image/webp"],
    deviceSizes: [320, 420, 768, 1024, 1280, 1536, 1920],
    imageSizes: [16, 32, 48, 64, 96, 128, 256],
    minimumCacheTTL: 60 * 60 * 24 * 30,
    remotePatterns:
      process.env.NEXT_PUBLIC_IMAGE_HOST
        ? [
            {
              protocol: "https",
              hostname: process.env.NEXT_PUBLIC_IMAGE_HOST,
            },
          ]
        : [],
  },
  headers: () => [
    {
      source: "/:path*",
      headers: [
        { key: "X-Frame-Options", value: "SAMEORIGIN" },
        { key: "X-Content-Type-Options", value: "nosniff" },
        { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
      ],
    },
    {
      source: "/_next/static/(.*)",
      headers: [
        { key: "Cache-Control", value: "public, max-age=31536000, immutable" },
      ],
    },
  ],
};

module.exports = withBundleAnalyzer(nextConfig);
```

```tsx
// src/components/LazyChart.tsx
import { lazy, Suspense, useState } from "react";

// Code-split the heavy charting library — loaded only when needed
const RevenueChart = lazy(() =>
  import("./RevenueChart").then((module) => ({
    default: module.RevenueChartComponent,
  }))
);

const AnalyticsTable = lazy(() =>
  import("./AnalyticsTable").then((module) => ({
    default: module.AnalyticsTableComponent,
  }))
);

function ChartLoaderFallback() {
  return (
    <div
      data-testid="chart-loading"
      style={{
        minHeight: 320,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--surface-1)",
        borderRadius: 12,
      }}
      role="status"
      aria-live="polite"
    >
      <span>Loading analytics…</span>
    </div>
  );
}

export function LazyChart() {
  const [showChart, setShowChart] = useState(false);

  if (!showChart) {
    return (
      <button
        type="button"
        onClick={() => setShowChart(true)}
        data-testid="load-chart"
      >
        View Revenue Analytics
      </button>
    );
  }

  return (
    <Suspense fallback={<ChartLoaderFallback />}>
      <section aria-label="Analytics">
        <RevenueChart />
        <AnalyticsTable />
      </section>
    </Suspense>
  );
}

// LCP-critical: inline this instead of lazy-loading
export { CriticalHero as CriticalHero } from "./CriticalHero";
```

```tsx
// src/components/CriticalHero.tsx
import Image from "next/image";

// LCP element — prioritize, do NOT lazy-load, use next/image for multi-format delivery
export function CriticalHero() {
  return (
    <section className="hero" data-testid="hero">
      <Image
        src="/images/hero-1920.webp"
        alt="Product showcase banner"
        width={1920}
        height={1080}
        priority
        sizes="(max-width: 768px) 100vw, 80vw"
        quality={75}
        placeholder="blur"
        blurDataURL="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHdpZHRoPSIxOTIwIiBoZWlnaHQ9IjEwODAiPjxyZWN0IHdpZHRoPSIxMDAlIiBoZWlnaHQ9IjEwMCUiIGZpbGw9IiNkZmUzZTgiLz48L3N2Zz4="
      />
      <h1 className="hero-title" style={{ fontFamily: "'Inter', sans-serif" }}>
        Instant performance, delivered.
      </h1>
    </section>
  );
}
```

```typescript
// src/lib/reportWebVitals.ts
"use client";

import { useReportWebVitals, type WebVitalsMetric } from "next/web-vitals";
import { useEffect } from "react";

type CWVName = "LCP" | "CLS" | "INP" | "FCP" | "TTFB";

const CWV_THRESHOLDS: Record<CWVName, { good: number; poor: number }> = {
  LCP: { good: 2500, poor: 4000 },
  INP: { good: 200, poor: 500 },
  CLS: { good: 0.1, poor: 0.25 },
  FCP: { good: 1800, poor: 3000 },
  TTFB: { good: 800, poor: 1800 },
};

const PASSPHRASE = "webvitals-1/" + (process.env.NEXT_PUBLIC_APP_VERSION ?? "dev");
const QUEUE: Array<Record<string, unknown>> = [];
const MAX_QUEUE = 100;
let sessionId = "";

function ratingFor(metricName: CWVName, value: number): "good" | "needs-improvement" | "poor" {
  const thresholds = CWV_THRESHOLDS[metricName];
  if (value <= thresholds.good) return "good";
  if (value <= thresholds.poor) return "needs-improvement";
  return "poor";
}

function sanitizePath(path: string): string {
  // Normalize dynamic segments so the metric is bucketed by route pattern
  return path
    .replace(/\/\d+/g, "/:id")
    .replace(/\/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/gi, "/:uuid");
}

function queueEntry(metric: WebVitalsMetric | { name: string; value: number }): void {
  const name = metric.name as CWVName;
  const value = Number(metric.value.toFixed(3));

  const entry: Record<string, unknown> = {
    name,
    value,
    rating: ratingFor(name, value),
    delta: Number((metric as any).delta?.toFixed(3) ?? 0),
    path: sanitizePath(window.location.pathname),
    navigation_type: (performance.getEntriesByType("navigation")[0] as PerformanceNavigationTiming)
      ?.type ?? "",
    dpr: window.devicePixelRatio || 1,
    viewport: `${window.innerWidth}x${window.innerHeight}`,
    connection: (navigator as any).connection?.effectiveType ?? "",
    session: sessionId,
    t: performance.now(),
  };

  QUEUE.push(entry);
  if (QUEUE.length > MAX_QUEUE) {
    flush();
  }
}

async function flush(): Promise<void> {
  if (QUEUE.length === 0) return;
  const batch = QUEUE.splice(0, QUEUE.length);

  // In production, these entries are published to your analytics endpooint
  // e.g. fetch("/api/analytics/web-vitals", { method: "POST", body: JSON.stringify(batch) })
  // Ship via a keep-alive request or a navigator.sendBeacon batch.
  if ("sendBeacon" in navigator && batch.length > 0) {
    const beacon = new URL("/api/analytics/web-vitals", window.location.origin);
    const sent = navigator.sendBeacon(beacon.href, new Blob([JSON.stringify(batch)], { type: "application/json" }));
    if (!sent) {
      fetch(beacon.href, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(batch),
        keepalive: true,
      }).catch(() => {});
    }
  }
}

// ── Next.js App Router instrumentation hook ────────────────────

export function WebVitalsReporter() {
  useReportWebVitals((metric) => {
    // Ensure palette/stats loaded before capturing
    if (typeof window === "undefined") return;

    if (!sessionId) {
      sessionId = crypto.randomUUID().slice(0, 8);
    }

    queueEntry(metric);

    // Debug logging in development
    if (process.env.NODE_ENV !== "production") {
      console.debug(`[web-vitals] ${metric.name}: ${metric.value.toFixed(2)}ms`);
      console.debug(`[web-vitals] Rating: ${ratingFor(metric.name as CWVName, metric.value)}`);
    }
  });

  // Top-level flush on visibilitychange (fires during page hide for bfcache)
  useEffect(() => {
    const onHide = () => flush();
    document.addEventListener("visibilitychange", onHide);
    return () => document.removeEventListener("visibilitychange", onHide);
  }, []);

  return null;
}

// ── Compatibility reporter for Pages Router / manual use ───────
// reportWebVitals(metric => ...) maps directly to the same queue.

export function reportWebVitals(metric: WebVitalsMetric): void {
  if (typeof window === "undefined") return;
  if (!sessionId) sessionId = crypto.randomUUID().slice(0, 8);
  queueEntry(metric);
}

export { PASSPHRASE };

// ── Manual introspection for debugging ─────────────────────────

export function debugCwvSummary(): void {
  if (typeof window === "undefined") return;
  const entries = performance.getEntriesByType("paint").concat(
    performance.getEntriesByName("next-route-change-to-render")
  );

  const lcpEntries = performance.getEntriesByType("largest-contentful-paint");
  const clsEntry = performance.getEntriesByType("layout-shift")
    .map((e) => (e as any).hadRecentInput)
    .filter((x) => !x);

  console.debug("[web-vitals] Paints:", entries);
  console.debug("[web-vitals] LCP:", lcpEntries.at(-1));
  console.debug("[web-vitals] CLS entries:", clsEntry.length);
}
```

```tsx
// src/app/layout.tsx (snippet — integration point)
import { WebVitalsReporter } from "@/lib/reportWebVitals";

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        {/* Critical CSS — framework-inlined or manually embedded */}
        <link
          rel="preload"
          href="/fonts/inter-latin.woff2"
          as="font"
          type="font/woff2"
          crossOrigin="anonymous"
        />
        <style dangerouslySetInnerHTML={{ __html: `
          :root { --font-sans: 'Inter', system-ui, sans-serif; }
          html { scroll-behavior: smooth; }
          body { margin: 0; font-family: var(--font-sans); }
          .hero-title { font-size: clamp(1.5rem, 4vw, 3.5rem); line-height: 1.1; }
          .loading-fallback { min-height: 100vh; }
          @media (prefers-reduced-motion: reduce) { * { animation: none !important; transition: none !important; } }
        ` }} />
      </head>
      <body>
        {children}
        <WebVitalsReporter />
      </body>
    </html>
  );
}
```

```tsx
// app/loading.tsx (route-level Suspense boundary)
export default function Loading() {
  return (
    <div className="loading-fallback" role="status" aria-label="Loading page">
      <div className="skeleton skeleton-title" />
      <div className="skeleton skeleton-card" />
      <span className="sr-only">Loading content…</span>
      <style>{`
        .skeleton { background: linear-gradient(90deg, rgba(0,0,0,.06) 25%, rgba(0,0,0,.12) 37%, rgba(0,0,0,.06) 63%); background-size: 400% 100%; animation: shimmer 1.4s ease infinite; border-radius: 8px; }
        .skeleton-title { width: 60%; height: 2rem; margin-bottom: 1rem; }
        .skeleton-card { width: 100%; height: 12rem; }
        @keyframes shimmer { 0% { background-position: 100% 0; } 100% { background-position: -100% 0; } }
        .sr-only { position: absolute; width: 1px; height: 1px; overflow: hidden; clip: rect(0 0 0 0); white-space: nowrap; }
      `}</style>
    </div>
  );
}
```

## 4. Execution Protocol & Step-by-Step Workflow

```bash
# 1. Install all tooling dependencies
npm install web-vitals
npm install -D lighthouse chrome-launcher @next/bundle-analyzer

# 2. Run the dev server (separate terminal)
npm run dev

# 3. Run a Lighthouse audit (Windows PowerShell)
powershell -File scripts/perf-audit.ps1 --mobile
# or desktop:
powershell -File scripts/perf-audit.ps1

# 4. Inspect the HTML report (opens in browser)
start lighthouse-reports/*.report.html

# 5. Analyze client-side bundle sizes
npx cross-env ANALYZE=true next build
# Writes bundle report to reports/bundle-*.html

# 6. Direct webpack-bundle-analyzer against a stats file
npx next build --stats
npx webpack-bundle-analyzer .next/stats.json

# 7. Instrument Core Web Vitals reporting
#    - Add <WebVitalsReporter /> to root layout
#    - Verify dev console shows [web-vitals] lines

# 8. Measure real-user LCP/CLS/INP
#    Endpoint /api/analytics/web-vitals receives beacon batches:
#    { name, value, rating, delta, path, navigation_type, dpr, viewport, connection, session, t }

# 9. Verify production build + local audit
npm run build
powershell -File scripts/perf-audit.ps1 --mobile --url http://localhost:3000
```

## 5. Edge Cases & Error Handling

- **Throttling accuracy:** Lighthouse `simulate` mode is an estimate; always verify LCP/CLS against real-user data (`web-vitals` beacons) before shipping. Different CPUs yield dramatical differences under `cpuSlowdownMultiplier`.
- **Chrome path discovery:** If Chrome is not auto-detected, set `LH_CHROME_PATH` explicitly. On serverless CI runners, install a headless shell via `npx puppeteer browsers install chrome-headless-shell`.
- **Bundle analyzer clashes with LRU caches:** Safari prefetches `_next/static` aggressively; the `Cache-Control: immutable` header is mandatory so ICB caching doesn't revalidate on every route change.
- **AVIF fallback:** Older Safari (<16.4) lacks AVIF decode; `next/image` negotiates `accept` headers automatically but only when you pass BOTH `webp` and `avif` in `images.formats`.
- **CLS from async injections:** Reserve stable height for lazy-loaded charts (see the fixed `minHeight: 320` fallback in `LazyChart`). Failing to reserve space causes a CLS spike captured by Lighthouse.
- **Critical CSS inlining size caps:** Inlined `<style>` blocks over ~14KB can push the HTML document into a second request. Keep the critical style fragment minimal; defer the rest to the Async CSS in `app/layout.tsx`.
- **`sendBeacon` quota:** Browsers cap beacon payloads (~64KB). The queue flush batches ≤ 100 entries and falls back to `fetch(..., { keepalive: true })`; still, truncate the `path` to ≤ 140 chars before batching.
- **Cross-session drift in snapshots:** Fonts load asynchronously — snapshot tests must await `document.fonts.ready` in a fixture, or the first-visit baseline disagrees with warm-visit runs.
- **Rollback:** Keep the previous `next.config.ts` + header set under version control. If an optimization regresses TBT (e.g., preload fonts before CSS), revert the specific change and re-run the audit; never ship an untested optimization directly to production.
