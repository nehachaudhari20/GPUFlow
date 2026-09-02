import { useState } from 'react';
import type { WorkloadType, Priority, Workload } from '../types';
import { PlusCircle, Cpu, Activity, HardDrive, CheckCircle2, Clock, Loader2 } from 'lucide-react';
import { apiPost } from '../api';

interface Props {
  onSubmitSuccess: () => void;
  refresh: () => void;
}

async function waitForSchedule(
  jobId: string,
  refresh: () => void,
  maxAttempts = 12
): Promise<Workload> {
  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    const res = await fetch(`/workloads/${jobId}`);
    const workload: Workload = await res.json();
    if (workload.status !== 'QUEUED') {
      return workload;
    }

    const allRes = await fetch('/workloads').then(r => r.json());
    const hasRunning = (allRes.workloads || []).some(
      (w: Workload) => w.status === 'RUNNING' && w.job_id !== jobId
    );
    if (hasRunning) {
      return workload;
    }

    await apiPost('/scheduler/run-next').catch(() => undefined);
    refresh();
    await new Promise(r => setTimeout(r, 1500));
  }
  const final = await fetch(`/workloads/${jobId}`).then(r => r.json());
  return final;
}

export default function SubmitWorkload({ onSubmitSuccess, refresh }: Props) {
  const [name, setName] = useState('');
  const [type, setType] = useState<WorkloadType>('TRAINING');
  const [priority, setPriority] = useState<Priority>('MEDIUM');
  const [gpuRequired, setGpuRequired] = useState(1.0);
  const [gpuMemoryRequired, setGpuMemoryRequired] = useState(4.0);
  const [cpuRequired, setCpuRequired] = useState(2.0);
  const [ramRequired, setRamRequired] = useState(8.0);
  const [estimatedDuration, setEstimatedDuration] = useState(30);

  const [submitting, setSubmitting] = useState(false);
  const [submittedJob, setSubmittedJob] = useState<Workload | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setError(null);
    try {
      const res = await fetch('/workloads', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          name,
          type,
          priority,
          gpu_required: Number(gpuRequired),
          gpu_memory_required: Number(gpuMemoryRequired),
          cpu_required: Number(cpuRequired),
          ram_required: Number(ramRequired),
          estimated_duration: Number(estimatedDuration),
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || 'Submission failed');
      }
      const data: Workload = await res.json();
      let finalJob = data;
      if (data.status === 'QUEUED') {
        finalJob = await waitForSchedule(data.job_id, refresh);
      }
      setSubmittedJob(finalJob);
      refresh();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Submission failed');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Submit Workload</h2>
        <p className="text-sm text-slate-400">
          Jobs auto-start when the cluster is idle (Priority + FCFS). If another job is already running, new jobs queue automatically.
        </p>
      </div>

      {submittedJob ? (
        <div className="bg-slate-900 border border-emerald-500/30 p-6 rounded-xl space-y-4">
          <div className="flex items-center gap-3 text-emerald-400">
            <CheckCircle2 size={24} />
            <h3 className="text-lg font-bold">Added to Queue</h3>
          </div>
          <div className="bg-slate-950 p-4 rounded-lg space-y-2 text-xs font-mono text-slate-300 border border-slate-800">
            <div><span className="text-slate-500">Job ID:</span> {submittedJob.job_id}</div>
            <div className="flex items-center gap-2">
              <span className="text-slate-500">Status:</span>
              <span className={`font-semibold ${
                submittedJob.status === 'RUNNING' ? 'text-emerald-400' :
                submittedJob.status === 'QUEUED' ? 'text-yellow-400' : 'text-cyan-400'
              }`}>{submittedJob.status}</span>
              {submittedJob.status === 'RUNNING' && <Loader2 size={12} className="text-emerald-400 animate-spin" />}
              {submittedJob.status === 'QUEUED' && <Clock size={12} className="text-yellow-400" />}
            </div>
            <div><span className="text-slate-500">Priority:</span> {submittedJob.priority}</div>
            <div><span className="text-slate-500">Duration:</span> {submittedJob.estimated_duration}s when scheduled</div>
            <div><span className="text-slate-500">Requirements:</span> {submittedJob.gpu_required} GPU ({submittedJob.gpu_memory_required}GB), {submittedJob.cpu_required} CPU, {submittedJob.ram_required}GB RAM</div>
          </div>
          <p className="text-xs text-slate-400">
            {submittedJob.status === 'RUNNING'
              ? 'Job is running — open Workload Queue to watch the live progress bar.'
              : submittedJob.status === 'QUEUED'
                ? 'Another job is running (or workers are starting). This job is queued by priority + FCFS — use Workload Queue → Process Next or Schedule All.'
                : 'Check Workload Queue for status updates.'}
          </p>
          <div className="flex gap-3 pt-2">
            <button
              onClick={() => {
                setSubmittedJob(null);
                setName('');
              }}
              className="px-4 py-2 bg-slate-800 hover:bg-slate-700 text-slate-200 text-xs font-medium rounded-lg transition"
            >
              Submit Another
            </button>
            <button
              onClick={onSubmitSuccess}
              className="px-4 py-2 bg-indigo-600 hover:bg-indigo-500 text-white text-xs font-medium rounded-lg transition"
            >
              Go to Workload Queue
            </button>
          </div>
        </div>
      ) : (
        <form onSubmit={handleSubmit} className="bg-slate-900 border border-slate-800 p-6 rounded-xl space-y-6 shadow-sm">
          {error && (
            <div className="p-3 bg-red-950/40 border border-red-800/60 rounded-lg text-xs text-red-400">
              {error}
            </div>
          )}
          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                Workload Name
              </label>
              <input
                type="text"
                required
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. LLM Fine-tuning Job"
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none transition"
              />
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                Workload Type
              </label>
              <select
                value={type}
                onChange={(e) => setType(e.target.value as WorkloadType)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none transition"
              >
                <option value="TRAINING">Training</option>
                <option value="INFERENCE">Inference</option>
                <option value="BATCH">Batch Processing</option>
                <option value="PREPROCESSING">Preprocessing (CPU-heavy)</option>
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-6">
            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                Priority
              </label>
              <select
                value={priority}
                onChange={(e) => setPriority(e.target.value as Priority)}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none transition"
              >
                <option value="CRITICAL">Critical</option>
                <option value="HIGH">High</option>
                <option value="MEDIUM">Medium</option>
                <option value="LOW">Low</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-semibold text-slate-400 mb-1.5 uppercase tracking-wider">
                Estimated Duration (seconds)
              </label>
              <input
                type="number"
                min="1"
                required
                value={estimatedDuration}
                onChange={(e) => setEstimatedDuration(Number(e.target.value))}
                className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3.5 py-2 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none transition"
              />
            </div>
          </div>

          <div className="border-t border-slate-800 pt-5">
            <h4 className="text-xs font-semibold text-slate-400 uppercase tracking-wider mb-4">
              Resource Requirements
            </h4>
            <div className="grid grid-cols-4 gap-4">
              <div>
                <label className="block text-xs text-slate-400 mb-1 flex items-center gap-1">
                  <Activity size={13} className="text-purple-400" /> GPU Count
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={gpuRequired}
                  onChange={(e) => setGpuRequired(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1 flex items-center gap-1">
                  <Activity size={13} className="text-purple-400" /> VRAM (GB)
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0"
                  value={gpuMemoryRequired}
                  onChange={(e) => setGpuMemoryRequired(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1 flex items-center gap-1">
                  <Cpu size={13} className="text-blue-400" /> CPU Cores
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  value={cpuRequired}
                  onChange={(e) => setCpuRequired(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                />
              </div>

              <div>
                <label className="block text-xs text-slate-400 mb-1 flex items-center gap-1">
                  <HardDrive size={13} className="text-emerald-400" /> RAM (GB)
                </label>
                <input
                  type="number"
                  step="0.5"
                  min="0.5"
                  value={ramRequired}
                  onChange={(e) => setRamRequired(Number(e.target.value))}
                  className="w-full bg-slate-950 border border-slate-800 rounded-lg px-3 py-1.5 text-sm text-slate-200 focus:border-indigo-500 focus:outline-none"
                />
              </div>
            </div>
          </div>

          <div className="flex justify-end pt-3">
            <button
              type="submit"
              disabled={submitting}
              className="flex items-center gap-2 px-6 py-2.5 bg-indigo-600 hover:bg-indigo-500 text-white rounded-lg text-sm font-semibold transition shadow-md shadow-indigo-600/20"
            >
              <PlusCircle size={16} />
              {submitting ? 'Submitting...' : 'Submit to Queue'}
            </button>
          </div>
        </form>
      )}
    </div>
  );
}
