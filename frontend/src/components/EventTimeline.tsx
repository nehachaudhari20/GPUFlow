import { useState } from 'react';
import type { SystemEvent, EventType } from '../types';
import { MessageSquare, ArrowRight, Filter } from 'lucide-react';

interface Props {
  events: SystemEvent[];
}

export default function EventTimeline({ events }: Props) {
  const [filterType, setFilterType] = useState<string>('ALL');

  const filteredEvents = filterType === 'ALL'
    ? events
    : events.filter((e) => e.event_type === filterType);

  const eventTypes: EventType[] = [
    'NODE_REGISTERED',
    'HEARTBEAT_RECEIVED',
    'NODE_OFFLINE',
    'JOB_SUBMITTED',
    'JOB_QUEUED',
    'NODE_EVALUATED',
    'NODE_REJECTED',
    'NODE_SELECTED',
    'RESOURCE_ALLOCATED',
    'TASK_ASSIGNED',
    'TASK_STARTED',
    'RESOURCE_UPDATED',
    'TASK_COMPLETED',
    'TASK_FAILED',
    'RESOURCE_RELEASED',
  ];

  return (
    <div className="space-y-6 max-w-7xl mx-auto">
      <div className="flex justify-between items-center">
        <div>
          <h2 className="text-2xl font-bold tracking-tight">Distributed Communication Log</h2>
          <p className="text-sm text-slate-400">Stream-oriented & message-driven event bus tracing cluster operations</p>
        </div>
        <div className="flex items-center gap-2 bg-slate-900 border border-slate-800 rounded-lg px-3 py-1.5 text-xs">
          <Filter size={14} className="text-slate-400" />
          <select
            value={filterType}
            onChange={(e) => setFilterType(e.target.value)}
            className="bg-transparent text-slate-200 outline-none cursor-pointer"
          >
            <option value="ALL" className="bg-slate-900">All Event Types</option>
            {eventTypes.map((t) => (
              <option key={t} value={t} className="bg-slate-900">{t}</option>
            ))}
          </select>
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl overflow-hidden shadow-sm">
        <div className="divide-y divide-slate-800/60 max-h-[70vh] overflow-y-auto">
          {filteredEvents.map((event) => (
            <div key={event.event_id} className="p-4 hover:bg-slate-800/30 transition flex items-start justify-between gap-4 text-xs">
              <div className="flex items-start gap-3">
                <div className="mt-0.5 p-1.5 rounded-lg bg-slate-800 text-slate-400">
                  <MessageSquare size={14} />
                </div>
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <span className="font-mono text-slate-500">
                      {new Date(event.timestamp * 1000).toLocaleTimeString()}
                    </span>
                    <EventBadge type={event.event_type} />
                    {event.job_id && (
                      <span className="font-mono text-[11px] text-indigo-400 bg-indigo-950/40 px-1.5 py-0.5 rounded border border-indigo-900/40">
                        Job: {event.job_id.substring(0, 8)}
                      </span>
                    )}
                    {event.node_id && (
                      <span className="font-mono text-[11px] text-emerald-400 bg-emerald-950/40 px-1.5 py-0.5 rounded border border-emerald-900/40">
                        Node: {event.node_id}
                      </span>
                    )}
                  </div>
                  <p className="text-slate-300 font-medium">{event.message}</p>
                </div>
              </div>

              {(event.source || event.destination) && (
                <div className="flex items-center gap-1.5 font-mono text-[11px] text-slate-400 bg-slate-950 px-2.5 py-1 rounded border border-slate-800/60 shrink-0">
                  <span>{event.source || 'Scheduler'}</span>
                  <ArrowRight size={12} className="text-slate-600" />
                  <span>{event.destination || 'Cluster'}</span>
                </div>
              )}
            </div>
          ))}

          {filteredEvents.length === 0 && (
            <div className="p-12 text-center text-slate-500">
              No events match the selected criteria.
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function EventBadge({ type }: { type: EventType }) {
  const colors: Partial<Record<EventType, string>> = {
    NODE_REGISTERED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    HEARTBEAT_RECEIVED: 'bg-slate-500/10 text-slate-400 border-slate-500/20',
    NODE_OFFLINE: 'bg-red-500/10 text-red-400 border-red-500/20',
    JOB_SUBMITTED: 'bg-indigo-500/10 text-indigo-400 border-indigo-500/20',
    JOB_QUEUED: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    NODE_SELECTED: 'bg-cyan-500/10 text-cyan-400 border-cyan-500/20',
    TASK_ASSIGNED: 'bg-purple-500/10 text-purple-400 border-purple-500/20',
    TASK_STARTED: 'bg-blue-500/10 text-blue-400 border-blue-500/20',
    TASK_COMPLETED: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    TASK_FAILED: 'bg-red-500/10 text-red-400 border-red-500/20',
    RESOURCE_RELEASED: 'bg-teal-500/10 text-teal-400 border-teal-500/20',
  };

  return (
    <span className={`px-2 py-0.5 rounded text-[11px] font-mono font-medium border ${colors[type] || 'bg-slate-800 text-slate-300'}`}>
      {type}
    </span>
  );
}
