import { useState, useEffect } from 'react';
import type { WorkerNode, Workload, SystemEvent, ClusterResourceResponse } from '../types';

export function useClusterData() {
  const [nodes, setNodes] = useState<WorkerNode[]>([]);
  const [workloads, setWorkloads] = useState<Workload[]>([]);
  const [resources, setResources] = useState<ClusterResourceResponse | null>(null);
  const [events, setEvents] = useState<SystemEvent[]>([]);

  const fetchData = async () => {
    try {
      const [nodesRes, workloadsRes, resourcesRes, eventsRes] = await Promise.all([
        fetch('/nodes').then(r => r.json()),
        fetch('/workloads').then(r => r.json()),
        fetch('/cluster').then(r => r.json()),
        fetch('/events').then(r => r.json()),
      ]);
      setNodes(nodesRes.nodes || []);
      setWorkloads(workloadsRes.workloads || []);
      setResources({
        total_gpus: resourcesRes.gpu_total ?? 0,
        available_gpus: resourcesRes.gpu_available ?? 0,
        total_cpus: resourcesRes.cpu_total ?? 0,
        available_cpus: resourcesRes.cpu_available ?? 0,
        total_ram: resourcesRes.ram_total ?? 0,
        available_ram: resourcesRes.ram_available ?? 0,
      });
      setEvents(Array.isArray(eventsRes) ? eventsRes : eventsRes.events || []);
    } catch (e) {
      console.error("Error fetching cluster data:", e);
    }
  };

  useEffect(() => {
    fetchData();

    // Use absolute URL since proxy setup in Vite only works for fetch, not always for native WS in dev mode perfectly
    // if using just relative `/ws`, it tries window.location.host which is the dev server,
    // which delegates to target in proxy config.
    const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${wsProtocol}//${window.location.host}/ws`;
    const ws = new WebSocket(wsUrl);

    ws.onerror = () => {
      // WebSocket is optional; REST polling still works
    };

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        if (data.type === 'EVENT') {
          const sysEvent = data.data as SystemEvent;
          setEvents(prev => [sysEvent, ...prev].slice(0, 500));
          fetchData();
        }
      } catch {
        // Ignore malformed websocket payloads
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  return { nodes, workloads, resources, events, refresh: fetchData };
}
