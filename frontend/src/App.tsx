import { useCallback, useEffect, useState } from 'react';
import { health, request } from './api';
import type {
  Asset, Candidate, Health, Job, JobCreated, Library, Reference, SearchResponse,
} from './contracts';
import { Jobs, statusLabel } from './components/Jobs';
import { Preview } from './components/Preview';

const time = (ms: number) => `${Math.floor(ms / 60000)}:${(ms / 1000 % 60).toFixed(1).padStart(4, '0')}`;

export default function App() {
  const [service, setService] = useState<Health>();
  const [libraries, setLibraries] = useState<Library[]>([]);
  const [libraryId, setLibraryId] = useState('');
  const [root, setRoot] = useState('');
  const [assets, setAssets] = useState<Asset[]>([]);
  const [refs, setRefs] = useState<Reference[]>([]);
  const [refId, setRefId] = useState('');
  const [jobs, setJobs] = useState<Job[]>([]);
  const [candidates, setCandidates] = useState<Candidate[]>([]);
  const [selected, setSelected] = useState<Set<string>>(new Set());
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [rangeAsset, setRangeAsset] = useState('');
  const [rangeStart, setRangeStart] = useState('0');
  const [rangeEnd, setRangeEnd] = useState('15');

  const refresh = useCallback(async () => {
    const info = await health();
    setService(info);
    const [ls, rs, js] = await Promise.all([
      request<Library[]>('/libraries'), request<Reference[]>('/references'), request<Job[]>('/jobs'),
    ]);
    setLibraries(ls); setRefs(rs); setJobs(js);
    setLibraryId(current => ls.some(l => l.id === current) ? current : ls[0]?.id ?? '');
    setRefId(current => rs.some(r => r.id === current) ? current : rs[0]?.id ?? '');
  }, []);

  useEffect(() => {
    refresh().catch(exc => setError(exc.message));
    const interval = window.setInterval(() => {
      refresh().catch(exc => { setService(undefined); setError(exc.message); });
    }, 2000);
    return () => window.clearInterval(interval);
  }, [refresh]);

  useEffect(() => {
    if (!libraryId) { setAssets([]); return; }
    let active = true;
    const load = () => request<Asset[]>(`/libraries/${libraryId}/assets`)
      .then(rows => { if (active) setAssets(rows); }).catch(() => {});
    load();
    const interval = window.setInterval(load, 1500);
    return () => { active = false; window.clearInterval(interval); };
  }, [libraryId]);

  async function run(label: string, work: () => Promise<void>) {
    setBusy(label); setError(''); setNotice('');
    try { await work(); await refresh(); }
    catch (exc) { setError((exc as Error).message); }
    finally { setBusy(''); }
  }

  async function jobAction(path: string) {
    await run('更新任务', async () => { await request(path, 'POST'); });
  }

  function chooseLibrary(id: string) {
    setLibraryId(id); setCandidates([]); setSelected(new Set());
  }

  async function upload(file: File | undefined) {
    if (!file) return;
    await run('处理参考声音', async () => {
      const form = new FormData(); form.append('file', file);
      const reference = await request<Reference>('/references', 'POST', form);
      setRefId(reference.id);
      setCandidates([]);
      setNotice(`参考声音已保存：${reference.name}`);
    });
  }

  async function review(id: string, status: Candidate['review_status']) {
    await run('保存标注', async () => {
      const updated = await request<Candidate>(`/candidates/${id}`, 'PATCH', { review_status: status });
      setCandidates(rows => rows.map(row => row.id === id ? updated : row));
      setNotice('标注已保存，重启后保留。');
    });
  }

  const ready = service?.model.status === 'ready';
  const indexing = jobs.some(j => j.kind === 'index' && ['running', 'queued'].includes(j.status));
  const latestExport = jobs.find(j => j.kind === 'export');
  const completed = assets.filter(a => a.status === 'completed').length;

  return <div className="shell">
    <aside className="rail">
      <a className="brand" href="/" aria-label="VoiceTrail 首页">
        <span className="brand-mark">╎▥╎</span><span>VoiceTrail<span className="version">LOCAL · ALPHA 01</span></span>
      </a>
      <nav aria-label="工作流程">
        <a href="#library"><span>01</span> 选择资料</a>
        <a href="#reference"><span>02</span> 参考声音</a>
        <a href="#results"><span>03</span> 回听与导出</a>
      </nav>
      <div className="privacy-note"><span className="dot" /> 本地处理
        <p>原素材保持只读。模型准备后，索引与检索无需联网。</p>
      </div>
    </aside>
    <main>
      <header className="page-header">
        <div><p className="eyebrow">YOUR MEDIA. ORIGINAL VOICES.</p>
          <h1>循着声音，找到片段。</h1>
          <p className="subtitle">从你选择的影音资料中，检索与参考声音相似的原声。</p></div>
        <span className={`status-pill ${ready ? 'ready' : ''}`} role="status">
          <span className="dot" /> {ready ? 'CPU 模型就绪' : service ? '模型未就绪' : '连接本地服务…'}
        </span>
      </header>

      {error && <div role="alert" className="alert"><strong>操作未完成</strong><p>{error}</p>
        <button onClick={() => run('刷新状态', refresh)} className="text-button">刷新状态</button></div>}
      {notice && <div role="status" className="notice">{notice}</div>}

      <section className="model-strip" aria-label="运行环境">
        <div><strong>SpeechBrain ECAPA</strong><span> · CPU · 本地相似度检索</span>
          {!service?.ffmpeg && <p className="inline-error">需要安装 FFmpeg / FFprobe 后启动服务。</p>}
          {service && !ready && <p>
            {service.model.status === 'downloading'
              ? `正在下载：${(service.model.downloaded_bytes / 1048576).toFixed(1)} MiB${
                service.model.total_bytes ? ` / ${(service.model.total_bytes / 1048576).toFixed(1)} MiB` : '（查询实际大小…）'}`
              : service.model.status === 'loading' ? '正在加载已缓存的模型…' : '首次使用需从官方来源准备固定版本模型。'}
          </p>}
          {service?.model.error && <p className="inline-error">{service.model.error}</p>}
        </div>
        {service && !ready && <button disabled={!!busy || ['loading', 'downloading'].includes(service.model.status)}
          onClick={() => run('准备模型', async () => { await request('/model/prepare', 'POST'); })}>
          准备模型</button>}
        {service && <a href={service.model.source} target="_blank" rel="noreferrer" className="source-link">模型来源 ↗</a>}
      </section>

      <div className="setup-grid">
        <section className="panel" id="library">
          <div className="section-title"><span className="step">01</span><h2>选择你的资料</h2></div>
          <p className="muted">输入明确选择的本地文件夹。支持常见音视频，不会自动扫描其他目录。</p>
          <form onSubmit={event => { event.preventDefault(); run('添加资料', async () => {
            const lib = await request<Library>('/libraries', 'POST', { root });
            chooseLibrary(lib.id); setRoot(''); setNotice(`已登记资料：${lib.name}`);
          }); }}>
            <label htmlFor="library-root">本地文件夹路径</label>
            <div className="input-row"><input id="library-root" value={root}
              onChange={event => setRoot(event.target.value)} placeholder="/path/to/my-media" required />
              <button disabled={!root.trim() || !!busy || !service}>添加资料</button></div>
          </form>
          {libraries.length > 0 && <div className="library-controls">
            <label htmlFor="library-select">已登记资料</label>
            <select id="library-select" value={libraryId} onChange={event => chooseLibrary(event.target.value)}>
              {libraries.map(lib => <option key={lib.id} value={lib.id}>{lib.name}</option>)}
            </select>
            <div className="split-row"><span className="count">{completed} / {assets.length} 个文件已索引</span>
              <button disabled={!ready || indexing || !!busy} onClick={() => run('建立索引', async () => {
                await request<JobCreated>(`/libraries/${libraryId}/index`, 'POST');
                setNotice('索引任务已加入队列，按文件逐个处理。');
              })}>{indexing ? '正在索引…' : '建立 / 更新索引'}</button></div>
          </div>}
          {assets.length > 0 && <details className="asset-details"><summary>查看文件状态（{assets.length}）</summary>
            <ul className="asset-list">{assets.map(asset => <li key={asset.id}>
              <span className="filename">{asset.relative_path}</span>
              <span className={`file-state ${asset.status}`}>{statusLabel[asset.status] ?? asset.status}</span>
              {asset.error && <p className="inline-error">{asset.error}</p>}
              <button className="text-button" disabled={!!busy || indexing || asset.status === 'removed'}
                aria-label={`移除 ${asset.relative_path}`} onClick={() => run('移除索引', async () => {
                  await request(`/assets/${asset.id}`, 'DELETE');
                  setAssets(await request<Asset[]>(`/libraries/${libraryId}/assets`));
                  setCandidates([]); setSelected(new Set()); setNotice('已移除应用索引，原素材未删除。');
                })}>移除索引</button>
            </li>)}</ul>
          </details>}
        </section>

        <section className="panel" id="reference">
          <div className="section-title"><span className="step">02</span><h2>给一个参考声音</h2></div>
          <p className="muted">建议 10–30 秒单人清晰讲话。接受 3–60 秒，至少有 3 秒有效语音。</p>
          <label className={`upload-zone ${!ready ? 'disabled' : ''}`} htmlFor="reference-file">
            <span className="upload-icon">↑</span><strong>{busy === '处理参考声音' ? '正在处理真实声音…' : '选择参考音频 / 视频'}</strong>
            <span>仅在本机保存与处理 · 最大 128 MiB</span>
            <input id="reference-file" type="file" disabled={!ready || !!busy}
              onChange={event => { upload(event.target.files?.[0]); event.target.value = ''; }} />
          </label>
          {refs.length > 0 && <><label htmlFor="reference-select">已保存的参考</label>
            <select id="reference-select" value={refId} onChange={event => {
              setRefId(event.target.value); setCandidates([]); setSelected(new Set());
            }}>{refs.map(ref => <option value={ref.id} key={ref.id}>
              {ref.name} · {(ref.duration_ms / 1000).toFixed(1)} 秒</option>)}</select></>}
          {completed > 0 && <details className="range-details"><summary>或从资料中选一段讲话</summary>
            <label htmlFor="range-asset">来源文件</label>
            <select id="range-asset" value={rangeAsset} onChange={event => setRangeAsset(event.target.value)}>
              <option value="">选择已索引文件</option>
              {assets.filter(a => a.status === 'completed').map(a =>
                <option key={a.id} value={a.id}>{a.relative_path}</option>)}
            </select>
            <div className="range-row"><label>开始（秒）<input type="number" min="0" step=".1"
              value={rangeStart} onChange={e => setRangeStart(e.target.value)} /></label>
              <label>结束（秒）<input type="number" min="0" step=".1"
                value={rangeEnd} onChange={e => setRangeEnd(e.target.value)} /></label></div>
            <button disabled={!rangeAsset || !!busy || !ready} onClick={() => run('创建参考', async () => {
              const ref = await request<Reference>('/references/from-asset', 'POST', {
                asset_id: rangeAsset, start_ms: Math.round(Number(rangeStart) * 1000),
                end_ms: Math.round(Number(rangeEnd) * 1000),
              }); setRefId(ref.id); setNotice('参考声音已保存。');
            })}>保存参考片段</button>
          </details>}
        </section>
      </div>

      <Jobs jobs={jobs} action={jobAction} />

      <section id="results" className="results">
        <div className="results-heading">
          <div className="section-title"><span className="step">03</span><div>
            <h2>相似声音候选</h2><p className="muted">按余弦相似度排序。分数不是身份概率，请回听确认。</p>
          </div></div>
          <button className="primary" disabled={!refId || !libraryId || !ready || !completed || !!busy}
            onClick={() => run('检索相似声音', async () => {
              const result = await request<SearchResponse>('/search', 'POST', {
                reference_id: refId, library_id: libraryId, top_k: 20,
              }); setCandidates(result.candidates); setSelected(new Set());
              if (!result.candidates.length) setNotice('没有可检索片段。请检查文件状态并重新建立索引。');
            })}>{busy === '检索相似声音' ? '检索中…' : '检索相似声音 →'}</button>
        </div>
        {candidates.length === 0 ? <div className="empty-state"><div className="waveform" aria-hidden="true">
          {[18, 30, 50, 26, 62, 42, 28, 54, 36, 22, 46, 18].map((height, i) =>
            <span key={i} className={`wave wave-${height}`} />)}
        </div><h3>下一段声音，从这里找到。</h3>
          <p>添加资料并完成索引，选一个参考声音，再开始检索。</p></div>
          : <div className="candidate-list">{candidates.map((row, i) => <article className="candidate"
            key={row.id} data-review={row.review_status}>
            <div className="candidate-top"><label className="selection">
              <input type="checkbox" aria-label={`选择片段 ${i + 1}`} checked={selected.has(row.id)}
                onChange={e => setSelected(previous => {
                  const next = new Set(previous); e.target.checked ? next.add(row.id) : next.delete(row.id);
                  return next;
                })} /><span className="rank">{String(i + 1).padStart(2, '0')}</span></label>
              <div className="candidate-source"><h3>{row.source_name}</h3>
                <span>{time(row.start_ms)} — {time(row.end_ms)} · 原始音轨</span></div>
              <div className="score"><strong>{row.similarity.toFixed(3)}</strong><span>余弦相似度</span></div>
            </div>
            <div className="candidate-bottom"><Preview candidate={row} />
              <div className="review-controls" role="group" aria-label={`片段 ${i + 1} 标注`}>
                <button disabled={!!busy} aria-pressed={row.review_status === 'confirmed'}
                  onClick={() => review(row.id, 'confirmed')}>确认</button>
                <button disabled={!!busy} aria-pressed={row.review_status === 'rejected'}
                  onClick={() => review(row.id, 'rejected')}>排除</button>
                <button disabled={!!busy} aria-pressed={row.review_status === 'undecided'}
                  onClick={() => review(row.id, 'undecided')}>待定</button>
              </div></div>
          </article>)}</div>}
        <div className="export-bar"><div><strong>{selected.size} 个片段已选</strong>
          <p>导出原声 WAV 与 manifest.json 来源清单。</p></div>
          <div className="export-actions">
            {latestExport?.status === 'completed' && latestExport.result_id &&
              <a className="button-link" href={`/api/exports/${latestExport.result_id}/download`} download>下载 ZIP</a>}
            <button disabled={!selected.size || !!busy ||
              (latestExport && ['queued', 'running'].includes(latestExport.status))}
              onClick={() => run('导出片段', async () => {
                await request('/exports', 'POST', { candidate_ids: [...selected] });
                setNotice('正在导出原声。完成后可下载 ZIP。');
              })}>导出所选片段 ↗</button>
          </div></div>
      </section>
      <footer>VoiceTrail v0.1.0-alpha.1 · 本地技术预览
        <p>分窗检索不等于说话人分离。重叠发言、噪声与跨年龄声音可能误检，结果需要人工确认。</p>
      </footer>
    </main>
  </div>;
}
