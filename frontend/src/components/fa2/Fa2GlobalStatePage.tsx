import { useFa2Poll } from '../../hooks/useFa2Data';

export default function Fa2GlobalStatePage() {
  const latest = useFa2Poll<Record<string, unknown>>('/fa2/global-state/latest');
  const list = useFa2Poll<{ snapshots: Array<Record<string, unknown>> }>('/fa2/global-state/snapshots?limit=10');

  return (
    <div className="space-y-4">
      <div className="bg-amber-950/30 border border-amber-900/50 text-amber-200 text-xs p-3 rounded-lg">
        Snapshots are monitoring-assembled, not Chandy–Lamport consistent cuts (
        {String(latest.data?.snapshot_type ?? 'monitoring_assembled')}).
      </div>
      <Panel title="Latest snapshot">
        <pre className="text-xs max-h-96 overflow-auto font-mono">{JSON.stringify(latest.data, null, 2)}</pre>
      </Panel>
      <Panel title="History">
        <pre className="text-xs max-h-64 overflow-auto font-mono">{JSON.stringify(list.data?.snapshots, null, 2)}</pre>
      </Panel>
    </div>
  );
}

function Panel({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
      <h3 className="text-sm font-semibold mb-2">{title}</h3>
      {children}
    </div>
  );
}
