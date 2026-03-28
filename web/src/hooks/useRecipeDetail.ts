import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { Recipe } from '@/types';
import { api } from '@/lib/api';

export const useRecipeDetail = () => {
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);

  const fetchRecipe = useCallback(async (id: string) => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;

    setLoading(true);
    setError(null);

    try {
      const { data } = await api.get<Recipe>(`/recipes/${id}`, {
        signal: controller.signal,
      });
      setRecipe(data);
    } catch (err) {
      if (axios.isCancel(err)) return;
      setError('Failed to load recipe');
      setRecipe(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    return () => {
      activeRequest.current?.abort();
    };
  }, []);

  return { recipe, loading, error, fetchRecipe };
};
