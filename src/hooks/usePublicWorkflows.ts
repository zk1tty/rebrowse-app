import { useEffect, useState } from 'react';
import { apiFetch } from '@/lib/api';

export function usePublicWorkflows() {
  const [rows, setRows] = useState<any[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchWorkflows = async () => {
      try {
        setLoading(true);
        setError(null);
        const workflows = await apiFetch<any[]>('/workflows/', { auth: false });
        setRows(workflows);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch workflows');
      } finally {
        setLoading(false);
      }
    };

    fetchWorkflows();
  }, []);

  return { rows, loading, error };
} 