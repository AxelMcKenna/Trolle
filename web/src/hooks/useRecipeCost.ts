import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { RecipeCostResponse } from '@/types';
import { api } from '@/lib/api';

export const useRecipeCost = () => {
  const [costData, setCostData] = useState<RecipeCostResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);

  const compareCost = useCallback(
    async (recipeId: string, lat: number, lon: number, radiusKm: number) => {
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;

      setLoading(true);
      setError(null);

      try {
        const { data } = await api.post<RecipeCostResponse>(
          `/recipes/compare`,
          {
            recipe_id: recipeId,
            lat,
            lon,
            radius_km: radiusKm,
          },
          { signal: controller.signal }
        );
        setCostData(data);
      } catch (err) {
        if (axios.isCancel(err)) return;
        setError('Failed to compare recipe costs');
        setCostData(null);
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

  return { costData, loading, error, compareCost };
};
