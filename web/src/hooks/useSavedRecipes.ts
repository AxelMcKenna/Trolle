import { useState, useCallback } from "react";
import { api } from "@/lib/api";

export interface SavedRecipeItem {
  id: string;
  recipe_id: string;
  title: string;
  description: string | null;
  servings: number;
  image_url: string | null;
  ingredient_count: number;
  saved_at: string;
}

interface SavedRecipeList {
  recipes: SavedRecipeItem[];
  count: number;
}

export const useSavedRecipes = () => {
  const [recipes, setRecipes] = useState<SavedRecipeItem[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchSavedRecipes = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<SavedRecipeList>("/recipes/saved/list");
      setRecipes(data.recipes);
    } catch {
      setRecipes([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const saveRecipe = useCallback(async (recipeId: string): Promise<boolean> => {
    try {
      await api.post(`/recipes/${recipeId}/save`);
      return true;
    } catch {
      return false;
    }
  }, []);

  const unsaveRecipe = useCallback(async (recipeId: string): Promise<boolean> => {
    try {
      await api.delete(`/recipes/${recipeId}/save`);
      setRecipes((prev) => prev.filter((r) => r.recipe_id !== recipeId));
      return true;
    } catch {
      return false;
    }
  }, []);

  const checkSaved = useCallback(async (recipeId: string): Promise<boolean> => {
    try {
      const { data } = await api.get<{ saved: boolean }>(`/recipes/${recipeId}/saved`);
      return data.saved;
    } catch {
      return false;
    }
  }, []);

  return {
    recipes,
    loading,
    fetchSavedRecipes,
    saveRecipe,
    unsaveRecipe,
    checkSaved,
  };
};
