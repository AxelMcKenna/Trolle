import { useEffect, useState, useMemo } from "react";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Legend,
} from "recharts";
import { usePriceHistory } from "@/hooks/usePriceHistory";
import { getChainColor, getChainName } from "@/lib/chainConstants";
import { Skeleton } from "@/components/ui/skeleton";
import type { StoreHistoryGroup } from "@/types";

interface PriceHistoryChartProps {
  productId: string;
}

const DAY_OPTIONS = [30, 90, 180, 365] as const;

export function PriceHistoryChart({ productId }: PriceHistoryChartProps) {
  const { data, loading, error, fetchHistory } = usePriceHistory();
  const [days, setDays] = useState<number>(90);
  const [visibleStores, setVisibleStores] = useState<Set<string>>(new Set());

  useEffect(() => {
    fetchHistory(productId, days);
  }, [productId, days, fetchHistory]);

  // Auto-select first 3 stores when data loads
  useEffect(() => {
    if (data?.stores?.length) {
      setVisibleStores(new Set(data.stores.slice(0, 3).map((s) => s.store_id)));
    }
  }, [data]);

  // Build unified timeline data for recharts
  const chartData = useMemo(() => {
    if (!data?.stores?.length) return [];

    const timeMap = new Map<string, Record<string, number | string>>();

    for (const store of data.stores) {
      if (!visibleStores.has(store.store_id)) continue;
      for (const pt of store.data_points) {
        const dateKey = new Date(pt.recorded_at).toLocaleDateString("en-NZ", {
          day: "numeric",
          month: "short",
        });
        if (!timeMap.has(pt.recorded_at)) {
          timeMap.set(pt.recorded_at, { date: dateKey, _ts: pt.recorded_at });
        }
        const effectivePrice = pt.promo_price_nzd ?? pt.price_nzd;
        timeMap.get(pt.recorded_at)![store.store_id] = effectivePrice;
      }
    }

    return Array.from(timeMap.values()).sort((a, b) =>
      (a._ts as string).localeCompare(b._ts as string),
    );
  }, [data, visibleStores]);

  const toggleStore = (storeId: string) => {
    setVisibleStores((prev) => {
      const next = new Set(prev);
      if (next.has(storeId)) next.delete(storeId);
      else next.add(storeId);
      return next;
    });
  };

  if (loading) {
    return (
      <div className="space-y-3 py-4">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-48 w-full" />
      </div>
    );
  }

  if (error) {
    return <p className="text-sm text-secondary-gray py-4">{error}</p>;
  }

  if (!data?.stores?.length) {
    return (
      <p className="text-sm text-secondary-gray py-4">
        No price history available yet. History will build up as prices change.
      </p>
    );
  }

  return (
    <div className="py-4 space-y-3">
      {/* Day range selector */}
      <div className="flex items-center gap-2">
        <span className="text-xs text-secondary-gray font-medium">Range:</span>
        {DAY_OPTIONS.map((d) => (
          <button
            key={d}
            onClick={() => setDays(d)}
            className={`text-xs px-2 py-1 rounded-md transition-colors ${
              days === d
                ? "bg-primary text-white"
                : "bg-secondary/50 text-secondary-gray hover:bg-secondary"
            }`}
          >
            {d}d
          </button>
        ))}
      </div>

      {/* Chart */}
      {chartData.length > 1 ? (
        <ResponsiveContainer width="100%" height={200}>
          <LineChart data={chartData}>
            <XAxis
              dataKey="date"
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
            />
            <YAxis
              tick={{ fontSize: 11 }}
              tickLine={false}
              axisLine={false}
              tickFormatter={(v: number) => `$${v.toFixed(0)}`}
              domain={["auto", "auto"]}
              width={40}
            />
            <Tooltip
              formatter={(value: any, name: any) => {
                const store = data.stores.find((s) => s.store_id === String(name));
                return [`$${Number(value).toFixed(2)}`, store?.store_name ?? String(name)];
              }}
              contentStyle={{
                fontSize: 12,
                borderRadius: 8,
                border: "1px solid #e5e7eb",
              }}
            />
            {data.stores
              .filter((s) => visibleStores.has(s.store_id))
              .map((store) => (
                <Line
                  key={store.store_id}
                  type="stepAfter"
                  dataKey={store.store_id}
                  stroke={getChainColor(store.chain)}
                  strokeWidth={2}
                  dot={false}
                  connectNulls
                  name={store.store_id}
                />
              ))}
          </LineChart>
        </ResponsiveContainer>
      ) : (
        <p className="text-sm text-secondary-gray">
          Only one data point recorded so far. The chart will appear after the next price change.
        </p>
      )}

      {/* Store toggles */}
      <div className="flex flex-wrap gap-2">
        {data.stores.map((store) => (
          <button
            key={store.store_id}
            onClick={() => toggleStore(store.store_id)}
            className={`flex items-center gap-1.5 text-xs px-2 py-1 rounded-full border transition-colors ${
              visibleStores.has(store.store_id)
                ? "border-transparent text-white"
                : "border-gray-200 text-secondary-gray bg-white"
            }`}
            style={
              visibleStores.has(store.store_id)
                ? { backgroundColor: getChainColor(store.chain) }
                : undefined
            }
          >
            {store.store_name}
          </button>
        ))}
      </div>
    </div>
  );
}
