import { useState } from 'react';
import { LayoutDashboard, ListTodo, Server, PlusCircle, MessageSquare, Briefcase, RotateCcw, Loader2 } from 'lucide-react';
import { cn } from './utils';
import { apiPost } from './api';

import Dashboard from './components/Dashboard';
import Workloads from './components/Workloads';
import ClusterNodes from './components/ClusterNodes';
import EventTimeline from './components/EventTimeline';
import SubmitWorkload from './components/SubmitWorkload';
import SchedulerView from './components/SchedulerView';
import { useClusterData } from './hooks/useClusterData';

type Tab = 'dashboard' | 'workloads' | 'cluster' | 'scheduler' | 'events' | 'submit';

export default function App() {
  const [activeTab, setActiveTab] = useState<Tab>('dashboard');
  const [resetting, setResetting] = useState(false);
  const { nodes, workloads, resources, events, refresh, queuedCount, runningCount } = useClusterData();
  const cpuOnlyMode = resources?.cpu_only_mode ?? false;

  const handleReset = async () => {
    if (!window.confirm('Clear all workloads, events, and queue data? Workers will re-register.')) return;
    setResetting(true);
    try {
      await apiPost('/admin/reset');
      setActiveTab('dashboard');
      await refresh();
    } catch (e) {
      console.error(e);
      alert('Reset failed. Is the backend running?');
    } finally {
      setResetting(false);
    }
  };

  const navItems = [
    { id: 'dashboard', label: 'Dashboard', icon: LayoutDashboard },
    { id: 'cluster', label: 'Cluster Nodes', icon: Server },
    { id: 'submit', label: 'Submit Workload', icon: PlusCircle },
    { id: 'workloads', label: 'Workloads Config', icon: ListTodo },
    { id: 'scheduler', label: 'Scheduler Insights', icon: Briefcase },
    { id: 'events', label: 'Communication Log', icon: MessageSquare },
  ] as const;

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100 overflow-hidden font-sans">
      <nav className="w-64 border-r border-slate-800 flex flex-col shrink-0">
        <div className="p-6 border-b border-slate-800">
          <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-400 to-indigo-400 bg-clip-text text-transparent">GPUFlow</h1>
          <p className="text-xs text-slate-500 mt-1">Distributed FA1 Platform</p>
        </div>
        <div className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <button
              key={item.id}
              onClick={() => setActiveTab(item.id as Tab)}
              className={cn(
                "w-full flex items-center space-x-3 px-4 py-3 rounded-lg transition-all",
                activeTab === item.id
                  ? "bg-indigo-600 border border-indigo-500 text-white shadow-md shadow-indigo-500/20"
                  : "hover:bg-slate-800/60 text-slate-400 hover:text-slate-200"
              )}
            >
              <item.icon size={18} />
              <span className="font-medium text-sm">{item.label}</span>
            </button>
          ))}
        </div>

        <div className="p-4 border-t border-slate-800 text-xs space-y-2 text-slate-500">
          <div className="flex justify-between items-center">
            <span>Backend Link</span>
            <span className="flex items-center gap-1.5 text-emerald-500">
              <span className="w-2 h-2 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </span>
          </div>
          <div className="flex justify-between">
            <span>Queued</span>
            <span className="text-yellow-400 font-mono">{queuedCount}</span>
          </div>
          <div className="flex justify-between">
            <span>Running</span>
            <span className="text-emerald-400 font-mono">{runningCount}</span>
          </div>
          {cpuOnlyMode && (
            <div className="text-amber-400/90 text-[10px] uppercase tracking-wide pt-1">
              CPU-only AWS cluster
            </div>
          )}
          <button
            onClick={handleReset}
            disabled={resetting}
            className="w-full mt-2 flex items-center justify-center gap-2 px-3 py-2 rounded-lg border border-red-900/50 bg-red-950/30 text-red-400 hover:bg-red-950/50 disabled:opacity-50 text-xs font-medium transition"
          >
            {resetting ? <Loader2 size={14} className="animate-spin" /> : <RotateCcw size={14} />}
            {resetting ? 'Resetting...' : 'Reset Demo Data'}
          </button>
        </div>
      </nav>

      <main className="flex-1 overflow-y-auto p-8 relative scroll-smooth">
        {activeTab === 'dashboard' && <Dashboard nodes={nodes} workloads={workloads} resources={resources} />}
        {activeTab === 'cluster' && <ClusterNodes nodes={nodes} cpuOnlyMode={cpuOnlyMode} />}
        {activeTab === 'submit' && (
          <SubmitWorkload
            refresh={refresh}
            cpuOnlyMode={cpuOnlyMode}
            onSubmitSuccess={() => { refresh(); setActiveTab('workloads'); }}
          />
        )}
        {activeTab === 'workloads' && <Workloads workloads={workloads} nodes={nodes} refresh={refresh} />}
        {activeTab === 'scheduler' && (
          <SchedulerView workloads={workloads} nodes={nodes} refresh={refresh} cpuOnlyMode={cpuOnlyMode} />
        )}
        {activeTab === 'events' && <EventTimeline events={events} />}
      </main>
    </div>
  );
}
