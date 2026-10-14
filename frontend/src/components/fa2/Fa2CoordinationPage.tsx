import { useFa2Poll } from '../../hooks/useFa2Data';

export default function Fa2CoordinationPage() {
  const leader = useFa2Poll<Record<string, unknown>>('/fa2/coordination/leader');
  const elections = useFa2Poll<{ elections: Array<Record<string, unknown>> }>('/fa2/coordination/elections');
  const beacons = useFa2Poll<{ beacons: Array<Record<string, unknown>> }>('/fa2/coordination/beacons');
  const locks = useFa2Poll<Record<string, unknown>>('/fa2/coordination/locks');
  const deadlocks = useFa2Poll<Record<string, unknown>>('/fa2/coordination/deadlocks');

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <Panel title="Current coordinator (Bully)">
        <pre className="text-xs font-mono overflow-auto">{JSON.stringify(leader.data, null, 2)}</pre>
      </Panel>
      <Panel title="Distributed locks">
        <pre className="text-xs font-mono overflow-auto">{JSON.stringify(locks.data, null, 2)}</pre>
      </Panel>
      <Panel title="Beacon health" wide>
        {!beacons.data?.beacons?.length && <p className="text-slate-500 text-sm">No beacons yet.</p>}
        <div className="space-y-2 text-xs">
          {beacons.data?.beacons?.map((b, i) => (
            <div key={i} className="flex justify-between border-b border-slate-800 pb-1">
              <span>{String(b.node_id)} seq={String(b.sequence)}</span>
              <span className="text-emerald-400">{String(b.health)}</span>
            </div>
          ))}
        </div>
      </Panel>
      <Panel title="Election history" wide>
        {!elections.data?.elections?.length && (
          <p className="text-slate-500 text-sm">No elections recorded yet (workers must register).</p>
        )}
        {elections.data?.elections?.map((e, i) => (
          <details key={i} className="text-xs mb-2 border border-slate-800 rounded p-2">
            <summary className="cursor-pointer">
              {String(e.elected_coordinator ?? 'pending')} — {String(e.reason)}
            </summary>
            <pre className="mt-2 overflow-auto">{JSON.stringify(e.events, null, 2)}</pre>
          </details>
        ))}
      </Panel>
      <Panel title="Deadlock detection" wide>
        <pre className="text-xs font-mono">{JSON.stringify(deadlocks.data, null, 2)}</pre>
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
