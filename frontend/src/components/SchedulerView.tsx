import { useMemo, useState } from 'react';
import type { Workload, WorkerNode } from '../types';
import { Play, Info, CheckCircle2, XCircle, Loader2, ListOrdered } from 'lucide-react';
import { apiPost, ApiError, type SchedulingDecisionResponse } from '../api';
import { getNextQueuedJob, sortQueuedWorkloads } from '../utils/queueSort';

interface Props {
  workloads: Workload[];
  nodes: WorkerNode[];
  refresh: () => void;
}

interface SchedulingDecision {
  job_id: string;
  workload_name?: string;
  allocation_success: boolean;
  kept_queued?: boolean;
  selected_node?: string | null;
  reason?: string | null;
  candidate_nodes?: Array<{
    node_id: string;
    hostname: string;
    scores: Record<string, number>;
  }>;
  rejected_nodes?: Array<{
    node_id: string;
    hostname: string;
    reasons: string[];
  }>;
}

export default function SchedulerView({ workloads, nodes, refresh }: Props) {
  const orderedQueue = useMemo(() => sortQueuedWorkloads(workloads), [workloads]);
  const nextJob = useMemo(() => getNextQueuedJob(workloads), [workloads]);
  const [decision, setDecision] = useState<SchedulingDecision | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nodeById = useMemo(() => {
    const map = new Map<string, WorkerNode>();
    nodes.forEach(n => map.set(n.node_id, n));
    return map;
  }, [nodes]);

  const resolveNodeLabel = (nodeId: string) => {
    const node = nodeById.get(nodeId);
    return node ? `${node.hostname} (${nodeId.substring(0, 8)}...)` : nodeId;
  };

  const handleRunNext = async () => {
    setScheduling(true);
    setError(null);
    setDecision(null);
    try {
      const data = await apiPost<SchedulingDecisionResponse>('/scheduler/run-next');
      if (!data.decision) {
        setError(data.message || 'No queued workloads to schedule');
        return;
      }
      setDecision(data.decision as SchedulingDecision);
      await refresh();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : 'Scheduling failed');
    } finally {
      setScheduling(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Scheduling Engine (Explainability)</h2>
        <p className="text-sm text-slate-400 mt-1">
          Jobs auto-start on submit and follow <strong className="text-slate-300">Priority + FCFS</strong> queue order.
          This page shows <em>how</em> the scheduler picks a worker for the next queued job — no manual job selection needed.
        </p>
      </div>

      <div className="bg-indigo-950/20 border border-indigo-500/30 p-5 rounded-xl flex items-start gap-4">
        <Info size={20} className="text-indigo-400 mt-0.5 shrink-0" />
        <div className="space-y-1.5 text-xs text-slate-300">
          <p className="font-semibold text-slate-200">Two automatic layers:</p>
          <p className="text-slate-400">
            <strong className="text-yellow-400">1. Queue order</strong> — CRITICAL → HIGH → MEDIUM → LOW, then oldest first (FCFS).<br />
            <strong className="text-emerald-400">2. Worker placement</strong> — Score = 40% GPU + 25% CPU + 15% RAM + 10% Health + 10% Load Balance
          </p>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden">
        <div className="p-4 border-b border-slate-800 bg-slate-950/50 flex items-center gap-2">
          <ListOrdered size={16} className="text-yellow-400" />
          <h3 className="text-sm font-semibold text-slate-200">Live Queue Order (Priority + FCFS)</h3>
        </div>
        {orderedQueue.length === 0 ? (
          <p className="p-6 text-sm text-slate-500 text-center">No jobs waiting in queue. Submit a workload — it auto-starts when workers are free.</p>
        ) : (
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-xs text-slate-400 uppercase">
                <th className="p-3 pl-4">#</th>
                <th className="p-3">Name</th>
                <th className="p-3">Priority</th>
                <th className="p-3">Submitted</th>
                <th className="p-3">Requirements</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/60">
              {orderedQueue.map((job, idx) => (
                <tr
                  key={job.job_id}
                  className={idx === 0 ? 'bg-yellow-950/20 border-l-2 border-l-yellow-500' : ''}
                >
                  <td className="p-3 pl-4 font-mono text-xs">
                    {idx === 0 ? (
                      <span className="text-yellow-400 font-semibold">NEXT</span>
                    ) : (
                      idx + 1
                    )}
                  </td>
                  <td className="p-3 text-slate-200">{job.name}</td>
                  <td className="p-3">
                    <span className="text-xs font-medium text-indigo-300">{job.priority}</span>
                  </td>
                  <td className="p-3 text-xs text-slate-500 font-mono">
                    {new Date(job.created_at * 1000).toLocaleTimeString()}
                  </td>
                  <td className="p-3 text-xs text-slate-400">
                    {job.gpu_required} GPU, {job.cpu_required} CPU
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Next Job: Worker Selection
        </h3>
        {nextJob ? (
          <div className="text-sm text-slate-300 bg-slate-950 p-3 rounded-lg border border-slate-800">
            <span className="text-slate-500">Will schedule: </span>
            <strong>{nextJob.name}</strong>
            <span className="text-slate-500"> — </span>
            <span className="text-yellow-400">{nextJob.priority}</span>
            <span className="text-slate-500"> priority, submitted </span>
            {new Date(nextJob.created_at * 1000).toLocaleTimeString()}
          </div>
        ) : (
          <p className="text-sm text-slate-500">Queue is empty — nothing to schedule.</p>
        )}
        <button
          onClick={handleRunNext}
          disabled={scheduling || !nextJob}
          className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 disabled:cursor-not-allowed text-white rounded-lg text-sm font-semibold transition flex items-center gap-2 shadow-sm"
        >
          {scheduling ? <Loader2 size={16} className="animate-spin" /> : <Play size={16} />}
          {scheduling ? 'Scheduling...' : 'Run Next in Queue'}
        </button>
        <p className="text-xs text-slate-500">
          Same as Workload Queue → Process Next. Uses priority + FCFS automatically — you never pick which job runs first.
        </p>
        {error && (
          <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-lg text-xs text-red-400">
            {error}
          </div>
        )}
      </div>

      {decision && (
        <div className="space-y-6">
          <div className={`p-5 rounded-xl border ${
            decision.allocation_success
              ? 'bg-emerald-950/20 border-emerald-500/30 text-emerald-300'
              : 'bg-yellow-950/20 border-yellow-500/30 text-yellow-300'
          }`}>
            <div className="flex items-center justify-between">
              <div>
                <h4 className="font-bold text-base">
                  {decision.allocation_success ? 'Scheduled & Running' : 'Kept in Queue'}
                </h4>
                <p className="text-xs text-slate-300 mt-1">
                  {decision.workload_name && `${decision.workload_name} — `}
                  {decision.reason || (decision.kept_queued ? 'No eligible worker available' : '')}
                </p>
              </div>
              {decision.selected_node && (
                <div className="text-right">
                  <span className="text-xs text-slate-400">Selected Worker:</span>
                  <div className="font-mono text-lg font-bold text-emerald-400">
                    {resolveNodeLabel(decision.selected_node)}
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
            <div className="p-4 border-b border-slate-800 bg-slate-950/50">
              <h4 className="text-sm font-semibold text-slate-200">Node Evaluation Matrix</h4>
            </div>
            <table className="w-full text-left text-xs border-collapse">
              <thead>
                <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/30">
                  <th className="p-3 pl-4">Worker</th>
                  <th className="p-3 text-emerald-400">GPU (40%)</th>
                  <th className="p-3 text-blue-400">CPU (25%)</th>
                  <th className="p-3 text-teal-400">RAM (15%)</th>
                  <th className="p-3 text-slate-400">Health (10%)</th>
                  <th className="p-3 text-slate-400">Load Bal (10%)</th>
                  <th className="p-3 font-semibold text-white bg-slate-800/40">Total</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/60 font-mono">
                {decision.candidate_nodes?.map((node) => (
                  <tr
                    key={node.node_id}
                    className={node.node_id === decision.selected_node ? 'bg-indigo-950/30 font-semibold' : ''}
                  >
                    <td className="p-3 pl-4 text-slate-200 flex items-center gap-1.5">
                      <CheckCircle2 size={14} className="text-emerald-500" />
                      {node.hostname || node.node_id.substring(0, 8)}
                    </td>
                    <td className="p-3 text-slate-400">{node.scores.gpu_availability.toFixed(1)}</td>
                    <td className="p-3 text-slate-400">{node.scores.cpu_availability.toFixed(1)}</td>
                    <td className="p-3 text-slate-400">{node.scores.ram_availability.toFixed(1)}</td>
                    <td className="p-3 text-slate-400">{node.scores.health.toFixed(1)}</td>
                    <td className="p-3 text-slate-400">{node.scores.load_balance.toFixed(1)}</td>
                    <td className="p-3 bg-slate-800/20 text-indigo-300 font-bold">{node.scores.total.toFixed(2)}</td>
                  </tr>
                ))}
                {decision.rejected_nodes?.map((node) => (
                  <tr key={node.node_id} className="opacity-50">
                    <td className="p-3 pl-4 text-slate-200 flex items-center gap-1.5">
                      <XCircle size={14} className="text-red-500" />
                      {node.hostname || node.node_id.substring(0, 8)}
                    </td>
                    <td colSpan={6} className="p-3 text-red-300 font-sans text-xs">
                      {node.reasons.join(', ')}
                    </td>
                  </tr>
                ))}
                {(!decision.candidate_nodes?.length && !decision.rejected_nodes?.length) && (
                  <tr>
                    <td colSpan={7} className="p-6 text-center text-slate-500 font-sans">
                      No workers available to evaluate.
                    </td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
