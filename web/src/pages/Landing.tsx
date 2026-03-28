import { useState, useEffect, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { motion, useInView } from 'framer-motion';
import { ProductGrid } from '@/components/products/ProductGrid';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Slider } from '@/components/ui/slider';
import { LazyStoreMap } from '@/components/stores/LazyStoreMap';
import { StoreMapSkeleton } from '@/components/stores/StoreMapSkeleton';
import { useProducts } from '@/hooks/useProducts';
import { useLocationContext } from '@/contexts/LocationContext';
import { useStores } from '@/hooks/useStores';
import { useAuth } from '@/contexts/AuthContext';
import { Search, ArrowRight, MapPin, ShoppingCart, UtensilsCrossed, User, LogOut, Navigation } from 'lucide-react';
import { useTrolleyContext } from '@/contexts/TrolleyContext';
import { SortOption } from '@/types';
import { api } from '@/lib/api';
import { useIntersectionObserver } from '@/hooks/useIntersectionObserver';

/* ------------------------------------------------------------------ */
/*  Reveal — scroll-triggered entrance                                */
/* ------------------------------------------------------------------ */
const Reveal = ({
  children,
  className = '',
  delay = 0,
  direction = 'up',
}: {
  children: React.ReactNode;
  className?: string;
  delay?: number;
  direction?: 'up' | 'left' | 'right';
}) => {
  const ref = useRef<HTMLDivElement>(null);
  const isInView = useInView(ref, { once: true, margin: '-40px' });
  const originMap = {
    up: { y: 28, x: 0 },
    left: { x: -36, y: 0 },
    right: { x: 36, y: 0 },
  };
  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, ...originMap[direction] }}
      animate={isInView ? { opacity: 1, x: 0, y: 0 } : {}}
      transition={{ duration: 0.65, delay, ease: [0.22, 1, 0.36, 1] }}
      className={className}
    >
      {children}
    </motion.div>
  );
};

