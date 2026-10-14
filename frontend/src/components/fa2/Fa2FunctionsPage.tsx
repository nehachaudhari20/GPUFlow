import { useState } from 'react';
import { useFa2Poll } from '../../hooks/useFa2Data';

export default function Fa2FunctionsPage() {
  const fnList = useFa2Poll<{ functions: string[] }>('/fa2/functions');
  const scale = useFa2Poll<Record<string, unknown>>('/fa2/autoscaling/status');
  const [name, setName] = useState('calculate_fibonacci');
  const [params, setParams] = useState('{"n": 10}');
  const [result, setResult] = useState('');

  const invoke = async () => {
    setResult('');
    try {
      const res = await fetch('/fa2/functions/invoke', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          function_name: name,
          parameters: JSON.parse(params),
          cpu_required: 0.5,
          ram_required: 0.5,
          timeout: 15,
        }),
      });
      setResult(JSON.stringify(await res.json(), null, 2));
    } catch (e) {
      setResult(String(e));
    }
  };

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4 space-y-3">
        <h3 className="text-sm font-semibold">Serverless-style invoke (allowlist)</h3>
        <p className="text-xs text-slate-400">
          Scheduler picks a CPU worker; the function runs on that worker via gRPC <code>InvokeFunction</code>.
        </p>
        <select value={name} onChange={(e) => setName(e.target.value)} className="w-full bg-slate-950 border border-slate-700 rounded p-2 text-xs">
          {(fnList.data?.functions ?? []).map((f) => (
            <option key={f} value={f}>
              {f}
            </option>
          ))}
        </select>
        <textarea
          value={params}
          onChange={(e) => setParams(e.target.value)}
          className="w-full h-24 bg-slate-950 border border-slate-700 rounded p-2 text-xs font-mono"
        />
        <button onClick={invoke} className="px-3 py-2 bg-indigo-600 rounded text-xs">
          Invoke
        </button>
        <pre className="text-xs overflow-auto max-h-48">{result}</pre>
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-semibold mb-2">Autoscaling (decision only)</h3>
        <p className="text-xs text-amber-400/90 mb-2">Does not provision EC2 instances.</p>
        <pre className="text-xs font-mono overflow-auto">{JSON.stringify(scale.data, null, 2)}</pre>
      </div>
    </div>
  );
}
