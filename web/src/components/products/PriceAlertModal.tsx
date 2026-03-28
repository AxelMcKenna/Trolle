import { useState } from "react";
import { Bell } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { usePriceAlerts } from "@/hooks/usePriceAlerts";
import type { Product } from "@/types";

interface PriceAlertModalProps {
  product: Product;
  isOpen: boolean;
  onClose: () => void;
}

export function PriceAlertModal({ product, isOpen, onClose }: PriceAlertModalProps) {
  const currentPrice = product.price.promo_price_nzd ?? product.price.price_nzd;
  const [targetPrice, setTargetPrice] = useState(
    Math.floor(currentPrice * 0.9 * 100) / 100,
  );
  const [submitting, setSubmitting] = useState(false);
  const { createAlert } = usePriceAlerts();

  const handleSubmit = async () => {
    if (targetPrice <= 0) {
      toast.error("Target price must be greater than 0");
      return;
    }
    setSubmitting(true);
    try {
      await createAlert(product.id, targetPrice);
      toast.success(`Alert set for ${product.name} at $${targetPrice.toFixed(2)}`);
      onClose();
    } catch (err: any) {
      const detail = err?.response?.data?.detail;
      toast.error(detail ?? "Failed to create alert");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={isOpen} onOpenChange={(open) => !open && onClose()}>
      <DialogContent className="sm:max-w-[400px]">
        <div className="space-y-4">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 bg-primary/10 rounded-full flex items-center justify-center">
              <Bell className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h3 className="font-semibold text-primary-gray">Set Price Alert</h3>
              <p className="text-sm text-secondary-gray">Get notified when the price drops</p>
            </div>
          </div>

          <div className="bg-gray-50 rounded-lg p-3">
            <p className="text-sm font-medium text-primary-gray line-clamp-2">{product.name}</p>
            {product.brand && (
              <p className="text-xs text-secondary-gray">{product.brand}</p>
            )}
            <p className="text-lg font-bold text-primary mt-1">
              ${currentPrice.toFixed(2)}
              <span className="text-xs text-secondary-gray font-normal ml-1">current price</span>
            </p>
          </div>

          <div>
            <label className="text-sm font-medium text-primary-gray" htmlFor="target-price">
              Notify me when price drops to:
            </label>
            <div className="relative mt-1">
              <span className="absolute left-3 top-1/2 -translate-y-1/2 text-secondary-gray">$</span>
              <Input
                id="target-price"
                type="number"
                step="0.01"
                min="0.01"
                value={targetPrice}
                onChange={(e) => setTargetPrice(parseFloat(e.target.value) || 0)}
                className="pl-7"
              />
            </div>
            {targetPrice >= currentPrice && (
              <p className="text-xs text-amber-600 mt-1">
                Target is at or above the current price — the alert may trigger immediately.
              </p>
            )}
          </div>

          <div className="flex gap-2">
            <Button variant="outline" className="flex-1" onClick={onClose}>
              Cancel
            </Button>
            <Button
              className="flex-1 bg-primary hover:bg-accent"
              onClick={handleSubmit}
              disabled={submitting}
            >
              {submitting ? "Setting..." : "Set Alert"}
            </Button>
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
}
