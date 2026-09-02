import { useEffect, useState } from 'react';
import type { Workload, SystemEvent } from '../types';
import { X } from 'lucide-react';

interface Props {
  jobId: string;
  onClose: () => void;
}

export default function WorkloadDetails({ jobId, onClose }: Props) {
  const [workload, setWorkload] = useState<Workload | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([
      fetch(`/workloads/${jobId}`).then((r) => r.json()),
      fetch(`/events/${jobId}`).then((r) => r.json()),
    ])
      .then(([w, e]) => {
        setWorkload(w);
        setEvents(e || []);
      })
      .finally(() => setLoading(false));
  }, [jobId]);

  if (loading || !workload) {
    return (
      <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center">
        <div className="bg-slate-900 border border-slate-800 p-8 rounded-xl">Loading...</div>
      </div>
    );
  }

  const steps = [
    { label: 'SUBMITTED', active: true },
    { label: 'QUEUED', active: ['QUEUED', 'SCHEDULED', 'RUNNING', 'COMPLETED'].includes(workload.status) },
    { label: 'SCHEDULED', active: ['SCHEDULED', 'RUNNING', 'COMPLETED'].includes(workload.status) },
    { label: 'RUNNING', active: ['RUNNING', 'COMPLETED'].includes(workload.status) },
    { label: 'COMPLETED', active: workload.status === 'COMPLETED' },
  ];

  return (
    <div className="fixed inset-0 bg-slate-950/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl w-full max-w-3xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        <div className="p-6 border-b border-slate-800 flex justify-between items-center">
          <div>
            <h3 className="text-xl font-bold text-slate-100">{workload.name}</h3>
            <p className="text-xs font-mono text-slate-400 mt-1">ID: {workload.job_id}</p>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-200">
            <X size={20} />
          </button>
        </div>

        <div className="p-6 overflow-y-auto space-y-6">
          {/* Lifecycle progress bar */}
          <div>
            <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-4">Lifecycle</h4>
            <div className="flex items-center justify-between relative">
              <div className="absolute left-0 top-1/2 -translate-y-1/2 h-0.5 w-full bg-slate-800 -z-0" />
              {steps.map((step, idx) => (
                <div key={idx} className="flex flex-col items-center relative z-10">
                  <div
                    className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-bold ${
                      step.active
                        ? 'bg-indigo-600 text-white ring-4 ring-slate-900'
                        : 'bg-slate-800 text-slate-500'
                    }`}
                  >
                    {idx + 1}
                  </div>
                  <span className="text-[10px] font-medium text-slate-400 mt-2">{step.label}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Allocation & Info */}
          <div className="grid grid-cols-2 gap-4">
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80">
              <span className="text-xs text-slate-500 font-medium">Assigned Worker</span>
              <p className="text-sm font-semibold text-slate-200 mt-1">
                {workload.assigned_node || 'Pending Allocation'}
              </p>
            </div>
            <div className="bg-slate-950 p-4 rounded-lg border border-slate-800/80">
              <span className="text-xs text-slate-500 font-medium">Estimated Duration</span>
              <p className="text-sm font-semibold text-slate-200 mt-1">
                {workload.estimated_duration ? `${workload.estimated_duration}s` : 'N/A'}
              </p>
            </div>
          </div>

          {/* Requirements Grid */}
          <div>
            <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Resource Requirements</h4>
            <div className="grid grid-cols-4 gap-3">
              <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
                <span className="text-xs text-slate-500">GPU Required</span>
                <p className="text-base font-bold text-indigo-400 mt-0.5">{workload.gpu_required}</p>
              </div>
              <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
                <span className="text-xs text-slate-500">VRAM</span>
                <p className="text-base font-bold text-indigo-400 mt-0.5">{workload.gpu_memory_required} GB</p>
              </div>
              <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
                <span className="text-xs text-slate-500">CPU Cores</span>
                <p className="text-base font-bold text-blue-400 mt-0.5">{workload.cpu_required}</p>
              </div>
              <div className="bg-slate-950/50 p-3 rounded-lg border border-slate-800/60">
                <span className="text-xs text-slate-500">RAM</span>
                <p className="text-base font-bold text-emerald-400 mt-0.5">{workload.ram_required} GB</p>
              </div>
            </div>
          </div>

          {/* Job Specific Events */}
          <div>
            <h4 className="text-sm font-semibold text-slate-400 uppercase tracking-wider mb-3">Execution Events</h4>
            <div className="space-y-2 max-h-48 overflow-y-auto">
              {events.map((e) => (
                <div key={e.event_id} className="text-xs p-2.5 rounded bg-slate-950 border border-slate-800/60 flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <span className="font-mono text-slate-500">{new Date(e.timestamp * 1000).toLocaleTimeString()}</span>
                    <span className="px-1.5 py-0.5 bg-slate-800 text-slate-300 rounded font-mono text-[10px]">{e.event_type}</span>
                    <span className="text-slate-300">{e.message}</span>
                  </div>
                </div>
              ))}
              {events.length === 0 && <p className="text-xs text-slate-500">No events recorded for this workload yet.</p>}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
