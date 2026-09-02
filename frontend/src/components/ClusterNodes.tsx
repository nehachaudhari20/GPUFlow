import type { WorkerNode } from '../types';
import { Server, Activity, Cpu, HardDrive, AlertTriangle, CheckCircle2 } from 'lucide-react';

interface Props {
  nodes: WorkerNode[];
}

export default function ClusterNodes({ nodes }: Props) {
  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div>
        <h2 className="text-2xl font-bold tracking-tight">Cluster Nodes</h2>
        <p className="text-sm text-slate-400">Heterogeneous worker nodes with real-time heartbeat and resource status</p>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        {nodes.map((node) => (
          <NodeCard key={node.node_id} node={node} />
        ))}
        {nodes.length === 0 && (
          <div className="col-span-full p-12 text-center bg-slate-900 border border-slate-800 rounded-xl">
            <p className="text-slate-500">No worker nodes registered with the scheduler yet.</p>
          </div>
        )}
      </div>
    </div>
  );
}

function NodeCard({ node }: { node: WorkerNode }) {
  const isOnline = node.status === 'ONLINE';
  const now = Date.now() / 1000;
  const secondsSinceHeartbeat = Math.floor(now - node.last_heartbeat);

  return (
    <div className={`bg-slate-900 border rounded-xl p-6 shadow-sm flex flex-col justify-between transition ${
      isOnline ? 'border-slate-800 hover:border-slate-700' : 'border-red-900/40 bg-red-950/10'
    }`}>
      <div>
        <div className="flex justify-between items-start mb-4">
          <div>
            <div className="flex items-center gap-2">
              <Server size={18} className={isOnline ? 'text-indigo-400' : 'text-red-400'} />
              <h3 className="font-bold text-slate-200">{node.hostname}</h3>
            </div>
            <p className="text-xs text-slate-500 font-mono mt-0.5">{node.node_id.substring(0, 8)}... :{node.grpc_port}</p>
          </div>
          <span className={`px-2.5 py-0.5 rounded-full text-xs font-semibold flex items-center gap-1.5 ${
            isOnline ? 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20' : 'bg-red-500/10 text-red-400 border border-red-500/20'
          }`}>
            <span className={`h-1.5 w-1.5 rounded-full ${isOnline ? 'bg-emerald-400 animate-pulse' : 'bg-red-400'}`} />
            {node.status}
          </span>
        </div>

        <div className="space-y-3.5 my-4 text-xs">
          {/* GPU Bar */}
          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span className="flex items-center gap-1"><Activity size={13} /> GPUs</span>
              <span className="font-mono text-slate-200">
                {(node.gpu_total - node.gpu_available).toFixed(1)} / {node.gpu_total} ({node.gpu_memory_available.toFixed(1)}GB VRAM free)
              </span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div
                className="bg-purple-500 h-full rounded-full transition-all"
                style={{ width: `${node.gpu_total > 0 ? ((node.gpu_total - node.gpu_available) / node.gpu_total) * 100 : 0}%` }}
              />
            </div>
          </div>

          {/* CPU Bar */}
          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span className="flex items-center gap-1"><Cpu size={13} /> CPU Cores</span>
              <span className="font-mono text-slate-200">
                {(node.cpu_total - node.cpu_available).toFixed(1)} / {node.cpu_total}
              </span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div
                className="bg-blue-500 h-full rounded-full transition-all"
                style={{ width: `${node.cpu_total > 0 ? ((node.cpu_total - node.cpu_available) / node.cpu_total) * 100 : 0}%` }}
              />
            </div>
          </div>

          {/* RAM Bar */}
          <div>
            <div className="flex justify-between text-slate-400 mb-1">
              <span className="flex items-center gap-1"><HardDrive size={13} /> RAM</span>
              <span className="font-mono text-slate-200">
                {(node.ram_total - node.ram_available).toFixed(1)} / {node.ram_total} GB
              </span>
            </div>
            <div className="w-full bg-slate-800 h-2 rounded-full overflow-hidden">
              <div
                className="bg-emerald-500 h-full rounded-full transition-all"
                style={{ width: `${node.ram_total > 0 ? ((node.ram_total - node.ram_available) / node.ram_total) * 100 : 0}%` }}
              />
            </div>
          </div>
        </div>
      </div>

      <div className="border-t border-slate-800/80 pt-3 space-y-1 text-[11px] text-slate-500">
        <div className="flex justify-between items-center">
          <span>Last heartbeat: {secondsSinceHeartbeat > 0 ? `${secondsSinceHeartbeat}s ago` : 'just now'}</span>
          {isOnline ? (
            <span className="text-emerald-500 flex items-center gap-1"><CheckCircle2 size={12} /> Ready</span>
          ) : (
            <span className="text-red-400 flex items-center gap-1"><AlertTriangle size={12} /> Offline</span>
          )}
        </div>
        {(node.current_workloads?.length ?? 0) > 0 ? (
          <div className="text-emerald-400 font-mono">
            Running {node.current_workloads!.length} job(s): {node.current_workloads!.map(id => id.substring(0, 8)).join(', ')}...
          </div>
        ) : isOnline ? (
          <div className="text-slate-600">No active workloads — available for scheduling</div>
        ) : null}
      </div>
    </div>
  );
}
