import { useFa2Poll } from '../../hooks/useFa2Data';
import { Badge, Card, Empty, shortId } from './Fa2Ui';

interface ReplicaRow {
  name?: string;
  replica_id?: string;
  status?: string;
  lag?: number;
  role?: string;
  last_sequence?: number;
}

interface Status {
  model?: string;
  sequence?: number;
  persisted?: boolean;
  replicas?: ReplicaRow[];
}

interface Recent {
  sequence: number;
  timestamp: number;
  payload?: Record<string, unknown>;
}

export default function Fa2ReplicaPage() {
  const status = useFa2Poll<Status>('/fa2/replication/status', 2000);
  const extra = useFa2Poll<{ replicas: ReplicaRow[]; recent: Recent[] }>(
    '/fa2/replication/replicas',
    2000
  );

  const replicas = extra.data?.replicas?.length
    ? extra.data.replicas
    : status.data?.replicas ?? [];

  return (
    <div className="space-y-4">
      <div className="grid gap-4 md:grid-cols-3">
        <Card title="Model">
          <Badge tone="indigo">{status.data?.model || 'primary-writer'}</Badge>
        </Card>
        <Card title="Sequence">
          <div className="text-3xl font-mono text-indigo-300">{status.data?.sequence ?? 0}</div>
        </Card>
        <Card title="Store">
          <Badge tone={status.data?.persisted ? 'emerald' : 'amber'}>
            {status.data?.persisted ? 'MongoDB' : 'Memory'}
          </Badge>
        </Card>
      </div>

      <Card title="Replicas">
        {!replicas.length && <Empty>No replicas.</Empty>}
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 text-left">
              <th className="p-2">Replica</th>
              <th>Role</th>
              <th>Status</th>
              <th>Lag</th>
              <th>Seq</th>
            </tr>
          </thead>
          <tbody>
            {replicas.map((r) => (
              <tr key={r.replica_id || r.name} className="border-t border-slate-800">
                <td className="p-2 font-mono">
                  {r.name}
                  {r.replica_id && r.replica_id !== 'primary' && (
                    <span className="text-slate-500 ml-2">{shortId(r.replica_id)}</span>
                  )}
                </td>
                <td>{r.role || '—'}</td>
                <td>
                  <Badge tone={r.status === 'ACTIVE' ? 'emerald' : 'amber'}>{r.status || '—'}</Badge>
                </td>
                <td className="font-mono">{r.lag ?? 0}</td>
                <td className="font-mono">{r.last_sequence ?? 0}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <Card title="Log">
        {!(extra.data?.recent ?? []).length && <Empty>No records.</Empty>}
        <div className="max-h-72 overflow-y-auto divide-y divide-slate-800 font-mono text-xs">
          {[...(extra.data?.recent ?? [])].reverse().map((row) => (
            <div key={row.sequence} className="py-2 flex justify-between gap-3">
              <div>
                <span className="text-indigo-300">#{row.sequence}</span>
                <span className="ml-2 text-slate-300">{String(row.payload?.type ?? 'record')}</span>
                <div className="text-slate-500 mt-0.5">
                  {row.payload?.job_id ? String(row.payload.job_id).slice(0, 8) + '…' : ''}{' '}
                  {row.payload?.status ? String(row.payload.status) : ''}
                </div>
              </div>
              <span className="text-slate-500">
                {row.timestamp ? new Date(row.timestamp * 1000).toLocaleTimeString() : ''}
              </span>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
