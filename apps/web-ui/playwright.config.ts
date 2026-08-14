import { defineConfig, devices } from '@playwright/test'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const webRoot = fileURLToPath(new URL('.', import.meta.url))
const repoRoot = path.resolve(webRoot, '../..')
const defaultPython = process.platform === 'win32'
  ? path.join(repoRoot, '.venv', 'Scripts', 'python.exe')
  : 'python3'
const python = process.env.PLAYWRIGHT_PYTHON ?? defaultPython

export default defineConfig({
  testDir: './tests/e2e',
  outputDir: '../../output/playwright/test-results',
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: process.env.PLAYWRIGHT_BASE_URL ?? 'http://127.0.0.1:5173',
    screenshot: 'only-on-failure',
    trace: 'retain-on-failure',
  },
  webServer: [
    {
      command: `"${python}" -m uvicorn sop_api.main:app --app-dir "${path.join(repoRoot, 'services', 'api-server')}" --host 127.0.0.1 --port 8000`,
      url: 'http://127.0.0.1:8000/api/v1/health',
      reuseExistingServer: true,
      timeout: 120_000,
      env: {
        SOP_DATA_DIR: path.join(repoRoot, 'output', 'playwright', 'runtime'),
        RUNTIME_MODE: 'SIMULATION',
      },
    },
    {
      command: 'npm run dev',
      url: 'http://127.0.0.1:5173/station',
      reuseExistingServer: true,
      timeout: 120_000,
    },
  ],
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
})
