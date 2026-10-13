import React, { useEffect, useState } from 'react';
import { Loader2, Play } from 'lucide-react';
import { fetchBlobUrl } from '../services/api';

interface AuthAudioProps {
  filename: string;
}

/**
 * Retained recordings are only served to authorised, signed-in users and every fetch is audited,
 * so the audio is loaded on request (with the bearer token) instead of via a bare <audio src>.
 */
export const AuthAudio: React.FC<AuthAudioProps> = ({ filename }) => {
  const [url, setUrl] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (url) URL.revokeObjectURL(url);
    };
  }, [url]);

  const load = async () => {
    setLoading(true);
    setError(null);
    try {
      setUrl(await fetchBlobUrl(`/api/audio/${encodeURIComponent(filename)}`));
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  };

  if (url) return <audio controls src={url} className="h-8 max-w-full sm:max-w-xs" />;
  return (
    <div className="flex items-center gap-2">
      <button
        type="button"
        onClick={load}
        disabled={loading}
        className="px-3 py-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 border border-slate-700 text-xs font-semibold text-slate-200 flex items-center gap-1.5 disabled:opacity-60"
      >
        {loading ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Play className="w-3.5 h-3.5" />}
        <span>{loading ? 'Loading…' : 'Load recording'}</span>
      </button>
      {error && <span role="alert" className="text-[11px] text-rose-300">{error}</span>}
    </div>
  );
};
