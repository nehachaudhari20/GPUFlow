import { useFa2Poll } from '../../hooks/useFa2Data';
import type { WorkerNode } from '../../types';
import { Badge, Card, Empty, nodeLabel } from './Fa2Ui';

interface ClocksPayload {
  coordinator: { node_id: string; lamport_time: number; vector_clock: Record<string, number> };
  workers?: Array<{
    node_id: string;
    hostname?: string;
    election_id?: number;
    lamport_time?: number | null;
    vector_clock?: Record<string, number>;
    offset_ms?: number | null;
    rtt_ms?: number | null;
    sync_status?: string | null;
  }>;
}

interface EventsPayload {
  events: Array<{
    event_id: string;
    event_type: string;
    message: string;
    source: string;
    destination?: string;
    lamport_timestamp?: number;
    node_id?: string;
  }>;
}

export default function Fa2SyncPage({ nodes }: { nodes: WorkerNode[] }) {
  const clocks = useFa2Poll<ClocksPayload>('/fa2/synchronization/clocks', 2000);
  const events = useFa2Poll<EventsPayload>('/fa2/synchronization/events?limit=40', 2000);
  const workers = clocks.data?.workers ?? [];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Scheduler Lamport">
          <div className="text-4xl font-mono text-indigo-300">
            {clocks.data?.coordinator.lamport_time ?? '—'}
          </div>
        </Card>
        <Card title="Vector clock" className="md:col-span-2">
          <div className="flex flex-wrap gap-2">
            {Object.entries(clocks.data?.coordinator.vector_clock ?? {}).map(([k, v]) => (
              <span key={k} className="font-mono text-xs bg-slate-950 border border-slate-800 rounded px-2 py-1">
                {nodeLabel(k, nodes, k.slice(0, 8))} = {v}
              </span>
            ))}
            {!Object.keys(clocks.data?.coordinator.vector_clock ?? {}).length && <Empty>No vector entries.</Empty>}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {workers.map((w) => (
          <Card key={w.node_id} title={w.hostname || nodeLabel(w.node_id, nodes)}>
            <dl className="text-xs space-y-1.5 font-mono">
              <Row k="Lamport" v={w.lamport_time ?? '—'} />
              <Row k="Offset" v={w.offset_ms == null ? '—' : `${Number(w.offset_ms).toFixed(1)} ms`} />
              <Row k="RTT" v={w.rtt_ms == null ? '—' : `${Number(w.rtt_ms).toFixed(1)} ms`} />
              <Row k="Status" v={w.sync_status || '—'} />
            </dl>
          </Card>
        ))}
        {!workers.length && (
          <Card title="Workers" className="md:col-span-3">
            <Empty>No workers.</Empty>
          </Card>
        )}
      </div>

      <Card title="Events">
        {!events.data?.events?.length && <Empty>No events.</Empty>}
        <div className="max-h-80 overflow-y-auto divide-y divide-slate-800 text-xs">
          {events.data?.events?.map((e) => (
            <div key={e.event_id} className="py-2 flex justify-between gap-4">
              <div>
                <Badge tone="indigo">{e.event_type}</Badge>
                <span className="ml-2 text-slate-300">{e.message}</span>
                <div className="text-slate-500 mt-0.5 font-mono">
                  {e.source} → {e.destination || '—'}
                </div>
              </div>
              <span className="font-mono text-indigo-300 shrink-0">L={e.lamport_timestamp ?? '—'}</span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Row({ k, v }: { k: string; v: string | number }) {
  return (
    <div className="flex justify-between gap-2">
      <dt className="text-slate-500">{k}</dt>
      <dd className="text-slate-200">{v}</dd>
    </div>
  );
}
