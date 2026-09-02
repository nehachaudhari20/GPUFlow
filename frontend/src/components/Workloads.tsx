import { useState } from 'react';
import type { Workload } from '../types';
import { Play, Eye, Clock, CheckCircle2, XCircle, RefreshCw } from 'lucide-react';
import WorkloadDetails from './WorkloadDetails';

interface Props {
  workloads: Workload[];
  refresh: () => void;
}

export default function Workloads({ workloads, refresh }: Props) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState(false);

  const runScheduler = async () => {
    setScheduling(true);
    try {
      await fetch('/scheduler/run', { method: 'POST' });
      refresh();
    } finally {
      setScheduling(false);
    }
  };

  const scheduleJob = async (jobId: string) => {
    try {
      await fetch(`/scheduler/workloads/${jobId}/schedule`, { method: 'POST' });
      refresh();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Workload Queue</h2>
          <p className="text-sm text-slate-400">View and manage scheduled GPU workloads</p>
        </div>
        <div className="flex gap-3">
          <button
            onClick={refresh}
            className="flex items-center gap-2 px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm transition"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            onClick={runScheduler}
            disabled={scheduling}
            className="flex items-center gap-2 px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-medium transition shadow-sm"
          >
            <Play size={16} />
            {scheduling ? 'Scheduling...' : 'Run Scheduler'}
          </button>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-400 bg-slate-950/50">
              <th className="p-4">Job ID</th>
              <th className="p-4">Name</th>
              <th className="p-4">Type</th>
              <th className="p-4">Priority</th>
              <th className="p-4">Status</th>
              <th className="p-4">Requirements</th>
              <th className="p-4">Assigned Node</th>
              <th className="p-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-sm">
            {workloads.map((job) => (
              <tr key={job.job_id} className="hover:bg-slate-800/30 transition">
                <td className="p-4 font-mono text-xs text-indigo-400">{job.job_id.substring(0, 8)}...</td>
                <td className="p-4 font-medium text-slate-200">{job.name}</td>
                <td className="p-4">
                  <span className="px-2.5 py-1 rounded-full text-xs font-medium bg-slate-800 text-slate-300">
                    {job.type}
                  </span>
                </td>
                <td className="p-4">
                  <PriorityBadge priority={job.priority} />
                </td>
                <td className="p-4">
                  <StatusBadge status={job.status} />
                </td>
                <td className="p-4 text-xs text-slate-400 space-y-0.5">
                  <div>GPU: {job.gpu_required} ({job.gpu_memory_required}GB)</div>
                  <div>CPU: {job.cpu_required} | RAM: {job.ram_required}GB</div>
                </td>
                <td className="p-4 text-xs">
                  {job.assigned_node ? (
                    <span className="font-mono text-emerald-400 bg-emerald-950/30 px-2 py-1 rounded border border-emerald-900/50">
                      {job.assigned_node}
                    </span>
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </td>
                <td className="p-4 text-right">
                  <div className="flex justify-end gap-2">
                    {job.status === 'QUEUED' && (
                      <button
                        onClick={() => scheduleJob(job.job_id)}
                        className="px-2.5 py-1.5 bg-indigo-600/20 text-indigo-400 hover:bg-indigo-600/30 rounded border border-indigo-500/30 text-xs font-medium"
                      >
                        Schedule
                      </button>
                    )}
                    <button
                      onClick={() => setSelectedJobId(job.job_id)}
                      className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded transition"
                      title="View Details"
                    >
                      <Eye size={16} />
                    </button>
                  </div>
                </td>
              </tr>
            ))}
            {workloads.length === 0 && (
              <tr>
                <td colSpan={8} className="p-8 text-center text-slate-500">
                  No workloads found. Use the "Submit Workload" tab to create one.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {selectedJobId && (
        <WorkloadDetails jobId={selectedJobId} onClose={() => setSelectedJobId(null)} />
      )}
    </div>
  );
}

function PriorityBadge({ priority }: { priority: string }) {
  const colors: Record<string, string> = {
    CRITICAL: 'bg-red-500/10 text-red-400 border-red-500/20',
    HIGH: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    MEDIUM: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    LOW: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
  };
  return (
    <span className={`px-2.5 py-0.5 rounded-full text-xs font-medium border ${colors[priority] || colors.LOW}`}>
      {priority}
    </span>
  );
}

function StatusBadge({ status }: { status: string }) {
  switch (status) {
    case 'RUNNING':
      return (
        <span className="flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 border border-emerald-500/20 px-2.5 py-0.5 rounded-full text-xs font-medium">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
          Running
        </span>
      );
    case 'QUEUED':
      return (
        <span className="flex items-center gap-1.5 text-yellow-400 bg-yellow-500/10 border border-yellow-500/20 px-2.5 py-0.5 rounded-full text-xs font-medium">
          <Clock size={12} />
          Queued
        </span>
      );
    case 'COMPLETED':
      return (
        <span className="flex items-center gap-1.5 text-blue-400 bg-blue-500/10 border border-blue-500/20 px-2.5 py-0.5 rounded-full text-xs font-medium">
          <CheckCircle2 size={12} />
          Completed
        </span>
      );
    case 'FAILED':
      return (
        <span className="flex items-center gap-1.5 text-red-400 bg-red-500/10 border border-red-500/20 px-2.5 py-0.5 rounded-full text-xs font-medium">
          <XCircle size={12} />
          Failed
        </span>
      );
    default:
      return (
        <span className="text-slate-400 bg-slate-500/10 border border-slate-500/20 px-2.5 py-0.5 rounded-full text-xs font-medium">
          {status}
        </span>
      );
  }
}
