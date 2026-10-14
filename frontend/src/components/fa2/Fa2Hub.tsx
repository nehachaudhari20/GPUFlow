import { useState } from 'react';
import Fa2SyncPage from './Fa2SyncPage';
import Fa2CoordinationPage from './Fa2CoordinationPage';
import Fa2GlobalStatePage from './Fa2GlobalStatePage';
import Fa2RecoveryPage from './Fa2RecoveryPage';
import Fa2StoragePage from './Fa2StoragePage';
import Fa2FunctionsPage from './Fa2FunctionsPage';

const tabs = [
  { id: 'sync', label: 'Synchronization' },
  { id: 'coord', label: 'Coordination' },
  { id: 'global', label: 'Global State' },
  { id: 'recovery', label: 'Fault Recovery' },
  { id: 'storage', label: 'Distributed Storage' },
  { id: 'functions', label: 'Functions & Scaling' },
] as const;

type Fa2Tab = (typeof tabs)[number]['id'];

export default function Fa2Hub() {
  const [tab, setTab] = useState<Fa2Tab>('sync');

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold">FA2 Distributed Systems</h2>
        <p className="text-sm text-slate-400">
          CPU-only cluster — clocks, coordination, recovery, storage, and scaling from live backend APIs
        </p>
      </div>
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
      {tab === 'sync' && <Fa2SyncPage />}
      {tab === 'coord' && <Fa2CoordinationPage />}
      {tab === 'global' && <Fa2GlobalStatePage />}
      {tab === 'recovery' && <Fa2RecoveryPage />}
      {tab === 'storage' && <Fa2StoragePage />}
      {tab === 'functions' && <Fa2FunctionsPage />}
    </div>
  );
}
