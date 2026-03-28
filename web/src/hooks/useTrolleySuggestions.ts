import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { TrolleySuggestionsResponse } from '@/types';
import { api } from '@/lib/api';

interface SuggestionRequest {
  store_id: string;
  product_ids: string[];
}

export const useTrolleySuggestions = () => {
  const [suggestions, setSuggestions] = useState<TrolleySuggestionsResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);

  const fetchSuggestions = useCallback(
    async ({ store_id, product_ids }: SuggestionRequest) => {
      if (!product_ids.length) {
        setSuggestions(null);
        return;
      }

      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;

      setLoading(true);

      try {
        const { data } = await api.post<TrolleySuggestionsResponse>(
          `/trolley/suggestions`,
          {
            store_id,
            items: product_ids.map((id) => ({ product_id: id, quantity: 1 })),
          },
          { signal: controller.signal }
        );
        setSuggestions(data);
      } catch (err) {
        if (axios.isCancel(err)) return;
        setSuggestions(null);
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

  return { suggestions, loading, fetchSuggestions };
};