/* ------------------------------------------------------------------ */
/*  Landing Page                                                       */
/* ------------------------------------------------------------------ */
export const Landing = () => {
  const [query, setQuery] = useState('');
  const navigate = useNavigate();
  const { products, loading, fetchProducts } = useProducts();
  const {
    location,
    radiusKm,
    setRadiusKm,
    requestAutoLocation: requestLocation,
    loading: locationLoading,
    error: locationError,
  } = useLocationContext();
  const { stores, loading: storesLoading, fetchNearbyStores } = useStores();
  const { isAuthenticated, user, displayName, signOut } = useAuth();
  const { itemCount } = useTrolleyContext();
  const [userMenuOpen, setUserMenuOpen] = useState(false);
  const [tempRadius, setTempRadius] = useState(radiusKm);
  const [shouldLoadMap, setShouldLoadMap] = useState(false);
  const [globalStats, setGlobalStats] = useState<{ total_comparisons: number; total_savings: number } | null>(null);
  const mapRef = useIntersectionObserver({
    enabled: Boolean(location),
    onIntersect: () => setShouldLoadMap(true),
  });

  const promoFetchLimit = 10;

  useEffect(() => {
    if (location && !storesLoading) {
      fetchNearbyStores(location, radiusKm);
    }
  }, [location, radiusKm, fetchNearbyStores]);

  useEffect(() => {
    if (location) {
      fetchProducts({
        promo_only: true,
        limit: promoFetchLimit,
        sort: SortOption.DISCOUNT,
        unique_products: true,
        lat: location.lat,
        lon: location.lon,
        radius_km: radiusKm,
      });
    } else {
      fetchProducts({
        promo_only: true,
        limit: promoFetchLimit,
        sort: SortOption.DISCOUNT,
        unique_products: true,
      });
    }
  }, [location, radiusKm, fetchProducts]);

  useEffect(() => {
    setTempRadius(radiusKm);
  }, [radiusKm]);

  useEffect(() => {
    api.get<{ total_comparisons: number; total_savings: number; average_savings: number }>('/trolley/stats/global')
      .then(({ data }) => setGlobalStats(data))
      .catch(() => {});
  }, []);

  useEffect(() => {
    const debounceId = window.setTimeout(() => {
      if (tempRadius !== radiusKm) {
        setRadiusKm(tempRadius);
      }
    }, 500);
    return () => window.clearTimeout(debounceId);
  }, [tempRadius, radiusKm, setRadiusKm]);

  const getTopDiscountedProducts = () => {
    if (!products?.items) return [];
    return products.items
      .filter((item) => {
        const promoPrice = item.price.promo_price_nzd;
        return promoPrice !== null && promoPrice !== undefined && promoPrice < item.price.price_nzd;
      })
      .map((item) => ({
        ...item,
        discountPercent:
          ((item.price.price_nzd - (item.price.promo_price_nzd || 0)) / item.price.price_nzd) * 100,
      }))
      .sort((a, b) => b.discountPercent - a.discountPercent)
      .slice(0, 10);
  };

  const topDiscountedProducts = getTopDiscountedProducts();

  const handleSearch = () => {
    const trimmedQuery = query.trim();
    navigate(trimmedQuery ? `/explore?q=${encodeURIComponent(trimmedQuery)}` : '/explore');
  };

  const handleViewAllDeals = () => {
    navigate('/explore?promo_only=true');
  };

  return (
    <div className="min-h-screen bg-background overflow-x-hidden">

      {/* ============================================================ */}
      {/*  HERO — Split tension with grain texture & layered gradients */}
      {/* ============================================================ */}
      <section className="bg-primary hero-clip hero-grain relative">
        {/* Layered gradients for depth — top-left warm glow + bottom-right cool fade */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_15%_25%,rgba(255,255,255,0.08),transparent_50%)]" />
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_85%_75%,rgba(0,0,0,0.15),transparent_50%)]" />

        <div className="relative z-10 max-w-7xl mx-auto px-4 pt-6 pb-40 md:pb-44">
          {/* Nav — logo left, account right */}
          <div className="flex items-center justify-between mb-14 md:mb-20 animate-fade-up">
            <Link to="/" className="text-xl font-bold text-white font-sans tracking-[0.15em]">
              TROLL-E
            </Link>
            <div className="flex items-center gap-1">
              <Link to="/trolley">
                <Button variant="ghost" size="sm" className="text-white hover:bg-white/10 relative border-0">
                  <ShoppingCart className="h-4 w-4" />
                  {itemCount > 0 && (
                    <span className="absolute -top-1 -right-1 bg-white text-primary text-[10px] font-bold rounded-full h-4 min-w-[16px] flex items-center justify-center px-0.5">
                      {itemCount}
                    </span>
                  )}
                </Button>
              </Link>
            {isAuthenticated ? (
              <div className="relative">
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-white hover:bg-white/10 gap-2 border-0"
                  onClick={() => setUserMenuOpen(!userMenuOpen)}
                >
                  <div className="w-6 h-6 bg-white/20 rounded-full flex items-center justify-center text-xs font-bold font-sans">
                    {(displayName?.[0] ?? user?.email?.[0] ?? 'U').toUpperCase()}
                  </div>
                  <span className="font-sans text-sm">{displayName || 'Account'}</span>
                </Button>
                {userMenuOpen && (
                  <>
                    <div className="fixed inset-0 z-40" onClick={() => setUserMenuOpen(false)} />
                    <div className="absolute right-0 top-full mt-1 w-48 bg-white rounded-lg shadow-lg border z-50 py-1">
                      <div className="px-3 py-2 border-b">
                        {displayName && <p className="text-sm font-medium text-gray-900 truncate">{displayName}</p>}
                        <p className="text-xs text-gray-500 truncate">{user?.email}</p>
                      </div>
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-gray-50 flex items-center gap-2"
                        onClick={() => { setUserMenuOpen(false); navigate('/account'); }}
                      >
                        <User className="h-3.5 w-3.5" /> Account
                      </button>
                      <button
                        className="w-full px-3 py-2 text-sm text-left hover:bg-gray-50 flex items-center gap-2 text-red-600"
                        onClick={() => { setUserMenuOpen(false); signOut(); }}
                      >
                        <LogOut className="h-3.5 w-3.5" /> Sign Out
                      </button>
                    </div>
                  </>
                )}
              </div>
            ) : (
              <Link to="/login">
                <Button variant="ghost" size="sm" className="text-white hover:bg-white/10 font-sans text-sm gap-2 border-0">
                  <User className="h-4 w-4" />
                  Account
                </Button>
              </Link>
            )}
            </div>
          </div>

          {/* Hero content — 7/5 asymmetric split */}
          <div className="grid grid-cols-1 md:grid-cols-12 gap-8 md:gap-10 items-end">
            {/* Left: headline + search */}
            <div className="md:col-span-6 animate-slide-left">
              <p className="text-[11px] text-white/50 font-sans font-medium uppercase tracking-[0.2em] mb-4">
                NZ Grocery Price Comparison
              </p>
              <h1 className="text-[clamp(2.25rem,5vw,3.75rem)] text-white tracking-tight leading-[1.08] mb-0">
                Find the best
                <br />
                deals <em className="font-serif italic font-normal text-white/80">near you</em>
              </h1>
              <hr className="accent-rule mt-6" />
              <p className="text-[15px] md:text-base text-white/55 font-sans max-w-md mt-5 leading-relaxed">
                Compare prices across Countdown, New World, and PAK'nSAVE — updated daily.
              </p>

              {/* Search — anchored under headline for stronger left weight */}
              <div className="relative search-glow rounded-lg mt-8 max-w-lg">
                <Search className="absolute left-4 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground z-10" />
                <Input
                  placeholder="Search for milk, bread, chicken..."
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                  className="pl-12 pr-24 h-14 text-base rounded-lg border-0 bg-white text-foreground shadow-xl font-sans"
                />
                <Button
                  onClick={handleSearch}
                  size="sm"
                  className="absolute right-1.5 top-1/2 -translate-y-1/2 h-11 z-10 font-sans"
                >
                  Search
                </Button>
              </div>

              {/* Location prompt — early, visible, non-blocking */}
              {!location && (
                <button
                  onClick={requestLocation}
                  disabled={locationLoading}
                  className="flex items-center gap-2 mt-5 text-[13px] font-sans text-white/60 hover:text-white/90 transition-colors group"
                >
                  <Navigation className="h-3.5 w-3.5 group-hover:text-[hsl(var(--gold))] transition-colors" />
                  {locationLoading ? 'Getting location...' : 'Enable location for nearby prices'}
                </button>
              )}

              {/* Stat pills — below search */}
              <div className="flex items-center gap-5 text-[11px] font-sans text-white/40 tracking-wide mt-5">
                {globalStats && globalStats.total_comparisons > 0 ? (
                  <>
                    <span className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[hsl(var(--gold))]" />
                      {globalStats.total_comparisons.toLocaleString()} comparisons
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[hsl(var(--gold))]" />
                      ${globalStats.total_savings.toLocaleString()} saved
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[hsl(var(--gold))]" />
                      3 supermarkets
                    </span>
                  </>
                ) : (
                  <>
                    <span className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[hsl(var(--gold))]" />
                      3 supermarkets
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[hsl(var(--gold))]" />
                      Daily updates
                    </span>
                    <span className="flex items-center gap-1.5">
                      <span className="w-1 h-1 rounded-full bg-[hsl(var(--gold))]" />
                      Free
                    </span>
                  </>
                )}
              </div>
            </div>

            {/* Right: glass panel with subtle tilt */}
            <div className="hidden md:block md:col-span-6 animate-slide-right" style={{ animationDelay: '200ms' }}>
              <div className="relative max-w-sm ml-auto">
                {/* Back panel — creates stacked-pages depth */}
                <div className="absolute inset-0 bg-white/[0.04] border border-white/[0.06] rounded-xl rotate-[-2deg] translate-y-1" />

                {/* Main panel */}
                <div className="relative bg-white/[0.07] backdrop-blur-md border border-white/[0.1] rounded-xl p-5 font-sans">
                  <p className="text-[10px] text-white/35 uppercase tracking-[0.15em] mb-4">Example trolley</p>

                  <div className="space-y-2.5 text-[13px]">
                    {[
                      { name: 'Anchor Blue Milk 2L', price: '3.49' },
                      { name: 'Vogel\'s Toast Bread', price: '3.99' },
                      { name: 'Free Range Eggs 12pk', price: '7.99' },
                    ].map((item) => (
                      <div key={item.name} className="flex items-center justify-between">
                        <span className="text-white/60">{item.name}</span>
                        <span className="text-white/80 tabular-nums">${item.price}</span>
                      </div>
                    ))}
                  </div>

                  <div className="mt-4 pt-3 border-t border-white/[0.08] flex items-center justify-between">
                    <span className="text-white/90 text-sm font-medium">PAK'nSAVE cheapest</span>
                    <span className="text-[hsl(var(--gold))] font-semibold text-sm tabular-nums">-$2.91</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  DEALS                                                        */}
      {/* ============================================================ */}
      <section className="pt-16 pb-14 md:pt-24 md:pb-20">
        <div className="max-w-7xl mx-auto px-4">
          <div className="grid grid-cols-1 md:grid-cols-12 gap-4 mb-10">
            <Reveal className="md:col-span-8">
              <hr className="accent-rule mb-4" />
              <h2 className="text-2xl md:text-3xl text-foreground tracking-tight">
                {location ? 'Deals Near You' : 'Top Deals'}
              </h2>
              {!location && (
                <p className="text-sm text-muted-foreground mt-2 font-sans">
                  Enable location for personalized results
                </p>
              )}
            </Reveal>
            <Reveal className="md:col-span-4 flex md:justify-end items-end" delay={0.08}>
              <Button
                onClick={handleViewAllDeals}
                variant="ghost"
                size="sm"
                className="text-primary -ml-3 md:ml-0 font-sans"
              >
                View all deals
                <ArrowRight className="ml-1 h-4 w-4" />
              </Button>
            </Reveal>
          </div>

          <ProductGrid products={topDiscountedProducts} loading={loading} />

          {!loading && topDiscountedProducts.length === 0 && (
            <div className="text-center py-20">
              <Search className="h-10 w-10 text-muted-foreground/20 mx-auto mb-4" />
              <p className="text-muted-foreground font-serif text-lg">No deals available right now</p>
              <p className="text-sm text-muted-foreground/60 mt-1 font-sans">Check back soon for new promotions</p>
            </div>
          )}
        </div>
      </section>

      {/* ============================================================ */}
      {/*  CTAs — Split Tension (7/5)                                   */}
      {/* ============================================================ */}
      <section className="px-4 py-12 md:py-16">
        <div className="max-w-7xl mx-auto grid grid-cols-12 gap-4 md:gap-6">
          {/* Trolley — 7 cols, primary bg */}
          <Reveal className="col-span-12 md:col-span-7" direction="left">
            <div
              className="relative bg-primary rounded-2xl p-8 md:p-10 flex flex-col justify-between min-h-[260px] overflow-hidden cursor-pointer group card-lift"
              onClick={() => navigate('/trolley')}
            >
              {/* Grain on card too */}
              <div className="absolute inset-0 hero-grain rounded-2xl" />
              <div className="absolute -bottom-16 -right-16 w-56 h-56 rounded-full bg-white/[0.04]" />
              <div className="absolute top-8 right-8 w-24 h-24 rounded-full border border-white/[0.06]" />

              <div className="relative z-10">
                <div className="w-11 h-11 rounded-lg bg-white/15 flex items-center justify-center mb-5">
                  <ShoppingCart className="h-5 w-5 text-white" />
                </div>
                <h3 className="text-2xl md:text-3xl text-white mb-2 leading-tight">
                  Build your trolley
                </h3>
                <p className="text-white/55 text-sm md:text-[15px] max-w-sm leading-relaxed font-sans">
                  Add your weekly shop and instantly see which nearby store is cheapest for your entire list.
                </p>
              </div>

              <div className="relative z-10 mt-6">
                <span className="inline-flex items-center text-white/70 text-sm font-sans font-medium group-hover:text-white transition-colors">
                  Start shopping
                  <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </span>
              </div>
            </div>
          </Reveal>

          {/* Recipes — 5 cols, light card */}
          <Reveal className="col-span-12 md:col-span-5" direction="right" delay={0.1}>
            <div
              className="relative bg-card border rounded-2xl p-8 md:p-10 flex flex-col justify-between min-h-[260px] overflow-hidden cursor-pointer group card-lift"
              onClick={() => navigate('/recipes')}
            >
              <div className="absolute -bottom-10 -left-10 w-36 h-36 rounded-full bg-primary/[0.04]" />
              <div className="absolute bottom-6 right-6 w-16 h-16 rounded-full border border-primary/[0.06]" />

              <div className="relative z-10">
                <div className="w-11 h-11 rounded-lg bg-primary/10 flex items-center justify-center mb-5">
                  <UtensilsCrossed className="h-5 w-5 text-primary" />
                </div>
                <h3 className="text-2xl md:text-3xl text-foreground mb-2 leading-tight">
                  Cheapest recipes
                </h3>
                <p className="text-muted-foreground text-sm md:text-[15px] max-w-xs leading-relaxed font-sans">
                  Find which store has the cheapest ingredients for your whole meal.
                </p>
              </div>

              <div className="relative z-10 mt-6">
                <span className="inline-flex items-center text-primary text-sm font-sans font-medium group-hover:text-primary/70 transition-colors">
                  Browse recipes
                  <ArrowRight className="ml-2 h-4 w-4 group-hover:translate-x-1 transition-transform" />
                </span>
              </div>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ============================================================ */}
      {/*  MAP                                                          */}
      {/* ============================================================ */}
      <section className="py-14 md:py-20 border-t">
        <div className="max-w-7xl mx-auto px-4">
          {!location && (
            <div className="max-w-md mx-auto text-center py-8">
              <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-secondary mb-4">
                <MapPin className="h-6 w-6 text-primary" />
              </div>
              <h3 className="text-lg font-medium mb-2">Enable Location</h3>
              <p className="text-sm text-muted-foreground mb-6">
                See deals from stores in your area
              </p>
              <Button
                onClick={requestLocation}
                disabled={locationLoading}
              >
                {locationLoading ? 'Getting location...' : 'Enable Location'}
              </Button>
              {locationError && (
                <p className="text-destructive text-sm mt-4">{locationError}</p>
              )}
            </div>
          )}

          {location && (
            <div className="space-y-4">
              <div className="bg-secondary rounded-lg p-4">
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm font-medium">Search radius</span>
                  <span className="text-sm font-semibold text-primary">
                    {tempRadius} km
                  </span>
                </div>
                <Slider
                  value={[tempRadius]}
                  onValueChange={(value) => setTempRadius(value[0])}
                  min={1}
                  max={10}
                  step={1}
                  className="w-full"
                />
                <div className="flex justify-between text-xs text-muted-foreground mt-2">
                  <span>1 km</span>
                  <span>{stores.length} stores</span>
                  <span>10 km</span>
                </div>
              </div>

              <div ref={mapRef} className="rounded-lg overflow-hidden border">
                {shouldLoadMap ? (
                  <LazyStoreMap
                    userLocation={location}
                    stores={stores}
                    selectedStore={null}
                    onStoreClick={() => {}}
                    radiusKm={radiusKm}
                  />
                ) : (
                  <StoreMapSkeleton className="h-[400px] border-none" />
                )}
              </div>
            </div>
          )}
        </div>
      </section>

      {/* Divider */}
      <div className="max-w-7xl mx-auto px-4">
        <hr className="border-border" />
      </div>

      {/* ============================================================ */}
      {/*  BOTTOM CTA — left-heavy with diagonal accent                 */}
      {/* ============================================================ */}
      <section className="pt-16 pb-16 md:pt-24 md:pb-24">
        <div className="max-w-7xl mx-auto px-4">
          <Reveal>
            <div className="bg-primary rounded-2xl overflow-hidden relative hero-grain">
              {/* Layered gradients */}
              <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_20%_50%,rgba(255,255,255,0.06),transparent_50%)]" />
              {/* Diagonal accent slab */}
              <div className="absolute top-0 right-0 w-1/3 h-full bg-white/[0.03] skew-x-[-12deg] translate-x-16" />

              <div className="relative z-10 px-8 py-10 md:px-12 md:py-14 grid grid-cols-1 md:grid-cols-12 gap-6 items-center">
                <div className="md:col-span-8">
                  <hr className="accent-rule mb-5" />
                  <h2 className="text-2xl md:text-3xl text-white tracking-tight mb-3">
                    Ready to compare?
                  </h2>
                  <p className="text-white/55 font-sans max-w-lg text-[15px] leading-relaxed">
                    Browse thousands of products from every major NZ supermarket. Find the lowest price near you.
                  </p>
                </div>
                <div className="md:col-span-4 md:text-right">
                  <Button
                    onClick={() => navigate('/explore')}
                    size="lg"
                    className="bg-white text-primary hover:bg-white/90 font-sans font-semibold shadow-lg"
                  >
                    <Search className="h-5 w-5 mr-2" />
                    Explore All Products
                  </Button>
                </div>
              </div>
            </div>
          </Reveal>
        </div>
      </section>
    </div>
  );
};

export default Landing;
