import { useMemo, useState, useEffect } from 'react';
import type { Workload, WorkerNode } from '../types';
import { Play, Eye, Clock, CheckCircle2, XCircle, RefreshCw, Loader2, Layers } from 'lucide-react';
import WorkloadDetails from './WorkloadDetails';
import { apiPost, ApiError, type SchedulingDecisionResponse } from '../api';

const STATUS_ORDER: Record<string, number> = {
  RUNNING: 0,
  SCHEDULED: 1,
  QUEUED: 2,
  COMPLETED: 3,
  FAILED: 4,
  CANCELLED: 5,
};

const PRIORITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

interface Props {
  workloads: Workload[];
  nodes: WorkerNode[];
  refresh: () => void;
  cpuOnlyMode?: boolean;
}

function decisionMessage(data: SchedulingDecisionResponse): string {
  if (data.message) return data.message;
  const d = data.decision;
  if (!d) return 'No scheduling decision returned';
  if (d.allocation_success && d.selected_node) {
    return `Job scheduled on node ${d.selected_node.substring(0, 8)}...`;
  }
  return d.reason || 'Job kept in queue (no free worker or insufficient resources)';
}

export default function Workloads({ workloads, nodes, refresh, cpuOnlyMode = true }: Props) {
  const [selectedJobId, setSelectedJobId] = useState<string | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [actionMessage, setActionMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const nodeById = useMemo(() => {
    const map = new Map<string, WorkerNode>();
    nodes.forEach(n => map.set(n.node_id, n));
    return map;
  }, [nodes]);

  const sortedWorkloads = useMemo(() => {
    return [...workloads].sort((a, b) => {
      const statusDiff = (STATUS_ORDER[a.status] ?? 99) - (STATUS_ORDER[b.status] ?? 99);
      if (statusDiff !== 0) return statusDiff;
      const priorityDiff = (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99);
      if (priorityDiff !== 0) return priorityDiff;
      return a.created_at - b.created_at;
    });
  }, [workloads]);

  const queuedCount = workloads.filter(w => w.status === 'QUEUED').length;
  const runningCount = workloads.filter(w => w.status === 'RUNNING').length;
  const freeWorkers = nodes.filter(
    n => n.status === 'ONLINE' && (n.current_workloads?.length ?? 0) === 0
  ).length;

  useEffect(() => {
    if (!actionMessage) return;
    const id = window.setTimeout(() => setActionMessage(null), 6000);
    return () => window.clearTimeout(id);
  }, [actionMessage]);

  const runScheduleAction = async (
    label: string,
    action: () => Promise<SchedulingDecisionResponse>
  ) => {
    setActionMessage(null);
    try {
      const data = await action();
      await refresh();
      setActionMessage({ type: 'success', text: `${label}: ${decisionMessage(data)}` });
    } catch (e) {
      const text = e instanceof ApiError ? e.message : e instanceof Error ? e.message : 'Request failed';
      setActionMessage({ type: 'error', text: `${label} failed — ${text}` });
    }
  };

  const processNext = async () => {
    setScheduling(true);
    try {
      await runScheduleAction('Process Next', () => apiPost('/scheduler/run-next'));
    } finally {
      setScheduling(false);
    }
  };

  const processAll = async () => {
    setScheduling(true);
    try {
      const data = await apiPost<SchedulingDecisionResponse>('/scheduler/run');
      await refresh();
      const count = data.count ?? data.decisions?.length ?? 0;
      if (count === 0) {
        setActionMessage({ type: 'error', text: 'No queued jobs were scheduled (check worker availability)' });
      } else {
        setActionMessage({ type: 'success', text: `Scheduled ${count} job(s) onto free workers` });
      }
    } catch (e) {
      const text = e instanceof ApiError ? e.message : 'Request failed';
      setActionMessage({ type: 'error', text: `Schedule All failed — ${text}` });
    } finally {
      setScheduling(false);
    }
  };

  const resolveNodeLabel = (nodeId: string | null | undefined) => {
    if (!nodeId) return '—';
    const node = nodeById.get(nodeId);
    if (node) return node.hostname;
    return `${nodeId.substring(0, 8)}...`;
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-start gap-4">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Workload Queue</h2>
          <p className="text-sm text-slate-400 mt-1">
            Jobs follow <strong className="text-slate-300">Priority + FCFS</strong> automatically.
            Jobs auto-start on a free worker at submit. Priority only orders the queue (CRITICAL before HIGH before MEDIUM); each worker runs one job at a time so concurrent jobs spread across worker-1/2/3.
          </p>
          <div className="flex gap-4 mt-2 text-xs font-mono">
            <span className="text-yellow-400">{queuedCount} queued</span>
            <span className="text-emerald-400">{runningCount} running</span>
            <span className="text-indigo-400">{freeWorkers} free workers</span>
          </div>
        </div>
        <div className="flex gap-2 shrink-0">
          <button
            onClick={() => refresh()}
            className="flex items-center gap-2 px-3 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 rounded-lg text-sm transition"
          >
            <RefreshCw size={16} />
            Refresh
          </button>
          <button
            onClick={processNext}
            disabled={scheduling || queuedCount === 0}
            className="flex items-center gap-2 px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition shadow-sm"
          >
            {scheduling ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
            Process Next
          </button>
          <button
            onClick={processAll}
            disabled={scheduling || queuedCount === 0}
            className="flex items-center gap-2 px-3 py-2 bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-medium transition shadow-sm"
          >
            {scheduling ? <Loader2 size={16} className="animate-spin" /> : <Layers size={16} />}
            Schedule All Queued
          </button>
        </div>
      </div>

      {actionMessage && (
        <div className={`p-3 rounded-lg text-sm border ${
          actionMessage.type === 'success'
            ? 'bg-emerald-950/40 border-emerald-800/60 text-emerald-300'
            : 'bg-red-950/40 border-red-800/60 text-red-300'
        }`}>
          {actionMessage.text}
        </div>
      )}

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <table className="w-full text-left border-collapse">
          <thead>
            <tr className="border-b border-slate-800 text-xs font-semibold uppercase tracking-wider text-slate-400 bg-slate-950/50">
              <th className="p-4">Job ID</th>
              <th className="p-4">Name</th>
              <th className="p-4">Type</th>
              <th className="p-4">Priority</th>
              <th className="p-4">Status</th>
              <th className="p-4">Duration</th>
              <th className="p-4">Requirements</th>
              <th className="p-4">Assigned Worker</th>
              <th className="p-4 text-right">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-800/60 text-sm">
            {sortedWorkloads.map((job) => (
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
                <td className="p-4 text-xs text-slate-400 font-mono min-w-[120px]">
                  {job.status === 'RUNNING' ? (
                    <RunningProgress job={job} />
                  ) : (
                    `${job.estimated_duration}s`
                  )}
                </td>
                <td className="p-4 text-xs text-slate-400 space-y-0.5">
                  {cpuOnlyMode ? (
                    <div>CPU: {job.cpu_required} | RAM: {job.ram_required}GB</div>
                  ) : (
                    <>
                      <div>GPU: {job.gpu_required} ({job.gpu_memory_required}GB)</div>
                      <div>CPU: {job.cpu_required} | RAM: {job.ram_required}GB</div>
                    </>
                  )}
                </td>
                <td className="p-4 text-xs">
                  {job.assigned_node ? (
                    <span className="font-mono text-emerald-400 bg-emerald-950/30 px-2 py-1 rounded border border-emerald-900/50">
                      {resolveNodeLabel(job.assigned_node)}
                    </span>
                  ) : (
                    <span className="text-slate-500">—</span>
                  )}
                </td>
                <td className="p-4 text-right">
                  <button
                    onClick={() => setSelectedJobId(job.job_id)}
                    className="p-1.5 hover:bg-slate-800 text-slate-400 hover:text-slate-200 rounded transition"
                    title="View Details"
                  >
                    <Eye size={16} />
                  </button>
                </td>
              </tr>
            ))}
            {sortedWorkloads.length === 0 && (
              <tr>
                <td colSpan={9} className="p-8 text-center text-slate-500">
                  No workloads found. Use the Submit Workload tab to create one.
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

function RunningProgress({ job }: { job: Workload }) {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 500);
    return () => window.clearInterval(id);
  }, [job.job_id]);

  const startMs = (job.started_at ?? job.updated_at) * 1000;
  const elapsed = Math.max(0, (now - startMs) / 1000);
  const total = job.estimated_duration;
  const progress = Math.min(100, (elapsed / total) * 100);
  const remaining = Math.max(0, total - elapsed);

  return (
    <div className="space-y-1.5">
      <div className="font-mono text-emerald-400">{Math.floor(elapsed)}s / {total}s</div>
      <div className="h-1.5 bg-slate-800 rounded-full overflow-hidden w-24">
        <div
          className="h-full bg-emerald-500 transition-all duration-500 ease-linear"
          style={{ width: `${progress}%` }}
        />
      </div>
      <div className="text-[10px] text-slate-500">{Math.ceil(remaining)}s remaining</div>
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
          <Loader2 size={12} className="animate-spin" />
          Running
        </span>
      );
    case 'SCHEDULED':
      return (
        <span className="flex items-center gap-1.5 text-cyan-400 bg-cyan-500/10 border border-cyan-500/20 px-2.5 py-0.5 rounded-full text-xs font-medium">
          <Clock size={12} />
          Scheduled
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
