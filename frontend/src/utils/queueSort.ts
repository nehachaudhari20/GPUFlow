import type { Workload } from '../types';

export const PRIORITY_ORDER: Record<string, number> = {
  CRITICAL: 0,
  HIGH: 1,
  MEDIUM: 2,
  LOW: 3,
};

/** Matches backend WorkloadQueue default_queue_sort_key: priority first, then FCFS. */
export function sortQueuedWorkloads(workloads: Workload[]): Workload[] {
  return [...workloads]
    .filter(w => w.status === 'QUEUED')
    .sort((a, b) => {
      const priorityDiff = (PRIORITY_ORDER[a.priority] ?? 99) - (PRIORITY_ORDER[b.priority] ?? 99);
      if (priorityDiff !== 0) return priorityDiff;
      return a.created_at - b.created_at;
    });
}

export function getNextQueuedJob(workloads: Workload[]): Workload | undefined {
  const ordered = sortQueuedWorkloads(workloads);
  return ordered[0];
}
