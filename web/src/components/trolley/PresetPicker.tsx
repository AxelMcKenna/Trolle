import { useState } from "react";
import { Loader2, ShoppingCart, ChevronRight } from "lucide-react";
import { toast } from "sonner";
import { PRESET_TROLLEYS, PresetTrolley } from "@/lib/presetTrolleys";
import { useTrolleyContext } from "@/contexts/TrolleyContext";
import { useLocationContext } from "@/contexts/LocationContext";
import { Card } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { api } from "@/lib/api";

interface BatchResolveResult {
  query: string;
  product_id: string | null;
  name: string | null;
  brand: string | null;
  size: string | null;
  chain: string | null;
  image_url: string | null;
  department: string | null;
}

interface BatchResolveResponse {
  results: BatchResolveResult[];
  resolved: number;
  total: number;
}

export const PresetPicker = () => {
  const { addItems } = useTrolleyContext();
  const { location, radiusKm, isLocationSet } = useLocationContext();
  const [loadingId, setLoadingId] = useState<string | null>(null);

  const handleLoad = async (preset: PresetTrolley) => {
    if (!location || !isLocationSet) {
      toast.error("Set your location first to load a preset trolley");
      return;
    }

    setLoadingId(preset.id);

    try {
      const { data } = await api.post<BatchResolveResponse>("/products/batch-resolve", {
        queries: preset.items,
        lat: location.lat,
        lon: location.lon,
        radius_km: radiusKm,
      });

      const resolved = data.results.filter(
        (r): r is BatchResolveResult & { product_id: string; name: string; chain: string } =>
          r.product_id !== null && r.name !== null && r.chain !== null
      );

      if (resolved.length === 0) {
        toast.error("No products found nearby. Try a different location or radius.");
        return;
      }

      const added = addItems(
        resolved.map((r) => ({
          product_id: r.product_id,
          name: r.name,
          brand: r.brand,
          size: r.size,
          chain: r.chain,
          image_url: r.image_url,
          department: r.department,
        }))
      );

      if (added > 0) {
        const missed = preset.items.length - data.resolved;
        if (missed > 0) {
          toast.info(`${missed} item${missed > 1 ? "s" : ""} not found nearby`);
        }
      }
    } catch {
      toast.error("Failed to load preset trolley");
    } finally {
      setLoadingId(null);
    }
  };

  return (
    <div>
      <h3 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
        Quick Start — Preset Trolleys
      </h3>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
        {PRESET_TROLLEYS.map((preset) => (
          <Card
            key={preset.id}
            className="p-4 cursor-pointer hover:shadow-sm transition-all border bg-card group"
            onClick={() => !loadingId && handleLoad(preset)}
          >
            <div className="flex items-start gap-3">
              <span className="text-2xl flex-shrink-0 mt-0.5" role="img" aria-label={preset.name}>
                {preset.emoji}
              </span>
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2 mb-1">
                  <h4 className="text-sm font-semibold truncate">{preset.name}</h4>
                  <Badge variant="secondary" className="text-[10px] px-1.5 py-0 flex-shrink-0">
                    {preset.items.length} items
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground line-clamp-1">
                  {preset.description}
                </p>
              </div>
              <div className="flex-shrink-0 self-center">
                {loadingId === preset.id ? (
                  <Loader2 className="h-4 w-4 animate-spin text-muted-foreground" />
                ) : (
                  <ChevronRight className="h-4 w-4 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>
    </div>
  );
};
