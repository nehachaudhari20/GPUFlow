import { useState } from 'react';
import { apiPost } from '../../api';
import { useFa2Poll } from '../../hooks/useFa2Data';
import type { WorkerNode } from '../../types';
import { Badge, Card, Empty, nodeLabel } from './Fa2Ui';

interface LockNode {
  node_id: string;
  hostname?: string;
  in_critical_section?: boolean;
  deferred_replies?: string[];
  replies_received?: string[];
  outstanding_replies?: string[];
}

interface Demo {
  owner?: string | null;
  owner_hostname?: string | null;
  clock?: number;
  nodes?: LockNode[];
  trace?: Array<{
    type: string;
    hostname?: string;
    node_id: string;
    timestamp?: number;
    job_id?: string;
  }>;
}

export default function Fa2MutexPage({ nodes }: { nodes: WorkerNode[] }) {
  const locks = useFa2Poll<{ demo?: Demo }>('/fa2/coordination/locks', 1500);
  const [busy, setBusy] = useState<string | null>(null);
  const [err, setErr] = useState('');

  const demo = locks.data?.demo;
  const members = demo?.nodes ?? [];

  const act = async (path: string, nodeId: string) => {
    setBusy(nodeId + path);
    setErr('');
    try {
      await apiPost(path, { node_id: nodeId });
      await locks.refresh();
    } catch (e) {
      setErr(e instanceof Error ? e.message : 'Failed');
    } finally {
      setBusy(null);
    }
  };

  return (
    <div className="space-y-4">
      {err && <p className="text-red-400 text-xs">{err}</p>}
      <Card title="Critical section">
        {demo?.owner ? (
          <>
            <Badge tone="amber">HELD</Badge>
            <p className="text-lg mt-2 font-semibold text-amber-300">
              {demo.owner_hostname || nodeLabel(demo.owner, nodes)}
            </p>
          </>
        ) : (
          <Badge tone="emerald">FREE</Badge>
        )}
        <p className="text-[11px] font-mono text-slate-500 mt-3">T={demo?.clock ?? 0}</p>
      </Card>

      <div className="grid gap-4 md:grid-cols-3">
        {members.map((m) => {
          const inCs = !!m.in_critical_section;
          const waiting = (m.outstanding_replies ?? []).length > 0;
          return (
            <div
              key={m.node_id}
              className={`rounded-xl border p-4 ${
                inCs ? 'border-amber-500/40 bg-amber-950/20' : 'border-slate-800 bg-slate-900'
              }`}
            >
              <div className="flex justify-between items-start">
                <h3 className="font-semibold">{m.hostname || nodeLabel(m.node_id, nodes)}</h3>
                <Badge tone={inCs ? 'amber' : waiting ? 'indigo' : 'slate'}>
                  {inCs ? 'IN CS' : waiting ? 'WAITING' : 'IDLE'}
                </Badge>
              </div>
              <dl className="text-[11px] font-mono mt-3 space-y-1 text-slate-400">
                <div>
                  outstanding:{' '}
                  {(m.outstanding_replies ?? []).length
                    ? (m.outstanding_replies ?? []).map((id) => nodeLabel(id, nodes)).join(', ')
                    : 'none'}
                </div>
                <div>
                  replies:{' '}
                  {(m.replies_received ?? []).length
                    ? (m.replies_received ?? []).map((id) => nodeLabel(id, nodes)).join(', ')
                    : 'none'}
                </div>
                <div>
                  deferred:{' '}
                  {(m.deferred_replies ?? []).length
                    ? (m.deferred_replies ?? []).map((id) => nodeLabel(id, nodes)).join(', ')
                    : 'none'}
                </div>
              </dl>
              <div className="flex gap-2 mt-3">
                <button
                  disabled={!!busy || inCs}
                  onClick={() => act('/fa2/coordination/locks/request', m.node_id)}
                  className="flex-1 text-xs py-1.5 rounded bg-indigo-600 disabled:opacity-40"
                >
                  Request
                </button>
                <button
                  disabled={!!busy || !inCs}
                  onClick={() => act('/fa2/coordination/locks/release', m.node_id)}
                  className="flex-1 text-xs py-1.5 rounded border border-slate-600 disabled:opacity-40"
                >
                  Release
                </button>
              </div>
            </div>
          );
        })}
        {!members.length && (
          <Card title="Workers" className="md:col-span-3">
            <Empty>No workers.</Empty>
          </Card>
        )}
      </div>

      <Card title="Trace">
        {!(demo?.trace ?? []).length && <Empty>No lock messages.</Empty>}
        <div className="max-h-48 overflow-y-auto font-mono text-xs space-y-1">
          {[...(demo?.trace ?? [])].reverse().map((t, i) => (
            <div key={i} className="flex gap-3">
              <span className="text-indigo-300 w-20">{t.type}</span>
              <span className="text-slate-300">{t.hostname || nodeLabel(t.node_id, nodes)}</span>
              {t.timestamp != null && <span className="text-slate-500">T={t.timestamp}</span>}
              {t.job_id && <span className="text-slate-500">{t.job_id.slice(0, 8)}…</span>}
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
