import { test, expect } from '../../frontend/node_modules/@playwright/test/index.mjs';
import { spawn, spawnSync, type ChildProcess } from 'node:child_process';
import { readFileSync, mkdirSync, mkdtempSync, symlinkSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const project = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const evaluation = process.env.VOICETRAIL_EVALUATION;
const modelCache = process.env.VOICETRAIL_MODEL_CACHE;
const python = process.env.VOICETRAIL_PYTHON ?? join(project, '.venv/bin/python');
const port = 8791;
const url = `http://127.0.0.1:${port}`;

test('real import, index, reference, search, playback, review, export and restart', async ({ page, browserName, browser }) => {
  if (!evaluation || !modelCache) {
    throw new Error('Real E2E requires VOICETRAIL_EVALUATION and VOICETRAIL_MODEL_CACHE; no mock fallback.');
  }
  const runtime = mkdtempSync(join(tmpdir(), 'voicetrail-e2e-'));
  mkdirSync(join(runtime, 'models'));
  // Resolve the fixed cache revision through a directory symlink; weights never enter Git.
  const revision = '0f99f2d0ebe89ac095bcc5903c4dd8f72b367286';
  symlinkSync(join(modelCache, revision), join(runtime, 'models', revision), 'dir');
  let service: ChildProcess | undefined;
  const errors: string[] = [];
  page.on('pageerror', error => errors.push(error.message));
  const report: Record<string, unknown> = {
    browser: browserName, browser_version: browser.version(), real_model: true,
    model_revision: revision,
  };

  function start() {
    service = spawn(python, ['-m', 'scripts.dev'], {
      cwd: project, env: { ...process.env, VOICETRAIL_DATA: runtime, VOICETRAIL_PORT: String(port),
        HF_HUB_OFFLINE: '1', VOICETRAIL_DEV_UI: '0' }, stdio: 'ignore',
    });
  }
  async function stop(signal: NodeJS.Signals = 'SIGTERM') {
    if (!service || service.exitCode !== null) return;
    const process = service;
    await new Promise<void>((done, reject) => {
      const deadline = setTimeout(() => reject(new Error('Service did not stop')), 15_000);
      process.once('exit', () => { clearTimeout(deadline); done(); });
      process.kill(signal);
    });
    service = undefined;
  }
  async function load() {
    await expect.poll(async () => {
      try { return (await fetch(`${url}/api/health`)).status; } catch { return 0; }
    }, { timeout: 60_000 }).toBe(200);
    await page.goto(url);
    await expect(page.getByText('CPU 模型就绪', { exact: true })).toBeVisible({ timeout: 60_000 });
  }
  async function search() {
    await page.getByRole('button', { name: '检索相似声音 →', exact: true }).click();
    await expect(page.locator('article.candidate').first()).toBeVisible();
    await expect(page.locator('article.candidate').first()).toContainText('2277-149897-0005');
  }
  async function index() {
    await page.getByRole('button', { name: '建立 / 更新索引', exact: true }).click();
  }

  try {
    start(); await load();
    await page.getByLabel('本地文件夹路径', { exact: true }).fill(join(evaluation, 'ui-library'));
    await page.getByRole('button', { name: '添加资料', exact: true }).click();
    await expect(page.getByLabel('已登记资料', { exact: true })).toContainText('ui-library');

    // Real queued cancellation, then real crash during index work and explicit recovery.
    await index();
    await page.locator('.job-list .job').first().getByRole('button', { name: '取消' }).click();
    await expect(page.locator('.job-list .job').first()).toHaveAttribute('data-status', 'cancelled');
    await index();
    await expect.poll(async () => {
      const jobs = await (await fetch(`${url}/api/jobs`)).json();
      return jobs.some((job: { kind: string; status: string }) =>
        job.kind === 'index' && job.status === 'running');
    }, { intervals: [30, 50, 100] }).toBe(true);
    await stop('SIGKILL');
    start(); await load();
    const interrupted = page.locator('.job[data-status="interrupted"]');
    await expect(interrupted).toBeVisible();
    await interrupted.getByRole('button', { name: '重试' }).click();
    await expect(page.getByText('3 / 5 个文件已索引', { exact: true })).toBeVisible();
    await page.getByText('查看文件状态（5）', { exact: true }).click();
    await expect(page.locator('.asset-list')).toContainText('无音轨 video.mp4');
    await expect(page.locator('.asset-list')).toContainText('This file has no audio track.');
    await expect(page.locator('.asset-list .failed')).toHaveCount(2);
    report.cancel_and_forced_restart_recovery = true;

    // UI must surface real too-short, silence and no-audio failures.
    await page.locator('#reference-file').setInputFiles(join(evaluation, 'short-reference.wav'));
    await expect(page.getByRole('alert')).toContainText('3–60 seconds');
    await page.locator('#reference-file').setInputFiles(join(evaluation, 'silence-reference.wav'));
    await expect(page.getByRole('alert')).toContainText('Insufficient speech');
    await page.locator('#reference-file').setInputFiles(join(evaluation, 'ui-library/无音轨 video.mp4'));
    await expect(page.getByRole('alert')).toContainText('no audio track');
    report.short_silence_no_audio_errors = true;

    await page.locator('#reference-file').setInputFiles(join(evaluation, 'references/2277-149896-0032.flac'));
    await expect(page.getByLabel('已保存的参考', { exact: true })).toContainText('2277-149896-0032');
    await search();
    const first = page.locator('article.candidate').first();
    await first.getByRole('button', { name: '▷ 回听', exact: true }).click();
    await expect(first.locator('audio')).toBeVisible();
    await first.locator('audio').evaluate((audio: HTMLAudioElement) => audio.play());
    await expect.poll(() => first.locator('audio').evaluate((a: HTMLAudioElement) => a.currentTime)).toBeGreaterThan(.2);
    await first.locator('audio').evaluate((a: HTMLAudioElement) => a.pause());
    const playback = await first.locator('audio').evaluate((a: HTMLAudioElement) => ({
      duration: a.duration, currentTime: a.currentTime, readyState: a.readyState, error: a.error?.code ?? null,
    }));
    report.original_preview_playback = playback;
    await first.getByRole('button', { name: '确认', exact: true }).click();
    await expect(first).toHaveAttribute('data-review', 'confirmed');
    await page.locator('article.candidate').nth(1).getByRole('button', { name: '排除', exact: true }).click();
    await expect(page.locator('article.candidate').nth(1)).toHaveAttribute('data-review', 'rejected');
    await page.getByRole('checkbox', { name: '选择片段 1', exact: true }).check();
    await page.getByRole('button', { name: '导出所选片段 ↗', exact: true }).click();
    await expect(page.getByRole('link', { name: '下载 ZIP', exact: true })).toBeVisible();
    const downloadPromise = page.waitForEvent('download');
    await page.getByRole('link', { name: '下载 ZIP', exact: true }).click();
    const download = await downloadPromise;
    const zip = join(runtime, 'browser-download.zip');
    await download.saveAs(zip);
    const unpack = spawnSync(python, ['-c',
      'import zipfile,json,sys; z=zipfile.ZipFile(sys.argv[1]); m=json.loads(z.read("manifest.json")); z.extract(m["clips"][0]["export_file"],sys.argv[2]); print(json.dumps(m))',
      zip, runtime], { encoding: 'utf8' });
    expect(unpack.status).toBe(0);
    const manifest = JSON.parse(unpack.stdout);
    expect(manifest.clips[0].source_name).toContain('2277-149897-0005');
    const base64 = readFileSync(join(runtime, manifest.clips[0].export_file)).toString('base64');
    await page.evaluate(async (encoded) => {
      const bytes = Uint8Array.from(atob(encoded), c => c.charCodeAt(0));
      const audio = document.createElement('audio');
      audio.id = 'verified-export-audio'; audio.controls = true;
      audio.src = URL.createObjectURL(new Blob([bytes], { type: 'audio/wav' }));
      document.querySelector('#results')!.append(audio);
      await audio.play();
    }, base64);
    await expect.poll(() => page.locator('#verified-export-audio').evaluate((a: HTMLAudioElement) => a.currentTime))
      .toBeGreaterThan(.2);
    report.export_playback = await page.locator('#verified-export-audio').evaluate((a: HTMLAudioElement) => ({
      duration: a.duration, readyState: a.readyState, currentTime: a.currentTime, error: a.error?.code ?? null,
    }));
    await page.locator('#verified-export-audio').evaluate((a: HTMLAudioElement) => { a.pause(); a.remove(); });
    report.export_manifest = manifest;
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: join(project, 'docs/ui-desktop.png'), fullPage: true });

    await stop(); start(); await load();
    await search();
    await expect(page.locator('article.candidate').first()).toHaveAttribute('data-review', 'confirmed');
    await expect(page.locator('article.candidate').nth(1)).toHaveAttribute('data-review', 'rejected');
    await expect(page.getByRole('link', { name: '下载 ZIP' })).toBeVisible();
    report.restart_persistence = true;
    await page.setViewportSize({ width: 390, height: 844 });
    await expect(page.getByRole('button', { name: '检索相似声音 →', exact: true })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
    await page.getByRole('button', { name: '检索相似声音 →', exact: true }).focus();
    await page.keyboard.press('Enter');
    await expect(page.locator('article.candidate').first()).toBeVisible();
    report.narrow_viewport_width = 390; report.keyboard_search = true;
    await page.evaluate(() => window.scrollTo(0, 0));
    await page.screenshot({ path: join(project, 'docs/ui-mobile.png'), fullPage: true });
    expect(errors).toEqual([]);
    report.passed = true; report.javascript_errors = errors;
    writeFileSync(join(project, 'docs/e2e_results.json'), JSON.stringify(report, null, 2) + '\n');
  } finally { await stop(); }
});
