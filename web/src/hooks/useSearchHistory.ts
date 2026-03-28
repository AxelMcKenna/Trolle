import { useState, useCallback } from 'react';

const STORAGE_KEY = 'trolle.searchHistory';
const MAX_ITEMS = 10;

function loadHistory(): string[] {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored ? JSON.parse(stored) : [];
  } catch {
    return [];
  }
}

export const useSearchHistory = () => {
  const [recentSearches, setRecentSearches] = useState<string[]>(loadHistory);

  const addSearch = useCallback((query: string) => {
    const q = query.trim();
    if (!q) return;

    setRecentSearches((prev) => {
      const filtered = prev.filter((s) => s.toLowerCase() !== q.toLowerCase());
      const next = [q, ...filtered].slice(0, MAX_ITEMS);
      localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const clearHistory = useCallback(() => {
    setRecentSearches([]);
    localStorage.removeItem(STORAGE_KEY);
  }, []);

  return { recentSearches, addSearch, clearHistory };
};
