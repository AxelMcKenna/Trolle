import { useState, useCallback } from "react";
import { api } from "@/lib/api";

export interface SavedTrolley {
  id: string;
  name: string;
  items: any[];
  item_count: number;
  created_at: string;
  updated_at: string;
}

interface SavedTrolleyList {
  trolleys: SavedTrolley[];
  count: number;
}

interface CreateTrolleyBody {
  name: string;
  items: {
    product_id: string;
    name: string;
    brand?: string | null;
    size?: string | null;
    chain: string;
    image_url?: string | null;
    quantity: number;
  }[];
}

export const useSavedTrolleys = () => {
  const [trolleys, setTrolleys] = useState<SavedTrolley[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchTrolleys = useCallback(async () => {
    setLoading(true);
    try {
      const { data } = await api.get<SavedTrolleyList>("/trolleys");
      setTrolleys(data.trolleys);
    } catch {
      setTrolleys([]);
    } finally {
      setLoading(false);
    }
  }, []);

  const createTrolley = useCallback(async (body: CreateTrolleyBody): Promise<SavedTrolley | null> => {
    try {
      const { data } = await api.post<SavedTrolley>("/trolleys", body);
      setTrolleys((prev) => [data, ...prev]);
      return data;
    } catch {
      return null;
    }
  }, []);

  const updateTrolley = useCallback(async (id: string, body: Partial<CreateTrolleyBody>): Promise<SavedTrolley | null> => {
    try {
      const { data } = await api.put<SavedTrolley>(`/trolleys/${id}`, body);
      setTrolleys((prev) => prev.map((t) => (t.id === id ? data : t)));
      return data;
    } catch {
      return null;
    }
  }, []);

  const deleteTrolley = useCallback(async (id: string): Promise<boolean> => {
    try {
      await api.delete(`/trolleys/${id}`);
      setTrolleys((prev) => prev.filter((t) => t.id !== id));
      return true;
    } catch {
      return false;
    }
  }, []);

  return {
    trolleys,
    loading,
    fetchTrolleys,
    createTrolley,
    updateTrolley,
    deleteTrolley,
  };
};
