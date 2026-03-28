import { useState, useCallback } from 'react';

const STORAGE_KEY = 'trolle.recentlyViewed';
const MAX_ITEMS = 20;

export interface RecentProduct {
  id: string;
  name: string;
  image_url?: string | null;
  chain: string;
  price_nzd: number;
  size?: string | null;
}

function loadRecent(): RecentProduct[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

export const useRecentlyViewed = () => {
  const [recentlyViewed, setRecentlyViewed] = useState<RecentProduct[]>(loadRecent);

  const addViewed = useCallback((product: RecentProduct) => {
    setRecentlyViewed((prev) => {
      const filtered = prev.filter((p) => p.id !== product.id);
      const next = [product, ...filtered].slice(0, MAX_ITEMS);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const clearRecent = useCallback(() => {
    setRecentlyViewed([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { recentlyViewed, addViewed, clearRecent };
};
