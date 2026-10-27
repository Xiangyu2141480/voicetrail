import { useEffect, useRef, useState } from 'react';
import type { Candidate } from '../contracts';
import { request } from '../api';

export function Preview({ candidate }: { candidate: Candidate }) {
  const [src, setSrc] = useState('');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');
  const audio = useRef<HTMLAudioElement>(null);
  useEffect(() => () => { if (src) URL.revokeObjectURL(src); }, [src]);
  useEffect(() => {
    if (src) audio.current?.play().catch(() => setError('已加载原声，请按播放器的播放键。'));
  }, [src]);
  async function preview() {
    if (src) { await audio.current?.play().catch(() => {}); return; }
    setLoading(true);
    setError('');
    try {
      const params = new URLSearchParams({
        start_ms: String(candidate.start_ms), end_ms: String(candidate.end_ms),
        revision: candidate.source_revision,
      });
      const blob = await request<Blob>(`/assets/${candidate.asset_id}/media?${params}`);
      setSrc(URL.createObjectURL(blob));
    } catch (exc) { setError((exc as Error).message); }
    finally { setLoading(false); }
  }
  return <div className="preview">
    <button type="button" className="quiet" onClick={preview} disabled={loading}>
      {loading ? '加载原声…' : '▷ 回听'}
    </button>
    {src && <audio ref={audio} src={src} controls preload="metadata"
      aria-label={`${candidate.source_name} 原声片段`}
      onError={() => setError('浏览器无法播放这个片段，请重试或导出 WAV。')} />}
    {error && <p className="inline-error" role="alert">{error}</p>}
  </div>;
}
