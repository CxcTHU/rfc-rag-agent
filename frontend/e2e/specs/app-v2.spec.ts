import { expect, test, type Page } from '@playwright/test'

const composerSelector = 'textarea.composer-input'

async function reset(page: Page) {
  await page.request.post('/__test/reset')
}

async function login(page: Page) {
  await page.goto('/')
  await page.locator('.auth-screen button').first().click()
  await page.locator('.auth-form input').nth(0).fill('mock-user')
  await page.locator('.auth-form input').nth(1).fill('fake-password')
  await page.locator('.auth-form button[type="submit"]').click()
  await expect(page.locator('.chat-panel')).toBeVisible()
}

async function newDraft(page: Page) {
  await page.locator('.conversation-panel button').filter({ hasText: /./ }).first().click()
  await expect(page.locator('.conversation-item.draft')).toBeVisible()
}

async function sendQuestion(page: Page, question: string, expectedAnswer: string) {
  await page.locator(composerSelector).fill(question)
  await page.locator('form.composer').evaluate((form: HTMLFormElement) => form.requestSubmit())
  await expect(page.getByText(expectedAnswer, { exact: false })).toBeVisible()
  await expect(page.locator('.message-bubble.assistant .thinking-timer.done').last()).toBeVisible()
}

test.beforeEach(async ({ page }) => {
  await reset(page)
})

test('draft creation, streaming, real thinking, message-level sources, library and Judge', async ({ page }) => {
  await login(page)
  await newDraft(page)
  expect((await (await page.request.get('/__test/state')).json()).createCount).toBe(0)

  await page.locator(composerSelector).fill('first question')
  await page.locator('form.composer').evaluate((form: HTMLFormElement) => {
    form.requestSubmit()
    form.requestSubmit()
  })
  await expect(page.getByText('first answer cites browser-test evidence', { exact: false })).toBeVisible()
  expect((await (await page.request.get('/__test/state')).json()).createCount).toBe(1)
  await expect(page.getByText('first answer source', { exact: true })).toBeVisible()

  const persistedConversation = page.locator('.conversation-item:not(.draft)').first()
  await persistedConversation.click({ button: 'right' })
  await page.locator('.conversation-context-menu button').first().click()
  await expect(persistedConversation).toContainText(/./)

  await page.locator('.thinking-summary').first().click()
  await expect(page.getByText(/Search mock corpus|Compose final answer/)).toBeVisible()
  await expect(page.getByText(/HyDE|citation repair|planning phase/i)).toHaveCount(0)

  const firstAnswer = page.locator('.message-bubble.assistant').first()
  const firstCitation = firstAnswer.locator('[data-citation-index="1"]')
  await firstCitation.click()
  await expect(page.locator('.source-card.active')).toContainText('first answer source')
  await page.locator('.source-card.active .source-card-title').click()
  await expect(firstCitation).toHaveClass(/active/)

  await sendQuestion(page, 'second question', 'second answer cites browser-test evidence')
  await expect(page.getByText('second answer source', { exact: true })).toBeVisible()
  await expect(page.getByText('first answer source', { exact: true })).toHaveCount(0)

  await firstAnswer.locator('.message-title-row').click()
  await expect(page.getByText('first answer source', { exact: true })).toBeVisible()
  await expect(page.getByText('second answer source', { exact: true })).toHaveCount(0)

  await page.locator('a[href="/library"]').click()
  await expect(page).toHaveURL(/\/library$/)
  await expect(page.getByText('Mock RFC document')).toBeVisible()
  await page.locator('.corpus-panel input').fill('not-present')
  await expect(page.locator('.empty-state')).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(/\/ask$/)
  await page.goForward()
  await expect(page).toHaveURL(/\/library$/)

  await page.locator('a[href="/quality"]').click()
  await page.getByRole('button', { name: /Judge/ }).click()
  await expect(page.getByText('0.91')).toBeVisible()
})

test('an answer without sources never falls back to a previous answer', async ({ page }) => {
  await login(page)
  await newDraft(page)
  await sendQuestion(page, 'first question with sources', 'first answer cites browser-test evidence')
  await sendQuestion(page, 'third question no sources', 'first answer has no returned sources')
  await expect(page.locator('.sources-panel .empty-state')).toBeVisible()
  await expect(page.getByText('first answer source', { exact: true })).toHaveCount(0)
  await page.locator('.message-bubble.assistant').first().locator('.message-title-row').click()
  await expect(page.getByText('first answer source', { exact: true })).toBeVisible()
  await page.locator('.message-bubble.assistant').last().locator('.message-title-row').click()
  await expect(page.locator('.sources-panel .empty-state')).toBeVisible()
})

test('Judge exposes an explicit retry state on failure', async ({ page }) => {
  await login(page)
  await newDraft(page)
  await sendQuestion(page, 'judge failure question', 'judge failure answer cites browser-test evidence')
  await page.locator('a[href="/quality"]').click()
  await page.getByRole('button', { name: /Judge/ }).click()
  await expect(page.locator('[role="alert"]')).toBeVisible()
  await expect(page.getByRole('button', { name: /retry|重新|评测/i })).toBeVisible()
})

test('logging out during deferred draft creation prevents the stale session from starting a stream', async ({ page }) => {
  await login(page)
  await newDraft(page)
  await page.locator(composerSelector).fill('logout while draft is being created')
  const createRequest = page.waitForRequest((request) => request.url().endsWith('/conversations') && request.method() === 'POST')
  await page.locator('form.composer').evaluate((form: HTMLFormElement) => form.requestSubmit())
  await createRequest
  await page.locator('.header-actions button').first().click()
  await expect(page.locator('.auth-screen')).toBeVisible()
  await page.waitForTimeout(180)
  const state = await (await page.request.get('/__test/state')).json()
  expect(state.createCount).toBe(1)
  expect(state.streamCount).toBe(0)
})

test('conversation creation failure keeps the local draft question and creates no fake messages', async ({ page }) => {
  await login(page)
  await newDraft(page)
  const composer = page.locator(composerSelector)
  await composer.fill('create failure draft question')
  await page.locator('form.composer').evaluate((form: HTMLFormElement) => form.requestSubmit())
  await expect(page.locator('[role="alert"]')).toBeVisible()
  await expect(composer).toHaveValue('create failure draft question')
  await expect(page.locator('.message-bubble')).toHaveCount(0)
  const state = await (await page.request.get('/__test/state')).json()
  expect(state.conversationCount).toBe(0)
  expect(state.streamCount).toBe(0)
})

test('direct child routes refresh and browser history remain valid', async ({ page }) => {
  await login(page)
  await page.goto('/library')
  await expect(page.locator('.corpus-panel')).toBeVisible()
  await page.reload()
  await expect(page.getByText('Mock RFC document')).toBeVisible()
  await page.goto('/trace')
  await expect(page.locator('.empty-state')).toBeVisible()
  await page.goBack()
  await expect(page).toHaveURL(/\/library$/)
})

test('mobile smoke has no horizontal page overflow and keeps composer and Sources reachable', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await login(page)
  await newDraft(page)
  await expect(page.locator(composerSelector)).toBeVisible()
  await expect(page.getByText('Sources', { exact: true })).toBeVisible()
  const dimensions = await page.evaluate(() => ({ width: window.innerWidth, scrollWidth: document.documentElement.scrollWidth }))
  expect(dimensions.scrollWidth).toBeLessThanOrEqual(dimensions.width)
})
