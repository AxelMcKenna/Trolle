import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { RecipeListResponse } from '@/types';
import { api } from '@/lib/api';

export const useRecipes = () => {
  const [recipes, setRecipes] = useState<RecipeListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);

  const fetchRecipes = useCallback(
    async (params: { q?: string; limit?: number; offset?: number } = {}) => {
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;

      setLoading(true);
      setError(null);

      try {
        const { data } = await api.get<RecipeListResponse>(`/recipes`, {
          params,
          signal: controller.signal,
        });
        setRecipes(data);
      } catch (err) {
        if (axios.isCancel(err)) return;
        setError('Failed to load recipes');
        setRecipes(null);
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

  return { recipes, loading, error, fetchRecipes };
};
