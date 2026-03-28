import { memo, useState } from "react";
import { Store, Clock, ShoppingCart, MapPin, Eye, Check, Plus, Minus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Product } from "@/types";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { useTrolleyContext } from "@/contexts/TrolleyContext";
import { QuickView } from "./QuickView";
import { LoyaltyBadge } from "./LoyaltyBadge";
import {
  formatPromoEndDate,
  formatDistance,
  getDistanceColorClass,
  calculateSavingsPercent,
} from "@/lib/formatters";

interface ProductCardProps {
  product: Product;
  index: number;
}

const ProductCardComponent = ({
  product,
  index,
}: ProductCardProps) => {
  const [imageError, setImageError] = useState(false);
  const [showQuickView, setShowQuickView] = useState(false);
  const { addItem, removeItem, updateQuantity, isInTrolley, getItemQuantity } = useTrolleyContext();
  const inTrolley = isInTrolley(product.id);
  const trolleyQty = getItemQuantity(product.id);
  const hasPromo = product.price.promo_price_nzd &&
    product.price.promo_price_nzd < product.price.price_nzd;

  const promoEndText = formatPromoEndDate(product.price.promo_ends_at);
  const savingsPercent = calculateSavingsPercent(product.price.price_nzd, product.price.promo_price_nzd);
  const distanceText = formatDistance(product.price.distance_km);
  const distanceColorClass = getDistanceColorClass(product.price.distance_km);

  const handleCardClick = () => {
    setShowQuickView(true);
  };

  return (
    <div className="h-full">
      <Card
        className="h-full flex flex-col overflow-hidden border bg-white hover:shadow-sm transition-shadow cursor-pointer group"
        onClick={handleCardClick}
      >
        {/* Product Image */}
        <div className="w-full aspect-square relative overflow-hidden border-b">
          {product.image_url && !imageError ? (
            <img
              src={product.image_url}
              alt={product.name}
              className="w-full h-full object-contain p-4"
              loading="lazy"
              decoding="async"
              onError={() => setImageError(true)}
            />
          ) : (
            <div className="w-full h-full flex items-center justify-center">
              <ShoppingCart className="h-12 w-12 text-muted-foreground/20" />
            </div>
          )}

          {/* Sale badge */}
          {hasPromo && savingsPercent > 0 && (
            <Badge className="absolute top-2 left-2 bg-primary text-white text-xs">
              {savingsPercent}% off
            </Badge>
          )}

          {/* Quick View button */}
          <div className="absolute inset-0 hidden items-center justify-center bg-black/40 opacity-0 transition-opacity group-hover:opacity-100 sm:flex">
            <Button
              size="sm"
              variant="secondary"
              onClick={(e) => {
                e.stopPropagation();
                setShowQuickView(true);
              }}
            >
              <Eye className="mr-1.5 h-4 w-4" />
              Quick View
            </Button>
          </div>
          <Button
            size="sm"
            variant="secondary"
            className="absolute bottom-2 right-2 sm:hidden"
            onClick={(e) => {
              e.stopPropagation();
              setShowQuickView(true);
            }}
          >
            <Eye className="mr-1.5 h-4 w-4" />
            Quick View
          </Button>
        </div>

        <CardContent className="p-3 flex-1 flex flex-col">
          {/* Product info */}
          <div className="mb-2">
            <h3 className="text-sm font-medium line-clamp-2 group-hover:text-primary transition-colors">
              {product.name}
            </h3>
            {product.size && (
              <p className="text-xs text-muted-foreground mt-0.5">
                {product.size}
              </p>
            )}
          </div>

          {/* Store info */}
          <div className="flex items-center gap-3 text-xs text-muted-foreground mb-2">
            <span className="flex items-center gap-1">
              <Store className="h-3 w-3" />
              {product.price.store_name}
            </span>
            {distanceText && (
              <span className={cn("flex items-center gap-1", distanceColorClass)}>
                <MapPin className="h-3 w-3" />
                {distanceText}
              </span>
            )}
          </div>

          {/* Price */}
          <div className="flex items-baseline gap-2">
            <span className="text-xl font-semibold text-primary">
              ${(product.price.promo_price_nzd ?? product.price.price_nzd).toFixed(2)}
            </span>
            {hasPromo && (
              <span className="text-xs line-through text-muted-foreground">
                ${product.price.price_nzd.toFixed(2)}
              </span>
            )}
          </div>

          {/* Badges */}
          {hasPromo && (
            <div className="flex flex-wrap gap-1 mt-2">
              {product.price.is_member_only && (
                <LoyaltyBadge chain={product.chain} className="text-xs" />
              )}
              {promoEndText && (
                <Badge variant="outline" className="text-xs gap-1">
                  <Clock className="h-3 w-3" />
                  {promoEndText}
                </Badge>
              )}
            </div>
          )}

          {/* Unit price */}
          {product.price.unit_price && product.price.unit_measure && (
            <p className="text-xs text-muted-foreground mt-2">
              ${product.price.unit_price.toFixed(2)} / {product.price.unit_measure}
            </p>
          )}

          {/* Spacer pushes button to bottom */}
          <div className="flex-1" />

          {/* Add to Trolley / Quantity controls */}
          {inTrolley ? (
            <div className="flex items-center justify-between mt-3 gap-2">
              <div className="flex items-center gap-0.5">
                <button
                  className="h-7 w-7 rounded-md flex items-center justify-center hover:bg-muted text-muted-foreground transition-colors touch-manipulation"
                  onClick={(e) => {
                    e.stopPropagation();
                    if (trolleyQty <= 1) {
                      removeItem(product.id);
                      toast('Removed from trolley', { duration: 2000 });
                    } else {
                      updateQuantity(product.id, trolleyQty - 1);
                    }
                  }}
                  aria-label={trolleyQty <= 1 ? "Remove from trolley" : "Decrease quantity"}
                >
                  {trolleyQty <= 1 ? <Trash2 className="h-3 w-3" /> : <Minus className="h-3 w-3" />}
                </button>
                <span className="text-xs font-medium w-6 text-center">{trolleyQty}</span>
                <button
                  className="h-7 w-7 rounded-md flex items-center justify-center hover:bg-muted text-muted-foreground transition-colors touch-manipulation"
                  onClick={(e) => {
                    e.stopPropagation();
                    updateQuantity(product.id, trolleyQty + 1);
                  }}
                  disabled={trolleyQty >= 99}
                  aria-label="Increase quantity"
                >
                  <Plus className="h-3 w-3" />
                </button>
              </div>
              <span className="flex items-center gap-1 text-xs text-primary font-medium">
                <Check className="h-3 w-3" />
                In Trolley
              </span>
            </div>
          ) : (
            <Button
              variant="outline"
              size="sm"
              className="w-full mt-3 text-xs"
              onClick={(e) => {
                e.stopPropagation();
                addItem(product);
                toast.success(`Added to trolley`, { duration: 2000 });
              }}
            >
              <ShoppingCart className="h-3 w-3 mr-1" />
              Add to Trolley
            </Button>
          )}
        </CardContent>
      </Card>

      <QuickView
        product={product}
        isOpen={showQuickView}
        onClose={() => setShowQuickView(false)}
      />
    </div>
  );
};

export const ProductCard = memo(ProductCardComponent);
