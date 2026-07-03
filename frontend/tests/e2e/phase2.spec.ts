import { test, expect } from '@playwright/test'
import path from 'node:path'

// Phase 2 rich-output journey, run against the LIVE app at
// http://localhost:8001/app/ (the app + backend must already be running):
//   create workspace -> upload the regional payment-mode fixture ->
//   ask a "mix by region" question -> see a plain-language answer, the analytics
//   dashboard (KPI tiles + stacked % bars + legend), a cost badge, follow-up
//   chips, and the run listed in the (now real) run-history panel.
//
// The fixture is created by the backend slice at the repo root
// (tests/phase2/fixtures/regional_payment_modes.csv). From this spec's dir
// (frontend/tests/e2e) the repo root is three levels up.

const CSV_FIXTURE = path.resolve(
  __dirname,
  '../../../tests/phase2/fixtures/regional_payment_modes.csv',
)

test('Phase 2: mix question renders dashboard, cost, follow-ups, and run history', async ({
  page,
}) => {
  await page.goto('/app/')
  await expect(page.getByTestId('new-workspace-button')).toBeVisible()

  // --- Create a workspace ---
  const workspaceName = `Payment modes ${Date.now()}`
  await page.getByTestId('new-workspace-button').click()
  await expect(page.getByTestId('new-workspace-modal')).toBeVisible()
  await page.getByTestId('workspace-name-input').fill(workspaceName)
  await page.getByTestId('workspace-create-submit').click()
  await expect(page.getByTestId('workspace-title')).toHaveText(workspaceName)

  // --- Upload the regional payment-mode fixture ---
  await page.getByTestId('file-input').setInputFiles(CSV_FIXTURE)
  await expect(page.getByTestId('schema-preview')).toBeVisible({ timeout: 30_000 })

  // --- Ask the mix-by-region question ---
  await expect(page.getByTestId('ask-input')).toBeEnabled()
  await page.getByTestId('ask-input').fill('show the payment-mode mix by region')
  await page.getByTestId('ask-submit').click()

  // A plain-language answer appears (streamed or via non-streaming fallback).
  const answerCard = page.getByTestId('answer-card')
  await expect(answerCard).toBeVisible({ timeout: 120_000 })
  await expect(page.getByTestId('answer-text').first()).not.toHaveText('')

  // --- The analytics dashboard renders from chart_spec ---
  const dashboard = page.getByTestId('dashboard-chart').first()
  await expect(dashboard).toBeVisible()

  // >= 3 KPI stat tiles.
  await expect(async () => {
    expect(await dashboard.getByTestId('kpi-tile').count()).toBeGreaterThanOrEqual(3)
  }).toPass({ timeout: 10_000 })

  // >= 1 colored stacked-bar segment.
  expect(await dashboard.getByTestId('bar-segment').count()).toBeGreaterThanOrEqual(1)

  // A shared legend maps series -> color.
  await expect(dashboard.getByTestId('chart-legend')).toBeVisible()

  // --- Cost badge shows the real per-query cost ---
  await expect(page.getByTestId('cost-badge').first()).toBeVisible()
  await expect(page.getByTestId('cost-badge').first()).toContainText('$')

  // --- 2-3 clickable follow-up chips ---
  await expect(async () => {
    expect(await page.getByTestId('followup-chip').count()).toBeGreaterThanOrEqual(2)
  }).toPass({ timeout: 10_000 })

  // --- The run-history panel lists this run ---
  const history = page.getByTestId('run-history-panel')
  await expect(history).toBeVisible()
  await expect(async () => {
    expect(await history.getByTestId('run-history-item').count()).toBeGreaterThanOrEqual(1)
  }).toPass({ timeout: 15_000 })

  // Clicking the past run re-renders its full answer (a second answer card).
  await history.getByTestId('run-history-item').first().click()
  await expect(async () => {
    expect(await page.getByTestId('answer-card').count()).toBeGreaterThanOrEqual(2)
  }).toPass({ timeout: 15_000 })
})
