import React, { useEffect, useState } from 'react';
import { Button } from '@/components/ui/button';
import { Copy, Check, X, ArrowLeft } from 'lucide-react';
import { useWorkflow } from '../context/workflow-provider';
import { ensureAuth } from '@/lib/auth';

const SessionTokenView: React.FC = () => {
  const { goHomeView } = useWorkflow();
  const [token, setToken] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      try {
        const t = await ensureAuth();
        setToken(t);
      } catch (e: any) {
        setError(e?.message ?? 'Failed to get token');
      }
    })();
  }, []);

  const copy = async () => {
    if (!token) return;
    try {
      await navigator.clipboard.writeText(token);
      setCopied(true);
      setTimeout(() => setCopied(false), 1500);
    } catch {
      setError('Failed to copy to clipboard');
    }
  };

  return (
    <div className="p-4 space-y-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Login app</h2>
        <button className="text-sm text-gray-600 hover:text-black flex items-center gap-1" onClick={goHomeView}>
          <ArrowLeft className="w-4 h-4" /> Back
        </button>
      </div>

      <div className="bg-blue-50 rounded-lg p-3">
        <div className="text-sm text-blue-800">
          Copy token and go to <a href="https://app.rebrowse.me" target="_blank" rel="noopener noreferrer" className="underline font-medium">app.rebrowse.me</a>
        </div>
      </div>

      {error && <div className="text-xs text-red-600">{error}</div>}

      <div className="space-y-3">
        <div className="bg-white rounded border p-3">
          <div className="text-xs text-gray-500 mb-1">Session Token:</div>
          <div className="font-mono text-xs text-gray-800 break-all bg-gray-50 p-2 rounded min-h-10">
            {token ?? 'Loading...'}
          </div>
        </div>
        <div className="flex gap-2">
          <Button size="sm" onClick={copy} className="flex-1">
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
          <Button variant="outline" size="sm" onClick={goHomeView}>
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SessionTokenView;


