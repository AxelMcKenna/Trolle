import { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { toast } from 'sonner';
import { Product, TrolleyItem } from '@/types';

interface TrolleyContextType {
  items: TrolleyItem[];
  itemCount: number;
  addItem: (product: Product) => void;
  removeItem: (productId: string) => void;
  updateQuantity: (productId: string, quantity: number) => void;
  clearTrolley: () => void;
  isInTrolley: (productId: string) => boolean;
  getItemQuantity: (productId: string) => number;
}

const TrolleyContext = createContext<TrolleyContextType | undefined>(undefined);

const STORAGE_KEY = 'grocify.trolley';
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

  const clearTrolley = useCallback(() => {
    setItems([]);
    toast.info('Trolley cleared');
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
