import { defineConfig, devices } from '@playwright/test'

export default defineConfig({
  testDir: './e2e/specs',
  fullyParallel: false,
  workers: 1,
  timeout: 30_000,
  expect: { timeout: 8_000 },
  outputDir: './test-results',
  reporter: [['list'], ['html', { outputFolder: './playwright-report', open: 'never' }]],
  use: {
    baseURL: 'http://127.0.0.1:4173',
    trace: 'retain-on-failure',
    screenshot: 'only-on-failure',
    video: 'retain-on-failure',
  },
  projects: [
    { name: 'chromium', use: { ...devices['Desktop Chrome'] } },
  ],
  webServer: {
    command: 'node e2e/mock-server.mjs',
    url: 'http://127.0.0.1:4173/__test/health',
    reuseExistingServer: false,
    timeout: 30_000,
  },
})
