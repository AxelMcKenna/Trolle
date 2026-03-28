import { useState, useEffect, lazy, Suspense } from "react";
import { useParams, Link, useNavigate } from "react-router-dom";
import {
  ArrowLeft,
  Store,
  MapPin,
  Clock,
  ShoppingCart,
  Check,
  ExternalLink,
  Bell,
  Award,
  Package,
} from "lucide-react";
import { toast } from "sonner";
import { ProductDetail as ProductDetailType, Product, Price } from "@/types";
import { useLocationContext } from "@/contexts/LocationContext";
import { useTrolleyContext } from "@/contexts/TrolleyContext";
import { useAuth } from "@/contexts/AuthContext";
import { useRecentlyViewed } from "@/hooks/useRecentlyViewed";
import { ChainLogo } from "@/components/stores/logos/ChainLogo";
import { LoyaltyBadge } from "@/components/products/LoyaltyBadge";
import { PriceAlertModal } from "@/components/products/PriceAlertModal";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { api } from "@/lib/api";
import {
  formatPromoEndDate,
  formatDistance,
  getDistanceColorClass,
  calculateSavingsPercent,
} from "@/lib/formatters";
import { getChainName } from "@/lib/chainConstants";

const PriceHistoryChart = lazy(() =>
  import("@/components/products/PriceHistoryChart").then((m) => ({
    default: m.PriceHistoryChart,
  }))
);

