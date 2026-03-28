import { useState, useCallback, useEffect } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { api } from '@/lib/api';

const STORAGE_KEY = 'trolle.loyaltyCards';
const DEFAULT_LOYALTY_CARDS: Record<string, boolean> = {
  countdown: true,
  new_world: true,
  paknsave: true,
};

function loadFromStorage(): Record<string, boolean> {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) return JSON.parse(stored);
  } catch {
    // ignore
  }
  return { ...DEFAULT_LOYALTY_CARDS };
}

export const useLoyaltyCards = () => {
  const [loyaltyCards, setLoyaltyCardsState] = useState<Record<string, boolean>>(loadFromStorage);
  const { isAuthenticated } = useAuth();

  // Sync from server on mount when authenticated
  useEffect(() => {
    if (!isAuthenticated) return;
    api.get('/users/me').then(({ data }) => {
      if (data.loyalty_cards) {
        setLoyaltyCardsState(data.loyalty_cards);
        localStorage.setItem(STORAGE_KEY, JSON.stringify(data.loyalty_cards));
      }
    }).catch(() => {
      // Use local state as fallback
    });
  }, [isAuthenticated]);

  const setLoyaltyCard = useCallback((chain: string, hasCard: boolean) => {
    setLoyaltyCardsState((prev) => {
      const updated = { ...prev, [chain]: hasCard };
      localStorage.setItem(STORAGE_KEY, JSON.stringify(updated));

      // Persist to server if authenticated (fire-and-forget)
      if (isAuthenticated) {
        api.patch('/users/me', { loyalty_cards: updated }).catch(() => {
          // Silent fail — localStorage is source of truth for unauth
        });
      }

      return updated;
    });
  }, [isAuthenticated]);

  return { loyaltyCards, setLoyaltyCard };
};
