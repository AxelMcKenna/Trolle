import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { TrolleyItem, TrolleyCompareResponse } from '@/types';

const API_BASE = import.meta.env.VITE_API_URL ?? "http://localhost:8000";

export const useTrolleyCompare = () => {
  const [comparison, setComparison] = useState<TrolleyCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);

  const compare = useCallback(
    async (items: TrolleyItem[], lat: number, lon: number, radiusKm: number) => {
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;

      setLoading(true);
      setError(null);

      try {
        const { data } = await axios.post<TrolleyCompareResponse>(
          `${API_BASE}/trolley/compare`,
          {
            items: items.map((i) => ({
              product_id: i.product_id,
              quantity: i.quantity,
            })),
            lat,
            lon,
            radius_km: radiusKm,
          },
          { signal: controller.signal }
        );
        setComparison(data);
      } catch (err) {
        if (axios.isCancel(err)) return;
        setError('Failed to compare trolley prices');
        setComparison(null);
      } finally {
        setLoading(false);
      }
    },
    []
  );

  useEffect(() => {
    return () => {
      activeRequest.current?.abort();
    };
  }, []);

  return { comparison, loading, error, compare };
};
