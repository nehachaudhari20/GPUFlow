export type WorkloadType = 'TRAINING' | 'INFERENCE' | 'BATCH' | 'PREPROCESSING';
export type Priority = 'CRITICAL' | 'HIGH' | 'MEDIUM' | 'LOW';
export type WorkloadStatus = 'QUEUED' | 'SCHEDULED' | 'RUNNING' | 'COMPLETED' | 'FAILED' | 'CANCELLED';

export interface Workload {
  job_id: string;
  name: string;
  type: WorkloadType;
  cpu_required: number;
  gpu_required: number;
  gpu_memory_required: number;
  ram_required: number;
  priority: Priority;
  status: WorkloadStatus;
  estimated_duration: number;
  assigned_node?: string | null;
  started_at?: number | null;
  created_at: number;
  updated_at: number;
}

export interface WorkerNode {
  node_id: string;
  hostname: string;
  grpc_port: number;
  cpu_total: number;
  cpu_available: number;
  ram_total: number;
  ram_available: number;
  gpu_total: number;
  gpu_available: number;
  gpu_memory_total: number;
  gpu_memory_available: number;
  status: 'ONLINE' | 'OFFLINE' | 'MAINTENANCE';
  last_heartbeat: number;
  current_workloads?: string[];
}

export interface ClusterResourceResponse {
  total_gpus: number;
  available_gpus: number;
  total_cpus: number;
  available_cpus: number;
  total_ram: number;
  available_ram: number;
}

export interface NodeEvaluation {
  node_id: string;
  eligible: boolean;
  score: number;
  reason: string;
  metrics: {
    gpu_score: number;
    cpu_score: number;
    ram_score: number;
    health_score: number;
    load_score: number;
  };
}

export interface SchedulingDecision {
  job_id: string;
  allocation_success: boolean;
  selected_node?: string | null;
  reason: string;
  evaluations: NodeEvaluation[];
  timestamp: string;
}

export type EventType =
  | 'NODE_REGISTERED'
  | 'NODE_OFFLINE'
  | 'HEARTBEAT_RECEIVED'
  | 'JOB_SUBMITTED'
  | 'JOB_QUEUED'
  | 'NODE_EVALUATED'
  | 'NODE_REJECTED'
  | 'NODE_SELECTED'
  | 'RESOURCE_ALLOCATED'
  | 'TASK_ASSIGNED'
  | 'TASK_STARTED'
  | 'RESOURCE_UPDATED'
  | 'TASK_COMPLETED'
  | 'TASK_FAILED'
  | 'RESOURCE_RELEASED'
  | 'SYSTEM_ERROR';

export interface SystemEvent {
  event_id: string;
  timestamp: number;
  event_type: EventType;
  message: string;
  job_id?: string | null;
  node_id?: string | null;
  source?: string;
  destination?: string;
}
