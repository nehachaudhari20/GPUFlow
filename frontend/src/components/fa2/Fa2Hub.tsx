import { useState } from 'react';
import type { WorkerNode, Workload } from '../../types';
import Fa2SyncPage from './Fa2SyncPage';
import Fa2CoordinationPage from './Fa2CoordinationPage';
import Fa2MutexPage from './Fa2MutexPage';
import Fa2RecoveryPage from './Fa2RecoveryPage';
import Fa2ReplicaPage from './Fa2ReplicaPage';

const tabs = [
  { id: 'sync', label: 'Clocks' },
  { id: 'bully', label: 'Bully election' },
  { id: 'mutex', label: 'Mutual exclusion' },
  { id: 'recovery', label: 'Failure & retry' },
  { id: 'replica', label: 'Replicas' },
] as const;

type Fa2Tab = (typeof tabs)[number]['id'];

export default function Fa2Hub({
  nodes,
  workloads,
  onRefresh,
}: {
  nodes: WorkerNode[];
  workloads: Workload[];
  onRefresh?: () => void;
}) {
  const [tab, setTab] = useState<Fa2Tab>('sync');

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h2 className="text-2xl font-bold">FA2</h2>
      <div className="flex flex-wrap gap-2">
        {tabs.map((t) => (
          <button
            key={t.id}
            onClick={() => setTab(t.id)}
            className={`px-3 py-1.5 rounded-lg text-xs font-medium border ${
              tab === t.id
                ? 'bg-indigo-600 border-indigo-500 text-white'
                : 'border-slate-700 text-slate-400 hover:text-slate-200'
            }`}
          >
            {t.label}
          </button>
        ))}
      </div>
      {tab === 'sync' && <Fa2SyncPage nodes={nodes} />}
      {tab === 'bully' && <Fa2CoordinationPage nodes={nodes} />}
      {tab === 'mutex' && <Fa2MutexPage nodes={nodes} />}
      {tab === 'recovery' && (
        <Fa2RecoveryPage nodes={nodes} workloads={workloads} onChanged={onRefresh} />
      )}
      {tab === 'replica' && <Fa2ReplicaPage />}
    </div>
  );
}
