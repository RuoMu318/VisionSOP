import { expect, test, type Page } from '@playwright/test'

const scenarios = [
  ['正常完成', '已关闭', '合规', 'NONE'],
  ['明确工艺 NG', '等待质量处置', '不合规', 'NONE'],
  ['缺少证据 HOLD', '暂停 · 不可验证', '不可判定', 'NONE'],
  ['系统故障 HOLD', '暂停 · 不可验证', '不可判定', 'NONE'],
  ['Cycle 中止', '已关闭', '已中止', 'NONE'],
  ['返工完成', '已关闭', '不合规', 'REWORK'],
] as const

async function runScenario(page: Page, label: string) {
  await page.getByRole('combobox', { name: '模拟场景' }).click()
  await page.locator('.ant-select-item-option').filter({ hasText: label }).click()
  await page.getByRole('button', { name: /运行场景/ }).click()
}

test.describe.configure({ mode: 'serial' })

test('renders every primary route', async ({ page }) => {
  for (const [route, heading] of [
    ['/station', 'ST01 · 装配工位 01'],
    ['/alarms', '报警中心'],
    ['/trace', 'SN 质量追溯'],
    ['/config', '受控配置'],
    ['/vision', '视觉识别模板'],
  ]) {
    await page.goto(route)
    await expect(page.getByRole('heading', { name: heading })).toBeVisible()
  }
})

test('keeps lifecycle, conformance, and disposition separate for every scenario', async ({ page }) => {
  await page.goto('/station')
  for (const [label, lifecycle, conformance, disposition] of scenarios) {
    await runScenario(page, label)
    const strip = page.getByRole('region', { name: 'Cycle 状态' })
    await expect(strip).toContainText(lifecycle)
    await expect(strip).toContainText(conformance)
    await expect(strip).toContainText(disposition)
    if (label.includes('HOLD')) await expect(strip).not.toContainText('不合规')
  }
})

test('global shell reports backend mode and a disconnected socket', async ({ page, request }) => {
  const response = await request.get('/api/v1/stations/ST01/snapshot')
  const snapshot = await response.json()
  snapshot.station.mode = 'SHADOW'
  await page.route('**/api/v1/stations/ST01/snapshot', (route) => route.fulfill({ json: snapshot }))
  await page.routeWebSocket('**/ws/v1/stations/ST01', (socket) => {
    socket.send(JSON.stringify(snapshot))
    setTimeout(() => { void socket.close({ code: 1012, reason: 'test disconnect' }) }, 100)
  })
  await page.goto('/station')
  await expect(page.getByText('SHADOW', { exact: true })).toBeVisible()
  await expect(page.getByText('边缘服务断开', { exact: true })).toBeVisible({ timeout: 5_000 })
})

test('controlled configuration shows an explicit API failure', async ({ page }) => {
  await page.route('**/api/v1/sops/**', (route) => route.fulfill({ status: 503, json: { detail: 'configuration unavailable' } }))
  await page.goto('/config')
  await expect(page.getByText('配置加载失败', { exact: true })).toBeVisible()
  await expect(page.getByText('Runtime Bundle', { exact: true })).not.toBeVisible()
})

test('station and configuration expose the camera-only visual boundary', async ({ page }) => {
  await page.goto('/station')
  await expect(page.getByText('纯视觉判定', { exact: true })).toBeVisible()
  await expect(page.getByText('执行锁紧动作（视觉确认）', { exact: true })).toBeVisible()
  await expect(page.getByText('Device IO', { exact: true })).not.toBeVisible()

  await page.goto('/config')
  await expect(page.getByText('ST01-P0-R03', { exact: true })).toBeVisible()
  await expect(page.getByText('simulated-vision', { exact: true })).toBeVisible()
  await expect(page.getByText('device Adapter', { exact: true })).not.toBeVisible()
})

test('station renders the USB camera stream when the runtime reports a live camera', async ({ page, request }) => {
  const response = await request.get('/api/v1/stations/ST01/snapshot')
  const snapshot = await response.json()
  snapshot.health.camera = 'ONLINE'
  snapshot.video = {
    kind: 'USB_MJPEG',
    status: 'ONLINE',
    stream_url: '/api/v1/cameras/ST01/stream.mjpg',
    snapshot_url: '/api/v1/cameras/ST01/snapshot.jpg',
  }
  await page.route('**/api/v1/stations/ST01/snapshot', (route) => route.fulfill({ json: snapshot }))
  await page.routeWebSocket('**/ws/v1/stations/ST01', (socket) => socket.send(JSON.stringify(snapshot)))

  await page.goto('/station')

  await expect(page.getByLabel('ST01 USB 摄像头画面')).toBeVisible()
  await expect(page.getByLabel('ST01 USB 摄像头画面')).toHaveAttribute('src', '/api/v1/cameras/ST01/stream.mjpg')
  await expect(page.getByLabel('ST01 模拟相机画面')).not.toBeVisible()
})

test('alarm workflow links to cycle evidence detail', async ({ page }) => {
  await page.goto('/station')
  await runScenario(page, '明确工艺 NG')
  await page.goto('/alarms')
  await page.getByRole('button', { name: /查看证据/ }).first().click()
  await expect(page).toHaveURL(/\/trace\?cycle_id=/)
  await expect(page.getByText('Cycle 追溯详情', { exact: true })).toBeVisible()
  await expect(page.getByText('证据资产', { exact: true })).toBeVisible()
})

test('mobile station controls and navigation do not overlap', async ({ page }) => {
  await page.setViewportSize({ width: 390, height: 844 })
  await page.goto('/station')
  const toolbar = await page.locator('.simulation-toolbar').boundingBox()
  const navigation = await page.getByRole('navigation', { name: '主导航' }).boundingBox()
  expect(toolbar).not.toBeNull()
  expect(navigation).not.toBeNull()
  expect((toolbar?.y ?? 0) + (toolbar?.height ?? 0)).toBeLessThan(navigation?.y ?? 0)
  await expect(page.getByLabel('ST01 模拟相机画面')).toBeVisible()
})
