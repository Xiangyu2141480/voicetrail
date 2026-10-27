import type { Health } from './contracts';

let sessionToken = '';

export async function request<T>(path: string, method = 'GET', body?: unknown): Promise<T> {
  const headers: Record<string, string> = {};
  if (method !== 'GET') headers['X-VoiceTrail-Session'] = sessionToken;
  const isForm = body instanceof FormData;
  if (body !== undefined && !isForm) headers['Content-Type'] = 'application/json';
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method, headers, credentials: 'same-origin',
      body: body === undefined ? undefined : isForm ? body : JSON.stringify(body),
    });
  } catch {
    throw new Error('无法连接本地服务。请确认 VoiceTrail 已启动，再刷新页面。');
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    const detail = typeof data?.detail === 'string' ? data.detail : `请求失败（${response.status}）`;
    throw new Error(detail);
  }
  if (response.headers.get('Content-Type')?.includes('audio/')) {
    return await response.blob() as T;
  }
  return await response.json() as T;
}

export async function health(): Promise<Health> {
  const result = await request<Health>('/health');
  sessionToken = result.session_token;
  return result;
}
