import { useFa2Poll } from '../../hooks/useFa2Data';

export default function Fa2OverviewStrip() {
  const leader = useFa2Poll<Record<string, unknown>>('/fa2/coordination/leader', 5000);
  const recovery = useFa2Poll<Record<string, unknown>>('/fa2/recovery/summary', 5000);
  const clocks = useFa2Poll<{ coordinator: { lamport_time: number } }>('/fa2/synchronization/clocks', 5000);

  return (
    <div className="bg-slate-900/80 border border-indigo-900/40 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-indigo-300 mb-3">FA2 overview</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <div>
          <span className="text-slate-500 block">Worker coordinator</span>
          <span className="font-mono text-slate-200">{String(leader.data?.coordinator_node_id ?? '—')}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Lamport (scheduler)</span>
          <span className="font-mono text-slate-200">{clocks.data?.coordinator?.lamport_time ?? '—'}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Pending retries</span>
          <span className="font-mono text-slate-200">{String(recovery.data?.pending_retries ?? 0)}</span>
        </div>
        <div>
          <span className="text-slate-500 block">Scheduling authority</span>
          <span className="font-mono text-emerald-400">laptop_scheduler</span>
        </div>
      </div>
    </div>
  );
}