const ProductDetail = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const { location, radiusKm, isLocationSet } = useLocationContext();
  const { addItem, isInTrolley, getItemQuantity } = useTrolleyContext();
  const { isAuthenticated } = useAuth();
  const { addViewed } = useRecentlyViewed();

  const [product, setProduct] = useState<ProductDetailType | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [alertModalOpen, setAlertModalOpen] = useState(false);

  useEffect(() => {
    if (!id) return;

    const fetchProduct = async () => {
      setLoading(true);
      setError(null);
      try {
        const params: Record<string, string | number> = {};
        if (location && isLocationSet) {
          params.lat = location.lat;
          params.lon = location.lon;
          params.radius_km = radiusKm;
        }
        const { data } = await api.get<ProductDetailType>(
          `/products/${id}`,
          { params }
        );
        setProduct(data);

        // Track recently viewed
        if (data.prices.length > 0) {
          addViewed({
            id: data.id,
            name: data.name,
            image_url: data.image_url,
            chain: data.chain,
            price_nzd:
              data.prices[0].promo_price_nzd ?? data.prices[0].price_nzd,
            size: data.size,
          });
        }
      } catch {
        setError("Product not found");
      } finally {
        setLoading(false);
      }
    };

    fetchProduct();
  }, [id, location, radiusKm, isLocationSet]); // eslint-disable-line react-hooks/exhaustive-deps

  if (loading) {
    return (
      <div className="min-h-screen bg-secondary">
        <div className="bg-primary text-white px-4 py-3">
          <div className="max-w-4xl mx-auto flex items-center gap-3">
            <Skeleton className="h-8 w-8 rounded bg-white/20" />
            <Skeleton className="h-5 w-40 rounded bg-white/20" />
          </div>
        </div>
        <div className="max-w-4xl mx-auto px-4 py-6">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <Skeleton className="h-80 w-full rounded-xl" />
            <div className="space-y-3">
              <Skeleton className="h-8 w-3/4 rounded" />
              <Skeleton className="h-5 w-1/2 rounded" />
              <Skeleton className="h-12 w-1/3 rounded" />
              <Skeleton className="h-40 w-full rounded-xl" />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (error || !product) {
    return (
      <div className="min-h-screen bg-secondary">
        <div className="bg-primary text-white px-4 py-3">
          <div className="max-w-4xl mx-auto">
            <Link
              to="/explore"
              className="inline-flex items-center gap-2 text-sm text-white/80 hover:text-white"
            >
              <ArrowLeft className="h-4 w-4" />
              Back to Explore
            </Link>
          </div>
        </div>
        <div className="max-w-4xl mx-auto px-4 py-24 text-center">
          <Package className="h-16 w-16 text-muted-foreground/30 mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Product not found</h2>
          <p className="text-sm text-muted-foreground mb-6">
            This product may have been removed or the link is invalid.
          </p>
          <Button onClick={() => navigate("/explore")}>Browse Products</Button>
        </div>
      </div>
    );
  }

  const cheapestPrice = product.prices[0];
  const effectivePrice =
    cheapestPrice?.promo_price_nzd ?? cheapestPrice?.price_nzd;
  const hasPromo =
    cheapestPrice?.promo_price_nzd != null &&
    cheapestPrice.promo_price_nzd < cheapestPrice.price_nzd;
  const savingsPercent = calculateSavingsPercent(
    cheapestPrice?.price_nzd,
    cheapestPrice?.promo_price_nzd
  );
  const promoEndText = formatPromoEndDate(cheapestPrice?.promo_ends_at);
  const inTrolley = isInTrolley(product.id);

  // Build a Product-shaped object for the PriceAlertModal
  const productForAlert: Product = {
    ...product,
    price: cheapestPrice,
    last_updated: product.last_updated,
  };

  return (
    <div className="min-h-screen bg-secondary">
      {/* Header */}
      <div className="bg-primary text-white px-4 py-3">
        <div className="max-w-4xl mx-auto flex items-center gap-3">
          <button
            onClick={() => navigate(-1)}
            className="text-white/80 hover:text-white transition-colors"
            aria-label="Go back"
          >
            <ArrowLeft className="h-5 w-5" />
          </button>
          <Link to="/" className="text-lg font-semibold">
            TROLL-E
          </Link>
          <span className="text-white/40">/</span>
          <span className="text-sm text-white/70 truncate">{product.name}</span>
        </div>
      </div>

      <div className="max-w-4xl mx-auto px-4 py-6">
        {/* Product header: image + info */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-8">
          {/* Image */}
          <Card className="bg-white p-6 flex items-center justify-center relative overflow-hidden">
            {hasPromo && savingsPercent > 0 && (
              <Badge className="absolute top-3 left-3 bg-primary text-white text-xs z-10">
                {savingsPercent}% off
              </Badge>
            )}
            {product.image_url ? (
              <img
                src={product.image_url}
                alt={product.name}
                className="w-full max-h-80 object-contain"
              />
            ) : (
              <Package className="h-32 w-32 text-muted-foreground/20" />
            )}
          </Card>

          {/* Info */}
          <div className="flex flex-col">
            <h1 className="text-2xl font-bold text-foreground mb-1">
              {product.name}
            </h1>
            {product.brand && (
              <p className="text-muted-foreground mb-1">{product.brand}</p>
            )}
            {product.size && (
              <p className="text-sm text-muted-foreground mb-4">
                {product.size}
              </p>
            )}

            {/* Price */}
            {cheapestPrice && (
              <div className="mb-4">
                <div className="flex items-baseline gap-3">
                  <span className="text-4xl font-black text-primary">
                    ${effectivePrice?.toFixed(2)}
                  </span>
                  {hasPromo && (
                    <span className="text-lg line-through text-muted-foreground">
                      ${cheapestPrice.price_nzd.toFixed(2)}
                    </span>
                  )}
                </div>
                {cheapestPrice.unit_price && cheapestPrice.unit_measure && (
                  <p className="text-sm text-muted-foreground mt-1">
                    ${cheapestPrice.unit_price.toFixed(2)} /{" "}
                    {cheapestPrice.unit_measure}
                  </p>
                )}
                {hasPromo && (
                  <div className="flex flex-wrap gap-2 mt-2">
                    {cheapestPrice.is_member_only && (
                      <LoyaltyBadge chain={product.chain} />
                    )}
                    {promoEndText && (
                      <Badge
                        variant="outline"
                        className="gap-1 text-primary border-primary/30"
                      >
                        <Clock className="h-3 w-3" />
                        {promoEndText}
                      </Badge>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* Product details */}
            <dl className="grid grid-cols-2 gap-x-4 gap-y-1.5 text-sm mb-6">
              {product.department && (
                <>
                  <dt className="text-muted-foreground">Department</dt>
                  <dd className="font-medium">{product.department}</dd>
                </>
              )}
              {product.subcategory && (
                <>
                  <dt className="text-muted-foreground">Subcategory</dt>
                  <dd className="font-medium">{product.subcategory}</dd>
                </>
              )}
              {product.category && (
                <>
                  <dt className="text-muted-foreground">Category</dt>
                  <dd className="font-medium">{product.category}</dd>
                </>
              )}
            </dl>

            {/* Actions */}
            <div className="flex gap-2 mt-auto">
              <Button
                variant={inTrolley ? "secondary" : "default"}
                className="flex-1"
                onClick={() => {
                  if (!inTrolley && cheapestPrice) {
                    addItem(productForAlert);
                  }
                }}
                disabled={inTrolley}
              >
                {inTrolley ? (
                  <>
                    <Check className="h-4 w-4 mr-2" />
                    In Trolley
                  </>
                ) : (
                  <>
                    <ShoppingCart className="h-4 w-4 mr-2" />
                    Add to Trolley
                  </>
                )}
              </Button>
              {isAuthenticated && (
                <Button
                  variant="outline"
                  size="icon"
                  onClick={() => setAlertModalOpen(true)}
                  aria-label="Set price alert"
                >
                  <Bell className="h-4 w-4" />
                </Button>
              )}
              {product.product_url && (
                <Button variant="outline" size="icon" asChild>
                  <a
                    href={product.product_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    aria-label="View at store"
                  >
                    <ExternalLink className="h-4 w-4" />
                  </a>
                </Button>
              )}
            </div>
          </div>
        </div>

        {/* Store prices */}
        {product.prices.length > 0 && (
          <Card className="bg-white mb-8 overflow-hidden">
            <div className="p-4 border-b">
              <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">
                Available at {product.prices.length} store
                {product.prices.length !== 1 ? "s" : ""}
              </h2>
            </div>
            <div className="divide-y">
              {product.prices.map((price, idx) => {
                const storeEffective =
                  price.promo_price_nzd ?? price.price_nzd;
                const storeHasPromo =
                  price.promo_price_nzd != null &&
                  price.promo_price_nzd < price.price_nzd;
                const distText = formatDistance(price.distance_km);
                const distColor = getDistanceColorClass(price.distance_km);
                const isCheapest = idx === 0;

                return (
                  <div
                    key={price.store_id}
                    className="flex items-center gap-3 p-3 hover:bg-secondary/30 transition-colors"
                  >
                    <ChainLogo chain={price.chain} className="h-6 w-6 flex-shrink-0" />
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <p className="text-sm font-medium truncate">
                          {price.store_name}
                        </p>
                        {isCheapest && product.prices.length > 1 && (
                          <Badge className="bg-primary text-white text-[10px] px-1.5 py-0">
                            <Award className="h-3 w-3 mr-0.5" />
                            Cheapest
                          </Badge>
                        )}
                        {price.is_member_only && (
                          <LoyaltyBadge
                            chain={price.chain}
                            className="text-[10px]"
                          />
                        )}
                      </div>
                      <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
                        <span>{getChainName(price.chain)}</span>
                        {distText && (
                          <span
                            className={cn(
                              "flex items-center gap-1",
                              distColor
                            )}
                          >
                            <MapPin className="h-3 w-3" />
                            {distText}
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="text-right flex-shrink-0">
                      <p className="text-lg font-bold text-primary">
                        ${storeEffective.toFixed(2)}
                      </p>
                      {storeHasPromo && (
                        <p className="text-xs line-through text-muted-foreground">
                          ${price.price_nzd.toFixed(2)}
                        </p>
                      )}
                    </div>
                  </div>
                );
              })}
            </div>
          </Card>
        )}

        {/* Price history chart */}
        <Card className="bg-white p-6 mb-8">
          <h2 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-4">
            Price History
          </h2>
          <Suspense
            fallback={<Skeleton className="h-64 w-full rounded-lg" />}
          >
            <PriceHistoryChart productId={product.id} />
          </Suspense>
        </Card>
      </div>

      {/* Price alert modal */}
      {cheapestPrice && (
        <PriceAlertModal
          product={productForAlert}
          isOpen={alertModalOpen}
          onClose={() => setAlertModalOpen(false)}
        />
      )}
    </div>
  );
};

export default ProductDetail;
