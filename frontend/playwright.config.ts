import { defineConfig, devices } from '@playwright/test'

// E2E runs against the LIVE app served by FastAPI at http://localhost:8001/app/.
// Start the backend first: `uv run --native-tls alembic upgrade head`,
// `cd frontend && pnpm build`, then from repo root `uv run python -m src`.
//
// baseURL is the origin; specs navigate to `/app/` (the static export mount).
export default defineConfig({
  testDir: './tests/e2e',
  timeout: 120_000, // real LLM calls can take several seconds per ask
  expect: { timeout: 30_000 },
  fullyParallel: false,
  workers: 1,
  reporter: [['list']],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? 'http://localhost:8001',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'chromium',
      use: { ...devices['Desktop Chrome'] },
    },
  ],
})
