import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { Recipe } from '@/types';
import { api } from '@/lib/api';

interface CreateRecipeInput {
  title: string;
  description?: string;
  servings: number;
  ingredients: { description: string }[];
}

export const useRecipeCreate = () => {
  const [recipe, setRecipe] = useState<Recipe | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeRequest = useRef<AbortController | null>(null);

  const createRecipe = useCallback(async (input: CreateRecipeInput) => {
    activeRequest.current?.abort();
    const controller = new AbortController();
    activeRequest.current = controller;

    setLoading(true);
    setError(null);

    try {
      const { data } = await api.post<Recipe>(`/recipes`, input, {
        signal: controller.signal,
      });
      setRecipe(data);
      return data;
    } catch (err) {
      if (axios.isCancel(err)) return null;
      setError('Failed to create recipe');
      return null;
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    return () => {
      activeRequest.current?.abort();
    };
  }, []);

  return { recipe, loading, error, createRecipe };
};
