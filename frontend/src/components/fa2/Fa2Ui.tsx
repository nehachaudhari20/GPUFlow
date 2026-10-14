import type { ReactNode } from 'react';
import type { WorkerNode } from '../../types';

export function shortId(id?: string | null, n = 8) {
  if (!id) return '—';
  return id.length <= n ? id : `${id.slice(0, n)}…`;
}

export function nodeLabel(id: string | null | undefined, nodes: WorkerNode[], fallback?: string) {
  if (!id) return fallback || '—';
  const n = nodes.find((x) => x.node_id === id);
  return n?.hostname || fallback || shortId(id);
}

export function Card({
  title,
  hint,
  children,
  className = '',
}: {
  title: string;
  hint?: string;
  children: ReactNode;
  className?: string;
}) {
  return (
    <div className={`bg-slate-900 border border-slate-800 rounded-xl p-4 ${className}`}>
      <h3 className="text-sm font-semibold text-slate-200">{title}</h3>
      {hint && <p className="text-xs text-slate-500 mt-1 mb-3 leading-relaxed">{hint}</p>}
      {!hint && <div className="mb-3" />}
      {children}
    </div>
  );
}

export function Badge({
  tone = 'slate',
  children,
}: {
  tone?: 'slate' | 'emerald' | 'amber' | 'indigo' | 'red';
  children: ReactNode;
}) {
  const map = {
    slate: 'bg-slate-800 text-slate-300 border-slate-700',
    emerald: 'bg-emerald-500/10 text-emerald-400 border-emerald-500/20',
    amber: 'bg-amber-500/10 text-amber-400 border-amber-500/20',
    indigo: 'bg-indigo-500/10 text-indigo-300 border-indigo-500/20',
    red: 'bg-red-500/10 text-red-400 border-red-500/20',
  };
  return (
    <span className={`px-2 py-0.5 rounded-full text-[10px] font-semibold border ${map[tone]}`}>
      {children}
    </span>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <p className="text-sm text-slate-500">{children}</p>;
}
