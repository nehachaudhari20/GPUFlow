import { useState } from 'react';
import type { Workload } from '../types';
import { Play, Info, CheckCircle2, XCircle } from 'lucide-react';

interface Props {
  workloads: Workload[];
  refresh: () => void;
}

export default function SchedulerView({ workloads, refresh }: Props) {
  const queuedWorkloads = workloads.filter((w) => w.status === 'QUEUED');
  const [selectedJobId, setSelectedJobId] = useState<string>(queuedWorkloads[0]?.job_id || '');
  const [decision, setDecision] = useState<any | null>(null);
  const [scheduling, setScheduling] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleScheduleJob = async (jobId: string) => {
    if (!jobId) return;
    setScheduling(true);
    setError(null);
    try {
      const res = await fetch(`/scheduler/workloads/${jobId}/schedule`, { method: 'POST' });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Scheduling failed');
      }
      const data = await res.json();
      setDecision(data.decision);
      refresh();
    } catch (e: any) {
      setError(e.message);
    } finally {
      setScheduling(false);
    }
  };

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Custom Scheduling Engine</h2>
        <p className="text-sm text-slate-400">
          Evaluates candidate worker nodes via normalized multi-criteria scoring algorithm
        </p>
      </div>

      <div className="bg-indigo-950/20 border border-indigo-500/30 p-5 rounded-xl flex items-start gap-4">
        <Info size={20} className="text-indigo-400 mt-0.5 shrink-0" />
        <div className="space-y-1.5 text-xs text-slate-300">
          <p className="font-semibold text-slate-200">FA1 Scheduling Decision Matrix:</p>
          <p className="font-mono text-indigo-300 bg-indigo-950/60 p-2 rounded border border-indigo-900/40 inline-block">
            Score = 40% GPU + 25% CPU + 15% RAM + 10% Health + 10% Load Balance
          </p>
          <p className="text-slate-400">
            1. Filter Phase: Rejects offline or resource-deficient nodes based on requirements.<br />
            2. Scoring Phase: Normalizes remaining eligible candidate capacities against weights.<br />
            3. Placement: Node with highest total score is selected for atomic resource reservation.
          </p>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-4">
        <h3 className="text-sm font-semibold text-slate-300 uppercase tracking-wider">
          Evaluate Queued Workload
        </h3>
        <div className="flex gap-4 items-center">
          <select
            value={selectedJobId}
            onChange={(e) => {
              setSelectedJobId(e.target.value);
              setDecision(null);
              setError(null);
            }}
            className="flex-1 bg-slate-950 border border-slate-800 rounded-lg px-4 py-2.5 text-sm text-slate-200 outline-none focus:border-indigo-500"
          >
            {queuedWorkloads.length === 0 && (
              <option value="">No workloads currently queued</option>
            )}
            {queuedWorkloads.map((job) => (
              <option key={job.job_id} value={job.job_id}>
                {job.name} ({job.type}) — Priority: {job.priority} [GPU: {job.gpu_required}, CPU: {job.cpu_required}]
              </option>
            ))}
          </select>
          <button
            onClick={() => handleScheduleJob(selectedJobId)}
            disabled={scheduling || !selectedJobId}
            className="px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 disabled:bg-slate-800 text-white rounded-lg text-sm font-semibold transition flex items-center gap-2 shadow-sm"
          >
            <Play size={16} />
            {scheduling ? 'Computing Scores...' : 'Run Scheduling Decision'}
          </button>
        </div>

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
                  {decision.allocation_success ? 'Workload Allocated Successfully' : 'Scheduling Postponed / Failed'}
                </h4>
                <p className="text-xs text-slate-300 mt-1">{decision.reason || (decision.kept_queued ? 'Kept queued due to lack of eligible nodes' : '')}</p>
              </div>
              {decision.selected_node && (
                <div className="text-right">
                  <span className="text-xs text-slate-400">Selected Node:</span>
                  <div className="font-mono text-lg font-bold text-emerald-400">{decision.selected_node}</div>
                </div>
              )}
            </div>
          </div>

          <div className="grid grid-cols-1 gap-6">
            <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
              <div className="p-4 border-b border-slate-800 bg-slate-950/50">
                <h4 className="text-sm font-semibold text-slate-200">Candidate Node Evaluations</h4>
              </div>
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-800 text-slate-400 bg-slate-950/30">
                    <th className="p-3 pl-4">Node ID</th>
                    <th className="p-3 text-emerald-400">GPU (40%)</th>
                    <th className="p-3 text-blue-400">CPU (25%)</th>
                    <th className="p-3 text-teal-400">RAM (15%)</th>
                    <th className="p-3 text-slate-400">Health (10%)</th>
                    <th className="p-3 text-slate-400">Load Bal (10%)</th>
                    <th className="p-3 font-semibold text-white bg-slate-800/40">Total Score</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/60 font-mono">
                  {decision.candidate_nodes?.map((node: any) => (
                    <tr
                      key={node.node_id}
                      className={node.node_id === decision.selected_node ? 'bg-indigo-950/30 font-semibold' : ''}
                    >
                      <td className="p-3 pl-4 text-slate-200 flex items-center gap-1.5">
                        <CheckCircle2 size={14} className="text-emerald-500" />
                        {node.node_id}
                      </td>
                      <td className="p-3 text-slate-400">{node.scores.gpu_availability.toFixed(1)}</td>
                      <td className="p-3 text-slate-400">{node.scores.cpu_availability.toFixed(1)}</td>
                      <td className="p-3 text-slate-400">{node.scores.ram_availability.toFixed(1)}</td>
                      <td className="p-3 text-slate-400">{node.scores.health.toFixed(1)}</td>
                      <td className="p-3 text-slate-400">{node.scores.load_balance.toFixed(1)}</td>
                      <td className="p-3 bg-slate-800/20 text-indigo-300 font-bold">{node.scores.total.toFixed(2)}</td>
                    </tr>
                  ))}

                  {decision.rejected_nodes?.map((node: any) => (
                    <tr key={node.node_id} className="opacity-50">
                      <td className="p-3 pl-4 text-slate-200 flex items-center gap-1.5">
                        <XCircle size={14} className="text-red-500" />
                        {node.node_id}
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
        </div>
      )}
    </div>
  );
}
