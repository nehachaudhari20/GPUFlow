import type { ReactNode } from 'react';
import { useFa2Poll } from '../../hooks/useFa2Data';

export default function Fa2SyncPage() {
  const clocks = useFa2Poll<{ coordinator: { lamport_time: number; vector_clock: Record<string, number> } }>(
    '/fa2/synchronization/clocks'
  );
  const events = useFa2Poll<{ events: Array<Record<string, unknown>> }>('/fa2/synchronization/events?limit=30');
  const offsets = useFa2Poll<{ offsets: Array<Record<string, unknown>> }>('/fa2/synchronization/offsets');

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Card title="Coordinator logical clock">
        {clocks.loading && <Muted>Loading…</Muted>}
        {clocks.error && <Err>{clocks.error}</Err>}
        {clocks.data && (
          <div className="font-mono text-sm space-y-2">
            <div>Lamport: {clocks.data.coordinator.lamport_time}</div>
            <pre className="text-xs bg-slate-950 p-2 rounded overflow-auto">
              {JSON.stringify(clocks.data.coordinator.vector_clock, null, 2)}
            </pre>
          </div>
        )}
      </Card>
      <Card title="Cristian offsets">
        {offsets.data?.offsets?.length ? (
          <ul className="text-xs font-mono space-y-1">
            {offsets.data.offsets.map((o, i) => (
              <li key={i}>{JSON.stringify(o)}</li>
            ))}
          </ul>
        ) : (
          <Muted>No offset samples yet (heartbeats).</Muted>
        )}
      </Card>
      <Card title="Synchronized events" className="md:col-span-2">
        {!events.data?.events?.length && <Muted>No synchronized events.</Muted>}
        <div className="max-h-96 overflow-y-auto divide-y divide-slate-800 text-xs">
          {events.data?.events?.map((e) => (
            <div key={String(e.event_id)} className="py-2 flex justify-between gap-4">
              <span>
                <span className="text-indigo-400">{String(e.event_type)}</span> — {String(e.message)}
              </span>
              <span className="text-slate-500 shrink-0">
                L={String(e.lamport_timestamp ?? '—')} | {String(e.source)}→{String(e.destination ?? '—')}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}

function Card({ title, children, className = '' }: { title: string; children: ReactNode; className?: string }) {
  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl p-4 ${className}`}>
      <h3 className="text-sm font-semibold mb-3 text-slate-200">{title}</h3>
      {children}
    </div>
  );
}
function Muted({ children }: { children: ReactNode }) {
  return <p className="text-slate-500 text-sm">{children}</p>;
}
function Err({ children }: { children: ReactNode }) {
  return <p className="text-red-400 text-sm">{children}</p>;
}
