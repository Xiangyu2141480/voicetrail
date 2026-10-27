import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: '../tests/e2e',
  timeout: 180_000,
  expect: { timeout: 30_000 },
  workers: 1,
  retries: 0,
  use: { headless: true, viewport: { width: 1280, height: 900 } },
  reporter: 'list',
});
