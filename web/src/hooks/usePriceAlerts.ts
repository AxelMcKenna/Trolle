import { useState, useCallback } from "react";
import { api } from "@/lib/api";
import type { PriceAlert, NotificationsResponse } from "@/types";

export function usePriceAlerts() {
  const [alerts, setAlerts] = useState<PriceAlert[]>([]);
  const [loading, setLoading] = useState(false);

  const fetchAlerts = useCallback(async (activeOnly = false) => {
    setLoading(true);
    try {
      const res = await api.get("/alerts", { params: { active_only: activeOnly } });
      setAlerts(res.data.items);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, []);

  const createAlert = useCallback(
    async (productId: string, targetPrice: number, storeId?: string) => {
      const body: Record<string, any> = { product_id: productId, target_price: targetPrice };
      if (storeId) body.store_id = storeId;
      const res = await api.post("/alerts", body);
      return res.data as PriceAlert;
    },
    [],
  );

  const deleteAlert = useCallback(async (alertId: string) => {
    await api.delete(`/alerts/${alertId}`);
    setAlerts((prev) => prev.filter((a) => a.id !== alertId));
  }, []);

  return { alerts, loading, fetchAlerts, createAlert, deleteAlert };
}

export function useNotifications() {
  const [notifications, setNotifications] = useState<NotificationsResponse>({
    items: [],
    unread_count: 0,
  });
  const [loading, setLoading] = useState(false);

  const fetchNotifications = useCallback(async (limit = 20) => {
    setLoading(true);
    try {
      const res = await api.get("/alerts/notifications", { params: { limit } });
      setNotifications(res.data);
    } catch {
      // silent — user may not be authenticated
    } finally {
      setLoading(false);
    }
  }, []);

  const markRead = useCallback(async (ids?: string[]) => {
    const body = ids ? { notification_ids: ids } : { all: true };
    await api.post("/alerts/notifications/mark-read", body);
    setNotifications((prev) => ({
      ...prev,
      unread_count: ids ? Math.max(0, prev.unread_count - ids.length) : 0,
      items: prev.items.map((n) =>
        !ids || ids.includes(n.id) ? { ...n, is_read: true } : n,
      ),
    }));
  }, []);

  return { notifications, loading, fetchNotifications, markRead };
}
