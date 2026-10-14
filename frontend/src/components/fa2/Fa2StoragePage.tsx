import { useState } from 'react';
import { useFa2Poll } from '../../hooks/useFa2Data';

export default function Fa2StoragePage() {
  const files = useFa2Poll<{ files: Array<Record<string, unknown>> }>('/fa2/storage/files');
  const [uploading, setUploading] = useState(false);
  const [msg, setMsg] = useState('');

  const onUpload = async (f: File) => {
    setUploading(true);
    setMsg('');
    try {
      const fd = new FormData();
      fd.append('file', f);
      const res = await fetch('/fa2/storage/files', { method: 'POST', body: fd });
      const body = await res.json();
      if (!res.ok) throw new Error(body.detail || res.statusText);
      setMsg(`Uploaded ${body.metadata?.file_id}`);
      files.refresh();
    } catch (e) {
      setMsg(e instanceof Error ? e.message : 'Upload failed');
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="space-y-4">
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <label className="text-sm block mb-2">Upload (replicated to workers)</label>
        <input
          type="file"
          disabled={uploading}
          onChange={(e) => e.target.files?.[0] && onUpload(e.target.files[0])}
          className="text-xs"
        />
        {msg && <p className="text-xs mt-2 text-slate-400">{msg}</p>}
      </div>
      <div className="bg-slate-900 border border-slate-800 rounded-xl p-4">
        <h3 className="text-sm font-semibold mb-2">Files</h3>
        {!files.data?.files?.length && <p className="text-slate-500 text-sm">No files stored.</p>}
        <table className="w-full text-xs">
          <thead>
            <tr className="text-slate-500 text-left">
              <th className="p-2">Name</th>
              <th>Size</th>
              <th>Replicas</th>
              <th>Status</th>
            </tr>
          </thead>
          <tbody>
            {files.data?.files?.map((f) => (
              <tr key={String(f.file_id)} className="border-t border-slate-800">
                <td className="p-2 font-mono">{String(f.original_filename)}</td>
                <td>{String(f.size_bytes)}</td>
                <td>{JSON.stringify(f.replica_nodes)}</td>
                <td>{String(f.replication_status)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
