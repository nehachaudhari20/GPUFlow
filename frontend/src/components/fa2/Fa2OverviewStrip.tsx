import { useFa2Poll } from '../../hooks/useFa2Data';
import type { WorkerNode } from '../../types';
import { nodeLabel } from './Fa2Ui';

export default function Fa2OverviewStrip({ nodes = [] }: { nodes?: WorkerNode[] }) {
  const leader = useFa2Poll<{ coordinator_node_id?: string | null }>('/fa2/coordination/leader', 4000);
  const recovery = useFa2Poll<{ pending_retries?: number }>('/fa2/recovery/summary', 4000);
  const clocks = useFa2Poll<{ coordinator: { lamport_time: number } }>('/fa2/synchronization/clocks', 4000);
  const replica = useFa2Poll<{ sequence?: number }>('/fa2/replication/status', 4000);

  return (
    <div className="bg-slate-900/80 border border-indigo-900/40 rounded-xl p-4">
      <h3 className="text-sm font-semibold text-indigo-300 mb-3">FA2 live</h3>
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 text-xs">
        <Cell
          label="Bully coordinator"
          value={nodeLabel(leader.data?.coordinator_node_id, nodes)}
        />
        <Cell label="Lamport (scheduler)" value={String(clocks.data?.coordinator?.lamport_time ?? '—')} />
        <Cell label="Pending retries" value={String(recovery.data?.pending_retries ?? 0)} />
        <Cell label="Replica sequence" value={String(replica.data?.sequence ?? 0)} />
      </div>
    </div>
  );
}

function Cell({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span className="text-slate-500 block">{label}</span>
      <span className="font-mono text-slate-200">{value}</span>
    </div>
  );
}
