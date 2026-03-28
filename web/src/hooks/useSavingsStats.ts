import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';

export interface SavingsStats {
  total_comparisons: number;
  total_savings: number;
  average_savings: number;
  most_used_store: string | null;
  comparisons_this_month: number;
  savings_this_month: number;
}

export interface ComparisonHistoryItem {
  id: string;
  cheapest_store_name: string | null;
  cheapest_total: number;
  most_expensive_total: number;
  savings: number;
  item_count: number;
  created_at: string;
}

export const useSavingsStats = () => {
  const [stats, setStats] = useState<SavingsStats | null>(null);
  const [history, setHistory] = useState<ComparisonHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  const fetchStats = useCallback(async () => {
    setLoading(true);
    try {
      const [statsRes, historyRes] = await Promise.all([
        api.get<SavingsStats>('/trolley/history/stats'),
        api.get<{ items: ComparisonHistoryItem[]; count: number }>('/trolley/history?limit=10'),
      ]);
      setStats(statsRes.data);
      setHistory(historyRes.data.items);
    } catch {
      // Non-critical — just show empty state
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchStats();
  }, [fetchStats]);

  return { stats, history, loading, refetch: fetchStats };
};
