import { test, expect } from '@playwright/test'
import path from 'node:path'

// Phase 1 primary journey, run against the LIVE app at http://localhost:8001/app/:
//   create workspace -> upload CSV -> see schema preview -> ask a question ->
//   see a plain-language answer -> expand "Show code" and see pandas.
// Also asserts the later-phase surfaces are present as visibly-disabled,
// clearly-labelled "coming soon" stubs.
//
// The fixture loans.csv has PII-ish columns (name, PAN, aadhaar, phone, email,
// account_number) and a numeric column `outstanding_principal` whose full-data
// total is 11,785,000 — used to verify a real computed answer is returned.

const CSV_FIXTURE = path.join(__dirname, 'fixtures', 'loans.csv')

test('Phase 1: create workspace, upload CSV, ask, and see answer + code', async ({ page }) => {
  await page.goto('/app/')

  // The shell is loaded and styled (sidebar present).
  await expect(page.getByTestId('new-workspace-button')).toBeVisible()

  // --- Create a workspace ---
  const workspaceName = `Q2 loan book ${Date.now()}`
  await page.getByTestId('new-workspace-button').click()
  await expect(page.getByTestId('new-workspace-modal')).toBeVisible()
  await page.getByTestId('workspace-name-input').fill(workspaceName)
  await page.getByTestId('workspace-create-submit').click()

  // Modal closes; the workspace is selected and its title shows.
  await expect(page.getByTestId('new-workspace-modal')).toBeHidden()
  await expect(page.getByTestId('workspace-title')).toHaveText(workspaceName)
  // It also appears in the sidebar list.
  await expect(
    page.locator('[data-testid="workspace-item"]', { hasText: workspaceName }),
  ).toBeVisible()

  // Before upload, asking is gated with a clear hint.
  await expect(page.getByTestId('no-dataset-hint')).toBeVisible()

  // --- Upload the CSV ---
  await page.getByTestId('file-input').setInputFiles(CSV_FIXTURE)

  // Schema preview appears with real content: filename, row count, and columns.
  const schema = page.getByTestId('schema-preview')
  await expect(schema).toBeVisible({ timeout: 30_000 })
  await expect(page.getByTestId('dataset-filename')).toContainText('loans.csv')
  await expect(page.getByTestId('dataset-row-count')).toHaveText('12')

  // Real column names from the CSV are rendered in the schema table.
  const colNames = page.getByTestId('schema-col-name')
  await expect(colNames.filter({ hasText: 'outstanding_principal' })).toBeVisible()
  await expect(colNames.filter({ hasText: 'customer_name' })).toBeVisible()

  // PII columns are detected and surfaced as a masked badge.
  const piiBadge = page.getByTestId('pii-badge')
  await expect(piiBadge).toBeVisible()
  await expect(piiBadge).toContainText(/PII masked/i)

  // --- Ask a question ---
  await expect(page.getByTestId('ask-input')).toBeEnabled()
  await page.getByTestId('ask-input').fill('What is the total outstanding principal?')
  await page.getByTestId('ask-submit').click()

  // A plain-language answer with real content appears.
  const answerCard = page.getByTestId('answer-card')
  await expect(answerCard).toBeVisible({ timeout: 90_000 })
  const answerText = page.getByTestId('answer-text')
  await expect(answerText).not.toHaveText('')
  // The answer should reference the computed total (11,785,000) in some digit form.
  await expect(answerText).toContainText(/11[.,]?785[.,]?000|11,785,000|1\.1785e\+07|1178500/)

  // --- Expand "Show code" and see the pandas that ran ---
  await page.getByTestId('show-code-toggle').click()
  const codePanel = page.getByTestId('code-panel')
  await expect(codePanel).toBeVisible()
  // The sandbox contract requires the frame `df` and assigning to `result`.
  await expect(codePanel).toContainText('df')
  await expect(codePanel).toContainText('result')
})

test('Phase 1: later-phase surfaces are present as labelled, disabled stubs', async ({ page }) => {
  await page.goto('/app/')

  // Create + open a workspace so the main panel (with its stubs) renders.
  const workspaceName = `Stub check ${Date.now()}`
  await page.getByTestId('new-workspace-button').click()
  await page.getByTestId('workspace-name-input').fill(workspaceName)
  await page.getByTestId('workspace-create-submit').click()
  await expect(page.getByTestId('workspace-title')).toHaveText(workspaceName)

  // Run-history and notes stubs are always present in an open workspace.
  const stubTitles = ['Run history', 'Notes & business rules']
  for (const title of stubTitles) {
    const stub = page.locator(`[data-testid="stub"][data-stub-title="${title}"]`)
    await expect(stub).toBeVisible()
    await expect(stub).toContainText(/coming soon/i)
    await expect(stub).toHaveAttribute('aria-disabled', 'true')
  }

  // Stub buttons (export, save-derived, sheet picker, etc.) are disabled.
  const stubButtons = page.getByTestId('stub-button')
  const count = await stubButtons.count()
  expect(count).toBeGreaterThan(0)
  for (let i = 0; i < count; i++) {
    await expect(stubButtons.nth(i)).toBeDisabled()
  }
})
