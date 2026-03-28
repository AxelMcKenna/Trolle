import { createContext, useContext, useState, useEffect, useCallback, useRef, ReactNode } from 'react';
import { toast } from 'sonner';
import { Product, TrolleyItem } from '@/types';
import { supabase } from '@/lib/supabase';
import { api } from '@/lib/api';

interface TrolleyItemInput {
  product_id: string;
  name: string;
  brand?: string | null;
  size?: string | null;
  chain: string;
  image_url?: string | null;
  department?: string | null;
}

interface TrolleyContextType {
  items: TrolleyItem[];
  itemCount: number;
  addItem: (product: Product) => void;
  addItems: (products: TrolleyItemInput[]) => number;
  removeItem: (productId: string) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  clearTrolley: () => void;
  isInTrolley: (productId: string) => boolean;
  getItemQuantity: (productId: string) => number;
}

const TrolleyContext = createContext<TrolleyContextType | undefined>(undefined);

const STORAGE_KEY = 'trolle.trolley';
const MAX_ITEMS = 50;

export const TrolleyProvider = ({ children }: { children: ReactNode }) => {
  const [items, setItems] = useState<TrolleyItem[]>(() => {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
      try {
        return JSON.parse(stored) as TrolleyItem[];
      } catch {
        return [];
      }
    }
    return [];
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  // Sync local trolley to cloud on first sign-in
  const syncedRef = useRef(false);
  useEffect(() => {
    if (!supabase) return;

    const { data: { subscription } } = supabase.auth.onAuthStateChange(async (event) => {
      if (event === 'SIGNED_IN' && !syncedRef.current) {
        syncedRef.current = true;
        const stored = localStorage.getItem(STORAGE_KEY);
        if (!stored) return;
        try {
          const localItems = JSON.parse(stored) as TrolleyItem[];
          if (localItems.length === 0) return;

          // Check if user already has saved trolleys
          const { data } = await api.get<{ count: number }>('/trolleys');
          if (data.count > 0) return; // Don't overwrite existing saved trolleys

          await api.post('/trolleys', {
            name: 'My Trolley',
            items: localItems.map((i) => ({
              product_id: i.product_id,
              name: i.name,
              brand: i.brand,
              size: i.size,
              chain: i.chain,
              image_url: i.image_url,
              quantity: i.quantity,
            })),
          });
        } catch {
          // Silent fail — non-critical
        }
      }
      if (event === 'SIGNED_OUT') {
        syncedRef.current = false;
      }
    });

    return () => subscription.unsubscribe();
  }, []);

  const addItem = useCallback((product: Product) => {
    setItems((prev) => {
      const existing = prev.find((i) => i.product_id === product.id);
      if (existing) {
        toast.info(`Already in trolley (x${existing.quantity})`);
        return prev;
      }
      if (prev.length >= MAX_ITEMS) {
        toast.error(`Trolley is full (max ${MAX_ITEMS} items)`);
        return prev;
      }
      toast.success(`Added ${product.name} to trolley`);
      return [
        ...prev,
        {
          product_id: product.id,
          name: product.name,
          brand: product.brand,
          size: product.size,
          chain: product.chain,
          image_url: product.image_url,
          department: product.department,
          quantity: 1,
        },
      ];
    });
  }, []);

  const addItems = useCallback((products: TrolleyItemInput[]): number => {
    let added = 0;
    setItems((prev) => {
      const existingIds = new Set(prev.map((i) => i.product_id));
      const remaining = MAX_ITEMS - prev.length;
      const newItems: TrolleyItem[] = [];

      for (const p of products) {
        if (existingIds.has(p.product_id)) continue;
        if (newItems.length >= remaining) break;
        existingIds.add(p.product_id);
        newItems.push({
          product_id: p.product_id,
          name: p.name,
          brand: p.brand,
          size: p.size,
          chain: p.chain,
          image_url: p.image_url,
          department: p.department,
          quantity: 1,
        });
      }
      added = newItems.length;
      if (newItems.length > 0) {
        return [...prev, ...newItems];
      }
      return prev;
    });
    if (added > 0) {
      toast.success(`Added ${added} item${added > 1 ? 's' : ''} to trolley`);
    }
    return added;
  }, []);

  const removeItem = useCallback((productId: string) => {
    setItems((prev) => {
      const item = prev.find((i) => i.product_id === productId);
      if (item) {
        toast.info(`Removed ${item.name} from trolley`);
      }
      return prev.filter((i) => i.product_id !== productId);
    });
  }, []);

  const updateQuantity = useCallback((productId: string, quantity: number) => {
    const clamped = Math.max(1, Math.min(99, quantity));
    setItems((prev) =>
      prev.map((i) =>
        i.product_id === productId ? { ...i, quantity: clamped } : i
      )
    );
  }, []);

  const previousItemsRef = useRef<TrolleyItem[]>([]);

  const clearTrolley = useCallback(() => {
    setItems((prev) => {
      previousItemsRef.current = prev;
      return [];
    });
    toast('Trolley cleared', {
      action: {
        label: 'Undo',
        onClick: () => {
          setItems(previousItemsRef.current);
          toast.success('Trolley restored');
        },
      },
      duration: 5000,
    });
  }, []);

  const isInTrolley = useCallback(
    (productId: string) => items.some((i) => i.product_id === productId),
    [items]
  );

  const getItemQuantity = useCallback(
    (productId: string) => items.find((i) => i.product_id === productId)?.quantity ?? 0,
    [items]
  );

  const value: TrolleyContextType = {
    items,
    itemCount: items.length,
    addItem,
    addItems,
    removeItem,
    updateQuantity,
    clearTrolley,
    isInTrolley,
    getItemQuantity,
  };

  return (
    <TrolleyContext.Provider value={value}>
      {children}
    </TrolleyContext.Provider>
  );
};

export const useTrolleyContext = () => {
  const context = useContext(TrolleyContext);
  if (!context) {
    throw new Error('useTrolleyContext must be used within TrolleyProvider');
  }
  return context;
};
