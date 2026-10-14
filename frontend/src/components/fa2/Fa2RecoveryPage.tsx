import { useFa2Poll } from '../../hooks/useFa2Data';

export default function Fa2RecoveryPage() {
  const summary = useFa2Poll<Record<string, unknown>>('/fa2/recovery/summary');
  const history = useFa2Poll<{ history: Array<Record<string, unknown>> }>('/fa2/recovery/history');
  const replication = useFa2Poll<Record<string, unknown>>('/fa2/replication/status');

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="Recovery summary">
        <pre className="text-xs font-mono">{JSON.stringify(summary.data, null, 2)}</pre>
      </Panel>
      <Panel title="Replication (primary-writer)">
        <pre className="text-xs font-mono">{JSON.stringify(replication.data, null, 2)}</pre>
      </Panel>
      <Panel title="Recovery timeline" wide>
        {!history.data?.history?.length && (
          <p className="text-slate-500 text-sm">No recovery events yet.</p>
        )}
        {history.data?.history?.map((h, i) => (
          <div key={i} className="text-xs py-2 border-b border-slate-800 font-mono">
            {new Date(Number(h.timestamp) * 1000).toLocaleTimeString()} — {String(h.event)} job={String(h.job_id)}
          </div>
        ))}
      </Panel>
    </div>
  );
}

function Panel({ title, children, wide }: { title: string; children: React.ReactNode; wide?: boolean }) {
  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl p-4 ${wide ? 'md:col-span-2' : ''}`}>
      <h3 className="text-sm font-semibold mb-2">{title}</h3>
      {children}
    </div>
  );
}
