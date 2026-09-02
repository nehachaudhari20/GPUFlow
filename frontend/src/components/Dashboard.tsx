import { ResponsiveContainer, PieChart, Pie, Cell } from 'recharts';
import type { WorkerNode, Workload, ClusterResourceResponse } from '../types';
import { Activity, Server, CheckCircle2, XCircle, GitCommit } from 'lucide-react';

interface Props {
  nodes: WorkerNode[];
  workloads: Workload[];
  resources: ClusterResourceResponse | null;
}

export default function Dashboard({ nodes, workloads, resources }: Props) {
  const healthyNodes = nodes.filter(n => n.status === 'ONLINE').length;
  const offlineNodes = nodes.filter(n => n.status === 'OFFLINE').length;

  const queued = workloads.filter(w => w.status === 'QUEUED').length;
  const running = workloads.filter(w => w.status === 'RUNNING').length;
  const completed = workloads.filter(w => w.status === 'COMPLETED').length;
  const failed = workloads.filter(w => w.status === 'FAILED').length;

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <h2 className="text-2xl font-bold tracking-tight">Cluster Dashboard</h2>

      <div className="grid grid-cols-4 gap-4">
        <MetricCard title="Total Nodes" value={nodes.length} icon={<Server className="text-blue-400" />} />
        <MetricCard title="Healthy Nodes" value={healthyNodes} icon={<CheckCircle2 className="text-emerald-400" />} />
        <MetricCard title="Offline Nodes" value={offlineNodes} icon={<XCircle className="text-red-400" />} />
        <MetricCard title="Total GPUs" value={resources?.total_gpus || 0} icon={<Activity className="text-purple-400" />} />
      </div>

      <div className="grid grid-cols-4 gap-4">
        <MetricCard title="Running Jobs" value={running} icon={<Activity className="text-emerald-400" />} />
        <MetricCard title="Queued Jobs" value={queued} icon={<GitCommit className="text-yellow-400" />} />
        <MetricCard title="Completed Jobs" value={completed} icon={<CheckCircle2 className="text-blue-400" />} />
        <MetricCard title="Failed Jobs" value={failed} icon={<XCircle className="text-red-400" />} />
      </div>

      {resources && (
        <div className="grid grid-cols-3 gap-6 pt-6">
          <ResourceUtilizationCard
            title="GPU Utilization"
            total={resources.total_gpus}
            available={resources.available_gpus}
            unit="GPUs"
            color="#a855f7" // purple
          />
          <ResourceUtilizationCard
            title="CPU Utilization"
            total={resources.total_cpus}
            available={resources.available_cpus}
            unit="Cores"
            color="#3b82f6" // blue
          />
          <ResourceUtilizationCard
            title="RAM Utilization"
            total={resources.total_ram}
            available={resources.available_ram}
            unit="GB"
            color="#10b981" // emerald
          />
        </div>
      )}
    </div>
  );
}

function MetricCard({ title, value, icon }: { title: string; value: number | string; icon: React.ReactNode }) {
  return (
    <div className="bg-slate-900 border border-slate-800 p-5 rounded-xl shadow-sm flex items-center justify-between">
      <div>
        <p className="text-sm font-medium text-slate-400">{title}</p>
        <p className="text-3xl font-bold text-slate-100 mt-1">{value}</p>
      </div>
      <div className="p-3 bg-slate-800/50 rounded-lg">{icon}</div>
    </div>
  );
}

function ResourceUtilizationCard({ title, total, available, unit, color }: { title: string; total: number; available: number; unit: string; color: string; }) {
  const safeTotal = Number.isFinite(total) ? total : 0;
  const safeAvailable = Number.isFinite(available) ? available : 0;
  const used = Math.max(0, safeTotal - safeAvailable);
  const utilizedPercent = safeTotal > 0 ? (used / safeTotal) * 100 : 0;

  const data = [
    { name: 'Used', value: used },
    { name: 'Free', value: available },
  ];

  return (
    <div className="bg-slate-900 border border-slate-800 p-6 rounded-xl shadow-sm flex flex-col items-center">
      <h3 className="text-lg font-medium text-slate-200 self-start">{title}</h3>
      <div className="h-48 w-full mt-4">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie
              data={data}
              innerRadius={70}
              outerRadius={90}
              paddingAngle={2}
              dataKey="value"
              stroke="none"
              cornerRadius={4}
            >
              <Cell fill={color} />
              <Cell fill="#1e293b" />
            </Pie>
          </PieChart>
        </ResponsiveContainer>
      </div>
      <div className="text-center mt-2">
        <div className="text-3xl font-bold text-slate-100">{utilizedPercent.toFixed(1)}%</div>
        <div className="text-sm text-slate-400 mt-1">{used.toFixed(1)} / {safeTotal.toFixed(1)} {unit}</div>
      </div>
    </div>
  );
}
