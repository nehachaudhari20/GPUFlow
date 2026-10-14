import { useState } from 'react';
import { apiPost } from '../../api';
import { useFa2Poll } from '../../hooks/useFa2Data';
import type { WorkerNode, Workload } from '../../types';
import { Badge, Card, Empty, nodeLabel, shortId } from './Fa2Ui';

interface Summary {
  epoch?: number;
  tracked_jobs?: number;
  pending_retries?: number;
  max_attempts?: number;
}

interface HistoryItem {
  timestamp: number;
  job_id: string;
  event: string;
  old_node_id?: string;
  new_node_id?: string;
  reason?: string;
}

export default function Fa2RecoveryPage({
  nodes,
  workloads,
  onChanged,
}: {
  nodes: WorkerNode[];
  workloads: Workload[];
  onChanged?: () => void;
}) {
  const summary = useFa2Poll<Summary>('/fa2/recovery/summary', 2000);
  const history = useFa2Poll<{ history: HistoryItem[] }>('/fa2/recovery/history', 2000);
  const [busy, setBusy] = useState<string | null>(null);
  const [msg, setMsg] = useState('');

  const running = workloads.filter((w) => w.status === 'RUNNING' && w.assigned_node);
  const queued = workloads.filter((w) => w.status === 'QUEUED');

  const fail = async (nodeId: string) => {
    setBusy(nodeId);
    setMsg('');
    try {
      const res = await apiPost<{
        interrupted_jobs: string[];
        new_coordinator?: string;
      }>(`/fa2/recovery/simulate-failure/${nodeId}`);
      const n = res.interrupted_jobs?.length ?? 0;
      setMsg(
        `${n} job(s) interrupted on ${nodeLabel(nodeId, nodes)}` +
          (res.new_coordinator ? ` · coordinator ${nodeLabel(res.new_coordinator, nodes)}` : '')
      );
      await history.refresh();
      await summary.refresh();
      onChanged?.();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Failed');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-4">
        <Stat label="Epoch" value={summary.data?.epoch ?? '—'} />
        <Stat label="Tracked jobs" value={summary.data?.tracked_jobs ?? 0} />
        <Stat label="Pending retries" value={summary.data?.pending_retries ?? 0} tone="amber" />
        <Stat label="Max attempts" value={summary.data?.max_attempts ?? '—'} />
      </div>

      {msg && (
        <p className="text-xs text-indigo-300 bg-indigo-950/40 border border-indigo-900/40 rounded-lg px-3 py-2">
          {msg}
        </p>
      )}

      <Card title="Running jobs">
        {!running.length && <Empty>No running jobs.</Empty>}
        <div className="space-y-2">
          {running.map((w) => (
            <div
              key={w.job_id}
              className="flex items-center justify-between border border-slate-800 rounded-lg px-3 py-2 text-sm"
            >
              <div>
                <div className="font-medium">{w.name}</div>
                <div className="text-[11px] text-slate-500 font-mono">
                  {w.priority} · {nodeLabel(w.assigned_node, nodes)} · {shortId(w.job_id)}
                </div>
              </div>
              <button
                disabled={!!busy}
                onClick={() => w.assigned_node && fail(w.assigned_node)}
                className="text-xs px-3 py-1.5 rounded border border-red-800 text-red-300 hover:bg-red-950/50 disabled:opacity-40"
              >
                Fail worker
              </button>
            </div>
          ))}
        </div>
        {!!queued.length && (
          <p className="text-xs text-amber-400 mt-3">{queued.length} queued</p>
        )}
      </Card>

      <Card title="Timeline">
        {!history.data?.history?.length && <Empty>No recoveries.</Empty>}
        <div className="max-h-72 overflow-y-auto divide-y divide-slate-800 text-xs">
          {[...(history.data?.history ?? [])].reverse().map((h, i) => (
            <div key={i} className="py-2 flex justify-between gap-3">
              <div>
                <Badge tone={h.event.includes('EXHAUSTED') ? 'red' : 'amber'}>{h.event}</Badge>
                <span className="ml-2 font-mono text-slate-400">{shortId(h.job_id)}</span>
                <div className="text-slate-500 mt-1">
                  {nodeLabel(h.old_node_id, nodes)}
                  {h.new_node_id ? ` → ${nodeLabel(h.new_node_id, nodes)}` : ' → queue'}
                  {h.reason ? ` · ${h.reason}` : ''}
                </div>
              </div>
              <span className="text-slate-500 shrink-0">
                {h.timestamp ? new Date(h.timestamp * 1000).toLocaleTimeString() : ''}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Stat({ label, value, tone }: { label: string; value: string | number; tone?: 'amber' }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <div className="text-[11px] text-slate-500 uppercase tracking-wide">{label}</div>
      <div className={`text-2xl font-mono mt-1 ${tone === 'amber' ? 'text-amber-300' : 'text-slate-100'}`}>
        {value}
      </div>
    </div>
  );
}
