import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { TrolleyItem, TrolleyCompareResponse } from '@/types';
import { api } from '@/lib/api';

export const useTrolleyCompare = () => {
  const [comparison, setComparison] = useState<TrolleyCompareResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);

  const compare = useCallback(
    async (items: TrolleyItem[], lat: number, lon: number, radiusKm: number, loyaltyCards?: Record<string, boolean>) => {
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;

      setLoading(true);
      setError(null);

      try {
        const { data } = await api.post<TrolleyCompareResponse>(
          `/trolley/compare`,
          {
            items: items.map((i) => ({
              product_id: i.product_id,
              quantity: i.quantity,
            })),
            lat,
            lon,
            radius_km: radiusKm,
            loyalty_cards: loyaltyCards,
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
