import { useState, useEffect, useRef, Fragment } from 'react';
import { Link } from 'react-router-dom';
import {
  ShoppingCart,
  Trash2,
  Plus,
  Minus,
  Navigation,
  MapPin,
  Award,
  AlertCircle,
  ChevronRight,
  Search,
  X,
  Check,
  Loader2,
  ArrowRightLeft,
} from 'lucide-react';
import { useTrolleyContext } from '@/contexts/TrolleyContext';
import { useLocationContext } from '@/contexts/LocationContext';
import { useTrolleyCompare } from '@/hooks/useTrolleyCompare';
import { useTrolleySuggestions } from '@/hooks/useTrolleySuggestions';
import { useProducts } from '@/hooks/useProducts';
import { Product, TrolleyStoreBreakdown, SuggestionProduct } from '@/types';
import { ChainLogo } from '@/components/stores/logos/ChainLogo';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { Input } from '@/components/ui/input';
import { getChainName } from '@/lib/chainConstants';

export const Trolley = () => {
  const { items, itemCount, addItem, removeItem, updateQuantity, clearTrolley, isInTrolley } = useTrolleyContext();
  const { location, radiusKm, isLocationSet, openLocationModal, requestAutoLocation, loading: locationLoading, error: locationError } = useLocationContext();
  const { comparison, loading, error, compare } = useTrolleyCompare();
  const { suggestions, loading: suggestionsLoading, fetchSuggestions } = useTrolleySuggestions();
  const { products: searchResults, loading: searchLoading, fetchProducts } = useProducts();
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [isSearchOpen, setIsSearchOpen] = useState(false);
  const searchRef = useRef<HTMLDivElement>(null);
  const searchTimerRef = useRef<number>();

  // Debounced search
  useEffect(() => {
    if (!searchQuery.trim() || !location) {
      return;
    }
    clearTimeout(searchTimerRef.current);
    searchTimerRef.current = window.setTimeout(() => {
      fetchProducts({
        query: searchQuery.trim(),
        lat: location.lat,
        lon: location.lon,
        radius_km: radiusKm,
        unique_products: true,
        limit: 8,
      });
    }, 300);
    return () => clearTimeout(searchTimerRef.current);
  }, [searchQuery, location, radiusKm, fetchProducts]);

  // Close search dropdown on outside click
  useEffect(() => {
    const handleClickOutside = (e: MouseEvent) => {
      if (searchRef.current && !searchRef.current.contains(e.target as Node)) {
        setIsSearchOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  // Trigger comparison when items or location change
  useEffect(() => {
    if (items.length > 0 && location && isLocationSet) {
      compare(items, location.lat, location.lon, radiusKm);
    }
  }, [items, location, radiusKm, isLocationSet, compare]);

  // Auto-select cheapest complete store
  useEffect(() => {
    if (comparison?.stores.length && !selectedStoreId) {
      setSelectedStoreId(comparison.stores[0].store_id);
    }
  }, [comparison, selectedStoreId]);

  const selectedStore = comparison?.stores.find((s) => s.store_id === selectedStoreId) ?? null;

  // Fetch suggestions for unavailable items when store changes
  useEffect(() => {
    if (!selectedStore || selectedStore.is_complete) return;
    const unavailableIds = selectedStore.items
      .filter((i) => !i.available)
      .map((i) => i.source_product_id);
    if (unavailableIds.length > 0) {
      fetchSuggestions({ store_id: selectedStore.store_id, product_ids: unavailableIds });
    }
  }, [selectedStoreId, selectedStore?.is_complete, fetchSuggestions]);

  return (
    <div className="min-h-screen bg-secondary">
      {/* Header bar */}
      <div className="bg-primary text-white px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="text-lg font-semibold">GROCIFY</Link>
            <span className="text-white/60">/</span>
            <h1 className="text-sm font-medium">Your Trolley</h1>
          </div>
          {itemCount > 0 && (
            <Button
              variant="ghost"
              size="sm"
              className="text-white/70 hover:bg-white/10 hover:text-white"
              onClick={clearTrolley}
            >
              Clear All
            </Button>
          )}
        </div>
      </div>

      {/* Search bar */}
      <div className="bg-white border-b">
        <div className="max-w-6xl mx-auto px-4 py-3">
          <div ref={searchRef} className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Search products to add..."
              value={searchQuery}
              onChange={(e) => {
                setSearchQuery(e.target.value);
                setIsSearchOpen(true);
              }}
              onFocus={() => searchQuery.trim() && setIsSearchOpen(true)}
              className="pl-10 pr-8 h-9 text-sm"
            />
            {searchQuery && (
              <button
                className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
                onClick={() => {
                  setSearchQuery('');
                  setIsSearchOpen(false);
                }}
              >
                <X className="h-4 w-4" />
              </button>
            )}

            {/* Search results dropdown */}
            {isSearchOpen && searchQuery.trim() && (
              <div className="absolute z-50 top-full left-0 right-0 mt-1 bg-white border rounded-lg shadow-lg max-h-80 overflow-y-auto">
                {searchLoading ? (
                  <div className="p-4 flex items-center justify-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    Searching...
                  </div>
                ) : searchResults?.items.length ? (
                  searchResults.items.map((product) => (
                    <SearchResultRow
                      key={product.id}
                      product={product}
                      inTrolley={isInTrolley(product.id)}
                      onAdd={() => {
                        addItem(product);
                        setSearchQuery('');
                        setIsSearchOpen(false);
                      }}
                    />
                  ))
                ) : (
                  <div className="p-4 text-sm text-muted-foreground text-center">
                    No products found
                  </div>
                )}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Empty state */}
        {itemCount === 0 && (
          <div className="flex items-center justify-center py-24">
            <Card className="p-8 text-center max-w-md border bg-card">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-secondary mb-4">
                <ShoppingCart className="h-8 w-8 text-muted-foreground" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Your trolley is empty</h2>
              <p className="text-sm text-muted-foreground mb-2">
                Search for products above or browse the Explore page to add items.
              </p>
            </Card>
          </div>
        )}

        {/* Location gate */}
        {itemCount > 0 && !isLocationSet && (
          <div className="flex items-center justify-center py-24">
            <Card className="p-8 text-center max-w-md border bg-card">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-secondary mb-4">
                <Navigation className="h-6 w-6 text-primary" />
              </div>
              <h2 className="text-xl font-semibold mb-2">Location Required</h2>
              <p className="text-sm text-muted-foreground mb-6">
                Enable location to compare trolley prices at stores near you.
              </p>
              {locationError && (
                <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                  <p className="text-sm text-destructive">{locationError}</p>
                </div>
              )}
              <div className="space-y-2">
                <Button onClick={requestAutoLocation} disabled={locationLoading} className="w-full">
                  {locationLoading ? 'Getting location...' : (
                    <><Navigation className="h-4 w-4 mr-2" />Use My Location</>
                  )}
                </Button>
                <Button onClick={openLocationModal} variant="outline" className="w-full">
                  <MapPin className="h-4 w-4 mr-2" />Set Manually
                </Button>
              </div>
            </Card>
          </div>
        )}

        {/* Comparison results */}
        {itemCount > 0 && isLocationSet && loading && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div className="space-y-3">
              {[1, 2, 3].map((i) => (
                <Skeleton key={i} className="h-24 w-full rounded-lg" />
              ))}
            </div>
            <Skeleton className="h-80 w-full rounded-lg" />
          </div>
        )}

        {itemCount > 0 && isLocationSet && error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 mb-4">
            <p className="text-sm text-destructive flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {error}
            </p>
          </div>
        )}

        {itemCount > 0 && isLocationSet && !loading && comparison && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left — Store rankings */}
            <div>
              <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
                Store Rankings
              </h2>
              {comparison.stores.length === 0 ? (
                <Card className="p-6 text-center bg-card">
                  <p className="text-sm text-muted-foreground">No nearby stores found</p>
                </Card>
              ) : (
                <div className="space-y-2">
                  {comparison.stores.map((store, idx) => (
                    <StoreRankCard
                      key={store.store_id}
                      store={store}
                      rank={idx + 1}
                      isSelected={store.store_id === selectedStoreId}
                      isBestPrice={idx === 0 && store.is_complete}
                      onClick={() => setSelectedStoreId(store.store_id)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Right — Item breakdown */}
            <div>
              <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
                Item Breakdown
              </h2>
              {selectedStore ? (
                <Card className="bg-card overflow-hidden">
                  <div className="p-4 border-b bg-secondary/50">
                    <div className="flex items-center gap-2">
                      <ChainLogo chain={selectedStore.chain} className="h-5 w-5" />
                      <span className="font-medium text-sm">{selectedStore.store_name}</span>
                    </div>
                  </div>
                  <div>
                    {(() => {
                      // Group items by department
                      const grouped: Record<string, typeof selectedStore.items> = {};
                      selectedStore.items.forEach((storeItem) => {
                        const sourceItem = comparison.items.find(
                          (i) => i.product_id === storeItem.source_product_id
                        );
                        const dept = sourceItem?.department || 'Other';
                        if (!grouped[dept]) grouped[dept] = [];
                        grouped[dept].push(storeItem);
                      });

                      return Object.entries(grouped).map(([dept, groupItems]) => (
                        <div key={dept}>
                          <div className="px-3 py-1.5 bg-secondary/70 border-y">
                            <span className="text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                              {dept}
                            </span>
                          </div>
                          <div className="divide-y">
                            {groupItems.map((storeItem, idx) => {
                              const sourceItem = comparison.items.find(
                                (i) => i.product_id === storeItem.source_product_id
                              );
                              const itemSuggestions = !storeItem.available
                                ? suggestions?.items.find(
                                    (s) => s.source_product_id === storeItem.source_product_id
                                  )?.suggestions
                                : undefined;

                              return (
                                <Fragment key={idx}>
                                  <div
                                    className={`p-3 flex items-center gap-3 ${!storeItem.available ? 'opacity-50' : ''}`}
                                  >
                                    {sourceItem?.image_url ? (
                                      <img
                                        src={sourceItem.image_url}
                                        alt={storeItem.source_product_name}
                                        className="w-10 h-10 object-contain rounded flex-shrink-0"
                                      />
                                    ) : (
                                      <div className="w-10 h-10 bg-muted rounded flex items-center justify-center flex-shrink-0">
                                        <ShoppingCart className="h-4 w-4 text-muted-foreground/30" />
                                      </div>
                                    )}
                                    <div className="flex-1 min-w-0">
                                      <p className="text-sm font-medium truncate">
                                        {storeItem.matched_product_name ?? storeItem.source_product_name}
                                      </p>
                                      <div className="flex items-center gap-2 mt-0.5">
                                        <div className="flex items-center gap-1">
                                          <button
                                            className="h-5 w-5 rounded flex items-center justify-center hover:bg-muted text-muted-foreground"
                                            onClick={() => updateQuantity(storeItem.source_product_id, storeItem.quantity - 1)}
                                            disabled={storeItem.quantity <= 1}
                                          >
                                            <Minus className="h-3 w-3" />
                                          </button>
                                          <span className="text-xs font-medium w-4 text-center">{storeItem.quantity}</span>
                                          <button
                                            className="h-5 w-5 rounded flex items-center justify-center hover:bg-muted text-muted-foreground"
                                            onClick={() => updateQuantity(storeItem.source_product_id, storeItem.quantity + 1)}
                                            disabled={storeItem.quantity >= 99}
                                          >
                                            <Plus className="h-3 w-3" />
                                          </button>
                                        </div>
                                        {!storeItem.available && (
                                          <span className="text-xs text-muted-foreground">— Unavailable</span>
                                        )}
                                        <button
                                          className="h-5 w-5 rounded flex items-center justify-center hover:bg-destructive/10 text-muted-foreground hover:text-destructive ml-1"
                                          onClick={() => removeItem(storeItem.source_product_id)}
                                        >
                                          <Trash2 className="h-3 w-3" />
                                        </button>
                                      </div>
                                    </div>
                                    <div className="text-right flex-shrink-0">
                                      {storeItem.available && storeItem.price != null ? (
                                        <>
                                          <p className="text-sm font-semibold">
                                            ${storeItem.line_total?.toFixed(2)}
                                          </p>
                                          {storeItem.quantity > 1 && (
                                            <p className="text-[10px] text-muted-foreground">
                                              ${storeItem.price.toFixed(2)} ea
                                            </p>
                                          )}
                                        </>
                                      ) : (
                                        <p className="text-xs text-muted-foreground">—</p>
                                      )}
                                    </div>
                                  </div>
                                  {/* Suggestions for unavailable items */}
                                  {!storeItem.available && (suggestionsLoading || (itemSuggestions && itemSuggestions.length > 0)) && (
                                    <div className="bg-amber-50/50 border-l-2 border-amber-300">
                                      {suggestionsLoading ? (
                                        <div className="px-4 py-2 flex items-center gap-2 text-xs text-muted-foreground">
                                          <Loader2 className="h-3 w-3 animate-spin" />
                                          Finding alternatives...
                                        </div>
                                      ) : (
                                        <>
                                          <div className="px-4 py-1.5 text-[10px] font-semibold text-amber-700 uppercase tracking-wide">
                                            Suggestions
                                          </div>
                                          {itemSuggestions!.map((sug) => {
                                            const sugPrice = sug.promo_price_nzd ?? sug.price_nzd;
                                            return (
                                              <div
                                                key={sug.product_id}
                                                className="px-4 py-2 flex items-center gap-3 hover:bg-amber-50/80 transition-colors"
                                              >
                                                {sug.image_url ? (
                                                  <img src={sug.image_url} alt={sug.name} className="w-8 h-8 object-contain rounded flex-shrink-0" />
                                                ) : (
                                                  <div className="w-8 h-8 bg-muted rounded flex items-center justify-center flex-shrink-0">
                                                    <ShoppingCart className="h-3 w-3 text-muted-foreground/30" />
                                                  </div>
                                                )}
                                                <div className="flex-1 min-w-0">
                                                  <p className="text-xs font-medium truncate">{sug.name}</p>
                                                  {sug.size && (
                                                    <p className="text-[10px] text-muted-foreground">{sug.size}</p>
                                                  )}
                                                </div>
                                                <span className="text-xs font-semibold text-primary flex-shrink-0">
                                                  ${sugPrice.toFixed(2)}
                                                </span>
                                                <Button
                                                  variant="outline"
                                                  size="sm"
                                                  className="h-6 text-[10px] px-2 flex-shrink-0"
                                                  onClick={() => {
                                                    removeItem(storeItem.source_product_id);
                                                    addItem({
                                                      id: sug.product_id,
                                                      name: sug.name,
                                                      brand: sug.brand,
                                                      size: sug.size,
                                                      chain: selectedStore!.chain,
                                                      image_url: sug.image_url,
                                                      department: sourceItem?.department,
                                                      price: {
                                                        store_id: selectedStore!.store_id,
                                                        store_name: selectedStore!.store_name,
                                                        chain: selectedStore!.chain,
                                                        price_nzd: sug.price_nzd,
                                                        promo_price_nzd: sug.promo_price_nzd,
                                                      },
                                                      last_updated: new Date().toISOString(),
                                                    } as Product);
                                                  }}
                                                >
                                                  <ArrowRightLeft className="h-3 w-3 mr-1" />
                                                  Swap
                                                </Button>
                                              </div>
                                            );
                                          })}
                                        </>
                                      )}
                                    </div>
                                  )}
                                </Fragment>
                              );
                            })}
                          </div>
                        </div>
                      ));
                    })()}
                  </div>
                  <div className="p-4 border-t bg-secondary/50 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      {selectedStore.items_available}/{selectedStore.items_total} items available
                    </span>
                    <span className="text-lg font-bold text-primary">
                      ${selectedStore.estimated_total.toFixed(2)}
                    </span>
                  </div>
                </Card>
              ) : (
                <Card className="p-6 text-center bg-card">
                  <p className="text-sm text-muted-foreground">Select a store to see the breakdown</p>
                </Card>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

interface StoreRankCardProps {
  store: TrolleyStoreBreakdown;
  rank: number;
  isSelected: boolean;
  isBestPrice: boolean;
  onClick: () => void;
}

const StoreRankCard = ({ store, rank, isSelected, isBestPrice, onClick }: StoreRankCardProps) => {
  return (
    <Card
      className={`p-3 cursor-pointer transition-all hover:shadow-sm ${
        isSelected ? 'ring-2 ring-primary bg-primary/5' : 'bg-card'
      }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-3">
        <div className="flex-shrink-0 w-6 text-center">
          <span className="text-xs font-bold text-muted-foreground">#{rank}</span>
        </div>
        <ChainLogo chain={store.chain} className="h-6 w-6 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium truncate">{store.store_name}</p>
            {isBestPrice && (
              <Badge className="bg-primary text-white text-[10px] px-1.5 py-0">
                <Award className="h-3 w-3 mr-0.5" />
                Best Price
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
            <span>{getChainName(store.chain)}</span>
            <span>{store.distance_km} km</span>
            <Badge
              variant={store.is_complete ? 'default' : 'secondary'}
              className="text-[10px] px-1.5 py-0"
            >
              {store.items_available}/{store.items_total} items
            </Badge>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-lg font-bold text-primary">${store.estimated_total.toFixed(2)}</p>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
      </div>
    </Card>
  );
};

interface SearchResultRowProps {
  product: Product;
  inTrolley: boolean;
  onAdd: () => void;
}

const SearchResultRow = ({ product, inTrolley, onAdd }: SearchResultRowProps) => {
  const effectivePrice = product.price.promo_price_nzd ?? product.price.price_nzd;
  return (
    <div className="flex items-center gap-3 px-3 py-2 hover:bg-secondary/50 cursor-pointer transition-colors">
      {product.image_url ? (
        <img
          src={product.image_url}
          alt={product.name}
          className="w-9 h-9 object-contain rounded flex-shrink-0"
        />
      ) : (
        <div className="w-9 h-9 bg-muted rounded flex items-center justify-center flex-shrink-0">
          <ShoppingCart className="h-4 w-4 text-muted-foreground/30" />
        </div>
      )}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium truncate">{product.name}</p>
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          {product.size && <span>{product.size}</span>}
          <span>{product.price.store_name}</span>
        </div>
      </div>
      <span className="text-sm font-semibold text-primary flex-shrink-0">
        ${effectivePrice.toFixed(2)}
      </span>
      <Button
        variant={inTrolley ? 'secondary' : 'default'}
        size="sm"
        className="flex-shrink-0 h-7 text-xs px-2"
        onClick={(e) => {
          e.stopPropagation();
          if (!inTrolley) onAdd();
        }}
        disabled={inTrolley}
      >
        {inTrolley ? (
          <><Check className="h-3 w-3 mr-1" />Added</>
        ) : (
          <><Plus className="h-3 w-3 mr-1" />Add</>
        )}
      </Button>
    </div>
  );
};

export default Trolley;
