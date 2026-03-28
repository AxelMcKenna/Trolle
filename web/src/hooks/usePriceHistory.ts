import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { PriceHistoryResponse } from "@/types";

export function usePriceHistory() {
  const [data, setData] = useState<PriceHistoryResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const fetchHistory = useCallback(
    async (productId: string, days: number = 90, storeId?: string) => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number> = { days };
        if (storeId) params.store_id = storeId;
        const res = await api.get(`/products/${productId}/price-history`, { params });
        setData(res.data);
      } catch (err: any) {
        setError(err?.response?.data?.detail ?? "Failed to load price history");
      } finally {
        setLoading(false);
      }
    },
    [],
  );

  return { data, loading, error, fetchHistory };
}
