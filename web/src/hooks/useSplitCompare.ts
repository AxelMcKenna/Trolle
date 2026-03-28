import { useState, useCallback, useRef, useEffect } from 'react';
import axios from 'axios';
import { api } from '@/lib/api';

interface SplitItem {
  product_id: string;
  quantity: number;
}

interface SplitAssignmentItem {
  source_product_name: string;
  matched_product_name: string | null;
  price: number | null;
  quantity: number;
  line_total: number | null;
}

interface SplitAssignment {
  store_id: string;
  store_name: string;
  chain: string;
  distance_km: number;
  subtotal: number;
  items: SplitAssignmentItem[];
}

interface SplitLevel {
  num_stores: number;
  grand_total: number;
  assignments: SplitAssignment[];
}

interface SplitCompareData {
  single_best_total: number;
  savings_vs_single: number;
  splits: SplitLevel[];
}

interface StoreItem {
  source_product_id: string;
  source_product_name: string;
  quantity: number;
  available: boolean;
  matched_product_id: string | null;
  matched_product_name: string | null;
  price: number | null;
  line_total: number | null;
}

interface StoreBreakdown {
  store_id: string;
  store_name: string;
  chain: string;
  distance_km: number;
  estimated_total: number;
  items_available: number;
  items_total: number;
  is_complete: boolean;
  items: StoreItem[];
}

/**
 * Client-side split-shopping optimiser.
 * Calls the existing /trolley/compare endpoint then greedily assigns each item
 * to the cheapest store that stocks it, constrained to at most `maxStores`.
 */
export const useSplitCompare = () => {
  const [data, setData] = useState<SplitCompareData | null>(null);
  const [loading, setLoading] = useState(false);
  const activeRequest = useRef<AbortController | null>(null);

  const compare = useCallback(
    async (
      items: SplitItem[],
      lat: number,
      lon: number,
      radiusKm: number,
      maxStores: number,
      loyaltyCards?: Record<string, boolean>,
    ) => {
      activeRequest.current?.abort();
      const controller = new AbortController();
      activeRequest.current = controller;

      setLoading(true);

      try {
        const { data: raw } = await api.post<{ stores: StoreBreakdown[] }>(
          '/trolley/compare',
          {
            items: items.map((i) => ({
              product_id: i.product_id,
              quantity: i.quantity,
            })),
            lat,
            lon,
            radius_km: radiusKm,
            loyalty_cards: loyaltyCards,
          },
          { signal: controller.signal },
        );

        const stores = raw.stores;
        if (!stores.length) {
          setData(null);
          return;
        }

        // Best single-store total (cheapest complete store, or cheapest overall)
        const completeStores = stores.filter((s) => s.is_complete);
        const singleBest = completeStores.length
          ? completeStores.reduce((a, b) => (a.estimated_total < b.estimated_total ? a : b))
          : stores.reduce((a, b) => (a.estimated_total < b.estimated_total ? a : b));
        const singleBestTotal = singleBest.estimated_total;

        // Build per-item price map: productId -> [{storeIdx, price, storeItem}]
        type PriceEntry = { storeIdx: number; price: number; storeItem: StoreItem };
        const priceMap = new Map<string, PriceEntry[]>();

        stores.forEach((store, storeIdx) => {
          store.items.forEach((item) => {
            if (!item.available || item.price == null) return;
            const entries = priceMap.get(item.source_product_id) ?? [];
            entries.push({ storeIdx, price: item.price, storeItem: item });
            priceMap.set(item.source_product_id, entries);
          });
        });

        // Greedy split: assign each item to its cheapest store, limited to maxStores
        // 1. Score each item's cheapest store
        const itemCheapest = items.map((item) => {
          const entries = priceMap.get(item.product_id);
          if (!entries?.length) return null;
          entries.sort((a, b) => a.price - b.price);
          return entries;
        });

        // 2. Greedy: pick items for cheapest stores, cap at maxStores
        const usedStores = new Set<number>();
        const assignments = new Map<number, { items: { si: StoreItem; qty: number }[] }>();

        // First pass — assign items to their cheapest store, track which stores used
        const itemAssignment: (number | null)[] = items.map(() => null);

        // Sort items by savings potential (diff between cheapest and 2nd cheapest)
        const order = items.map((_, i) => i);

        for (const i of order) {
          const entries = itemCheapest[i];
          if (!entries) continue;
          // Find cheapest store that's either already used or we still have budget
          for (const entry of entries) {
            if (usedStores.has(entry.storeIdx) || usedStores.size < maxStores) {
              usedStores.add(entry.storeIdx);
              itemAssignment[i] = entry.storeIdx;
              const asg = assignments.get(entry.storeIdx) ?? { items: [] };
              asg.items.push({ si: entry.storeItem, qty: items[i].quantity });
              assignments.set(entry.storeIdx, asg);
              break;
            }
          }
          // Fallback: if all stores full, pick cheapest among used stores
          if (itemAssignment[i] == null) {
            for (const entry of entries) {
              if (usedStores.has(entry.storeIdx)) {
                itemAssignment[i] = entry.storeIdx;
                const asg = assignments.get(entry.storeIdx) ?? { items: [] };
                asg.items.push({ si: entry.storeItem, qty: items[i].quantity });
                assignments.set(entry.storeIdx, asg);
                break;
              }
            }
          }
        }

        // Build result
        const splitAssignments: SplitAssignment[] = [];
        let grandTotal = 0;

        assignments.forEach((asg, storeIdx) => {
          const store = stores[storeIdx];
          let subtotal = 0;
          const assignedItems: SplitAssignmentItem[] = asg.items.map(({ si, qty }) => {
            const lt = (si.price ?? 0) * qty;
            subtotal += lt;
            return {
              source_product_name: si.source_product_name,
              matched_product_name: si.matched_product_name,
              price: si.price,
              quantity: qty,
              line_total: lt,
            };
          });
          grandTotal += subtotal;
          splitAssignments.push({
            store_id: store.store_id,
            store_name: store.store_name,
            chain: store.chain,
            distance_km: store.distance_km,
            subtotal,
            items: assignedItems,
          });
        });

        splitAssignments.sort((a, b) => b.subtotal - a.subtotal);

        setData({
          single_best_total: singleBestTotal,
          savings_vs_single: Math.max(0, singleBestTotal - grandTotal),
          splits: [
            {
              num_stores: splitAssignments.length,
              grand_total: grandTotal,
              assignments: splitAssignments,
            },
          ],
        });
      } catch (err) {
        if (axios.isCancel(err)) return;
        setData(null);
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  useEffect(() => {
    return () => {
      activeRequest.current?.abort();
    };
  }, []);

  return { data, loading, compare };
};
