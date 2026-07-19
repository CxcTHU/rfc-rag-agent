import { readFileSync } from 'node:fs'
import path from 'node:path'
import { expect, test, type Page } from '@playwright/test'

type WorkflowPersistenceCase = {
  id: string
  question: string
  expectedAnswer: string
  expectedStepCount: number
  recovery: 'reload' | 'reauth'
}

const cases = JSON.parse(
  readFileSync(path.resolve(process.cwd(), 'e2e/fixtures/workflow-persistence-cases.json'), 'utf8'),
) as WorkflowPersistenceCase[]

async function login(page: Page) {
  await page.goto('/')
  await page.locator('.auth-screen button').first().click()
  await page.locator('.auth-form input').nth(0).fill('mock-user')
  await page.locator('.auth-form input').nth(1).fill('fake-password')
  await page.locator('.auth-form button[type="submit"]').click()
  await expect(page.locator('.chat-panel')).toBeVisible()
}

async function createCompletedAnswer(page: Page, evaluationCase: WorkflowPersistenceCase) {
  await page.locator('.conversation-panel button').filter({ hasText: /./ }).first().click()
  await page.locator('textarea.composer-input').fill(evaluationCase.question)
  await page.locator('form.composer').evaluate((form: HTMLFormElement) => form.requestSubmit())
  await expect(page.getByText(evaluationCase.expectedAnswer, { exact: false })).toBeVisible()
  await expect(page.locator('.message-bubble.assistant .thinking-timer.done').last()).toBeVisible()
}

async function workflowSnapshot(page: Page, expectedStepCount: number) {
  const answer = page.locator('.message-bubble.assistant').last()
  const summary = answer.locator('.thinking-summary')
  await expect(summary.locator('small')).toContainText(`${expectedStepCount} 个真实步骤`)
  await summary.click()
  const labels = await answer.locator('.thinking-step-head strong').allTextContents()
  expect(labels).toHaveLength(expectedStepCount)
  return labels
}

test.beforeEach(async ({ page }) => {
  await page.request.post('/__test/reset')
})

for (const evaluationCase of cases) {
  test(`workflow persistence eval: ${evaluationCase.id}`, async ({ page }) => {
    await login(page)
    await createCompletedAnswer(page, evaluationCase)
    const liveLabels = await workflowSnapshot(page, evaluationCase.expectedStepCount)

    if (evaluationCase.recovery === 'reauth') {
      await page.locator('.header-actions button').first().click()
      await expect(page.locator('.auth-screen')).toBeVisible()
      await login(page)
    } else {
      await page.reload()
      await expect(page.locator('.chat-panel')).toBeVisible()
    }

    await expect(page.getByText(evaluationCase.expectedAnswer, { exact: false })).toBeVisible()
    const restoredLabels = await workflowSnapshot(page, evaluationCase.expectedStepCount)
    expect(restoredLabels).toEqual(liveLabels)
  })
}
