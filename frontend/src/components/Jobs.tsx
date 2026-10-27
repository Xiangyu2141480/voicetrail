import type { Job } from '../contracts';

export const statusLabel: Record<string, string> = {
  queued: '等待中', running: '处理中', completed: '已完成', failed: '失败',
  cancelled: '已取消', interrupted: '已中断', missing: '源文件缺失', removed: '已移除',
};

export function Jobs({ jobs, action }: {
  jobs: Job[]; action: (path: string) => Promise<void>;
}) {
  if (!jobs.length) return null;
  return <section className="job-list" aria-label="后台任务">
    {jobs.slice(0, 6).map(job => <div className="job" key={job.id} data-status={job.status}>
      <div>
        <strong>{job.kind === 'index' ? '资料索引' : job.kind === 'export' ? '原声导出' : '模型准备'}</strong>
        <span> · {statusLabel[job.status] ?? job.status}
          {job.total > 0 && ` · ${job.processed}/${job.total}`}</span>
        {job.error && <p className="inline-error">{job.error}</p>}
      </div>
      {['queued', 'running'].includes(job.status) &&
        <button className="text-button" onClick={() => action(`/jobs/${job.id}/cancel`)}>取消</button>}
      {['failed', 'cancelled', 'interrupted'].includes(job.status) &&
        <button className="text-button" onClick={() => action(`/jobs/${job.id}/retry`)}>重试</button>}
    </div>)}
  </section>;
}
