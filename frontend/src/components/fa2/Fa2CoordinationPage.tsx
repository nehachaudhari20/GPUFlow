import { Crown } from 'lucide-react';
import { useFa2Poll } from '../../hooks/useFa2Data';
import type { WorkerNode } from '../../types';
import { Badge, Card, Empty, nodeLabel, shortId } from './Fa2Ui';

interface Leader {
  coordinator_node_id?: string | null;
  coordinator_election_id?: number;
  membership_epoch?: number;
  scheduling_authority?: string;
}

interface Member {
  node_id: string;
  election_id: number;
  hostname: string;
}

interface Beacon {
  node_id: string;
  sequence: number;
  health: string;
}

interface Election {
  elected_coordinator?: string;
  reason?: string;
  events?: Array<{ type?: string }>;
}

export default function Fa2CoordinationPage({ nodes }: { nodes: WorkerNode[] }) {
  const leader = useFa2Poll<Leader>('/fa2/coordination/leader', 2000);
  const members = useFa2Poll<{ members: Member[] }>('/fa2/coordination/members', 2000);
  const beacons = useFa2Poll<{ beacons: Beacon[] }>('/fa2/coordination/beacons', 2000);
  const elections = useFa2Poll<{ elections: Election[] }>('/fa2/coordination/elections', 3000);

  const coordId = leader.data?.coordinator_node_id;
  const ranked = [...(members.data?.members ?? [])].sort((a, b) => b.election_id - a.election_id);

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Coordinator">
          <div className="flex items-center gap-2 text-lg font-semibold text-amber-300">
            <Crown size={18} />
            {coordId ? nodeLabel(coordId, nodes) : '—'}
          </div>
          <p className="text-xs font-mono text-slate-500 mt-2">
            id={leader.data?.coordinator_election_id ?? '—'} · epoch {leader.data?.membership_epoch ?? '—'}
          </p>
        </Card>
        <Card title="Scheduler">
          <Badge tone="emerald">{leader.data?.scheduling_authority || 'laptop_scheduler'}</Badge>
        </Card>
      </div>

      <Card title="Members">
        {!ranked.length && <Empty>No members.</Empty>}
        <div className="space-y-2">
          {ranked.map((m) => {
            const isCoord = m.node_id === coordId;
            return (
              <div
                key={m.node_id}
                className={`flex items-center justify-between rounded-lg border px-3 py-2 text-sm ${
                  isCoord ? 'border-amber-500/40 bg-amber-950/20' : 'border-slate-800 bg-slate-950'
                }`}
              >
                <div className="flex items-center gap-3">
                  <span className="font-mono text-indigo-300 w-6">#{m.election_id}</span>
                  <span className="font-medium">{m.hostname}</span>
                  {isCoord && <Badge tone="amber">COORDINATOR</Badge>}
                </div>
                <span className="text-[11px] font-mono text-slate-500">{shortId(m.node_id)}</span>
              </div>
            );
          })}
        </div>
      </Card>

      <div className="grid gap-4 md:grid-cols-2">
        <Card title="Beacons">
          {!beacons.data?.beacons?.length && <Empty>No beacons.</Empty>}
          <div className="space-y-2 text-xs">
            {beacons.data?.beacons?.map((b) => (
              <div key={b.node_id} className="flex justify-between border-b border-slate-800 pb-1.5">
                <span>{nodeLabel(b.node_id, nodes)}</span>
                <span className="flex items-center gap-2">
                  <span className="font-mono text-slate-500">seq {b.sequence}</span>
                  <Badge tone={b.health === 'HEALTHY' ? 'emerald' : 'red'}>{b.health}</Badge>
                </span>
              </div>
            ))}
          </div>
        </Card>
        <Card title="Elections">
          {!elections.data?.elections?.length && <Empty>No elections.</Empty>}
          <div className="max-h-56 overflow-y-auto space-y-2">
            {[...(elections.data?.elections ?? [])].reverse().slice(0, 8).map((e, i) => (
              <div key={i} className="text-xs border border-slate-800 rounded p-2">
                <div className="flex justify-between">
                  <span className="text-amber-300">
                    {e.elected_coordinator ? nodeLabel(e.elected_coordinator, nodes) : 'pending'}
                  </span>
                  <span className="text-slate-500">{e.reason}</span>
                </div>
                <div className="text-slate-500 mt-1 font-mono">
                  {(e.events ?? []).map((ev) => ev.type).filter(Boolean).join(' → ') || '—'}
                </div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
