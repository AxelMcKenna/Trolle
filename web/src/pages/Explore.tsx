import { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Header } from '@/components/layout/Header';
import { FilterBar } from '@/components/filters/FilterBar';
import { FilterSidebar } from '@/components/filters/FilterSidebar';
import { CategoryBar } from '@/components/filters/CategoryBar';
import { SortDropdown } from '@/components/filters/SortDropdown';
import { ProductGrid } from '@/components/products/ProductGrid';
import { usePaginatedProducts } from '@/hooks/usePaginatedProducts';
import { useFilters } from '@/hooks/useFilters';
import { useRecentlyViewed } from '@/hooks/useRecentlyViewed';
import { useLocationContext } from '@/contexts/LocationContext';
import { useSearchParams } from 'react-router-dom';
import { MapPin, X, Navigation, Sparkles } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SortOption, Product } from '@/types';
import { QuickView } from '@/components/products/QuickView';
import { api } from '@/lib/api';
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';

const LOCATION_PROMPT_DISMISSED_KEY = 'trolle.locationPromptDismissed';

export const Explore = () => {
  const FETCH_DEBOUNCE_MS = 220;
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(() => window.innerWidth >= 1024);
  const { location, radiusKm, isLocationSet, openLocationModal, requestAutoLocation, loading: locationLoading, error: locationError } = useLocationContext();
  const { filters, updateFilters } = useFilters();
  const { recentlyViewed } = useRecentlyViewed();
  const [luckyProduct, setLuckyProduct] = useState<Product | null>(null);
  const [luckyLoading, setLuckyLoading] = useState(false);
  const { products, total, loading, error, currentPage, totalPages, fetchProducts, goToPage, clearProducts } = usePaginatedProducts();
  const page = parseInt(searchParams.get('page') || '1', 10);
  const previousFetchInputsRef = useRef<{ page: number; nonPageKey: string } | null>(null);

  // Fix 1: Dismissable location prompt
  const [locationPromptDismissed, setLocationPromptDismissed] = useState(() => {
    return localStorage.getItem(LOCATION_PROMPT_DISMISSED_KEY) === 'true';
  });
  const dismissLocationPrompt = useCallback(() => {
    setLocationPromptDismissed(true);
    localStorage.setItem(LOCATION_PROMPT_DISMISSED_KEY, 'true');
  }, []);

  const handleRandomDeal = async () => {
    setLuckyLoading(true);
    try {
      const params: Record<string, number> = {};
      if (location && isLocationSet) {
        params.lat = location.lat;
        params.lon = location.lon;
        params.radius_km = radiusKm;
      }
      const { data } = await api.get('/products/random-deal', { params });
      setLuckyProduct(data);
    } catch {
      // no deals available
    } finally {
      setLuckyLoading(false);
    }
  };

  // Fix 9: Infinite scroll on mobile
  const [isMobile, setIsMobile] = useState(() => window.innerWidth < 768);
  const [mobileProducts, setMobileProducts] = useState<Product[]>([]);
  const [mobileLoadingMore, setMobileLoadingMore] = useState(false);
  const sentinelRef = useRef<HTMLDivElement>(null);
  const mobilePageRef = useRef(1);

  useEffect(() => {
    const mq = window.matchMedia('(max-width: 767px)');
    const handler = (e: MediaQueryListEvent) => setIsMobile(e.matches);
    mq.addEventListener('change', handler);
    return () => mq.removeEventListener('change', handler);
  }, []);

  // Reset mobile products when filters/location change (not page)
  useEffect(() => {
    if (isMobile) {
      setMobileProducts([]);
      mobilePageRef.current = 1;
    }
  }, [filters, location, radiusKm, isLocationSet, isMobile]);

  // Accumulate products for infinite scroll on mobile
  useEffect(() => {
    if (isMobile && products.length > 0) {
      if (currentPage === 1) {
        setMobileProducts(products);
      } else {
        setMobileProducts((prev) => {
          const existingIds = new Set(prev.map((p) => p.id));
          const newProducts = products.filter((p) => !existingIds.has(p.id));
          return [...prev, ...newProducts];
        });
      }
      setMobileLoadingMore(false);
      mobilePageRef.current = currentPage;
    }
  }, [products, currentPage, isMobile]);

  // Intersection observer for infinite scroll
  useEffect(() => {
    if (!isMobile || !sentinelRef.current) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const entry = entries[0];
        if (entry.isIntersecting && !loading && !mobileLoadingMore && currentPage < totalPages) {
          const nextPage = mobilePageRef.current + 1;
          setMobileLoadingMore(true);
          const newParams = new URLSearchParams(searchParams);
          newParams.set('page', nextPage.toString());
          setSearchParams(newParams, { replace: true });
        }
      },
      { rootMargin: '300px' }
    );

    observer.observe(sentinelRef.current);
    return () => observer.disconnect();
  }, [isMobile, loading, mobileLoadingMore, currentPage, totalPages, searchParams, setSearchParams]);

  useEffect(() => {
    setSearchQuery(filters.query || '');
  }, [filters.query]);

  useEffect(() => {
    const nonPageKey = JSON.stringify({
      filters,
      location,
      radiusKm,
      isLocationSet,
    });

    const previous = previousFetchInputsRef.current;
    const pageChangedOnly = Boolean(
      previous &&
      previous.page !== page &&
      previous.nonPageKey === nonPageKey
    );

    previousFetchInputsRef.current = { page, nonPageKey };

    const fetchFilters = {
      ...filters,
      ...(location && isLocationSet
        ? { lat: location.lat, lon: location.lon, radius_km: radiusKm }
        : {}),
    };

    if (pageChangedOnly) {
      fetchProducts(fetchFilters, page);
      return;
    }

    clearProducts();

    const timer = window.setTimeout(() => {
      fetchProducts(fetchFilters, page);
    }, FETCH_DEBOUNCE_MS);

    return () => window.clearTimeout(timer);
    // fetchProducts is stable (wrapped in useCallback with empty deps), so omitting from deps
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [filters, location, radiusKm, page, isLocationSet, clearProducts]);

  const handlePageChange = (newPage: number) => {
    const newParams = new URLSearchParams(searchParams);
    newParams.set('page', newPage.toString());
    setSearchParams(newParams);
    goToPage(newPage);
    window.scrollTo({ top: 0, behavior: 'smooth' });

  };

  const pageNumbers = useMemo(() => {
    const pages: (number | 'ellipsis')[] = [];
    const maxVisible = 7;

    if (totalPages <= maxVisible) {
      for (let i = 1; i <= totalPages; i++) {
        pages.push(i);
      }
    } else {
      pages.push(1);

      if (currentPage > 3) {
        pages.push('ellipsis');
      }

      const start = Math.max(2, currentPage - 1);
      const end = Math.min(totalPages - 1, currentPage + 1);

      for (let i = start; i <= end; i++) {
        pages.push(i);
      }

      if (currentPage < totalPages - 2) {
        pages.push('ellipsis');
      }

      pages.push(totalPages);
    }

    return pages;
  }, [currentPage, totalPages]);

  const handleSearch = () => {
    const trimmedQuery = searchQuery.trim();
    const nextParams = new URLSearchParams(searchParams);

    if (trimmedQuery) {
      nextParams.set('q', trimmedQuery);
    } else {
      nextParams.delete('q');
    }

    nextParams.delete('page');
    setSearchParams(nextParams);
  };

  return (
    <>
      <div className="min-h-screen bg-secondary">
        <div className="sticky top-0 z-50 bg-secondary">
          <Header
            query={searchQuery}
            setQuery={setSearchQuery}
            onSearch={handleSearch}
            variant="compact"
          />
        </div>

        <FilterBar onOpenFilters={() => setIsSidebarOpen(true)} />

        <div className="flex">
          <FilterSidebar
            isOpen={isSidebarOpen}
            onClose={() => setIsSidebarOpen(false)}
          />

          <main className="flex-1 overflow-y-auto min-h-screen overscroll-none">
            <CategoryBar />
            <div className="max-w-6xl mx-auto px-4 py-6 pb-32">
              {/* Fix 1: Dismissable location prompt — prominent on first visit */}
              {!isLocationSet && !locationPromptDismissed && (
                <div className="mb-6 p-4 bg-primary/5 border border-primary/15 rounded-xl relative">
                  <button
                    onClick={dismissLocationPrompt}
                    className="absolute top-3 right-3 text-muted-foreground hover:text-foreground p-0.5"
                    aria-label="Dismiss location prompt"
                  >
                    <X className="h-4 w-4" />
                  </button>
                  <div className="flex items-start gap-4">
                    <div className="flex-shrink-0 w-10 h-10 rounded-lg bg-primary/10 flex items-center justify-center">
                      <Navigation className="h-5 w-5 text-primary" />
                    </div>
                    <div className="flex-1 min-w-0 pr-4">
                      <p className="text-sm font-semibold">See prices at stores near you</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        Enable location to compare prices, sort by distance, and find the cheapest store for your trolley.
                      </p>
                      {locationError && (
                        <p className="text-xs text-destructive mt-1">{locationError}</p>
                      )}
                      <div className="flex items-center gap-2 mt-3">
                        <Button size="sm" onClick={requestAutoLocation} disabled={locationLoading}>
                          {locationLoading ? 'Locating...' : 'Use My Location'}
                        </Button>
                        <Button size="sm" variant="outline" onClick={openLocationModal}>
                          Set Manually
                        </Button>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {/* Recently viewed — show when no active search */}
              {!filters.query && recentlyViewed.length > 0 && (
                <div className="mb-6">
                  <h3 className="text-sm font-semibold text-muted-foreground mb-2 uppercase tracking-wide">
                    Recently Viewed
                  </h3>
                  <div className="flex gap-3 overflow-x-auto pb-2 -mx-1 px-1 scrollbar-thin">
                    {recentlyViewed.slice(0, 10).map((p) => (
                      <div
                        key={p.id}
                        className="flex-shrink-0 w-28 bg-white rounded-lg border p-2 hover:shadow-sm transition-shadow cursor-pointer"
                      >
                        {p.image_url ? (
                          <img
                            src={p.image_url}
                            alt={p.name}
                            className="w-full h-20 object-contain rounded mb-1.5"
                            loading="lazy"
                          />
                        ) : (
                          <div className="w-full h-20 bg-muted rounded flex items-center justify-center mb-1.5">
                            <span className="text-muted-foreground/30 text-xs">No image</span>
                          </div>
                        )}
                        <p className="text-[11px] font-medium line-clamp-2 leading-tight">{p.name}</p>
                        <p className="text-xs font-semibold text-primary mt-0.5">${p.price_nzd.toFixed(2)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Product content — always shown */}
              <>
                  {error && (
                    <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 mb-4">
                      <p className="text-sm text-destructive">{error}</p>
                    </div>
                  )}

                  {/* Results count + Sort */}
                  <div className="mb-4 flex items-center justify-between">
                    <span className="text-sm text-muted-foreground">
                      {loading
                        ? ''
                        : total === 0
                          ? 'No products found'
                          : `${(currentPage - 1) * 24 + 1}\u2013${Math.min(currentPage * 24, total)} of ${total.toLocaleString()}`}
                    </span>
                    <div className="flex items-center gap-2">
                      <Button
                        onClick={handleRandomDeal}
                        variant="outline"
                        size="sm"
                        disabled={luckyLoading}
                        className="hidden sm:flex"
                      >
                        <Sparkles className="h-3.5 w-3.5 mr-1" />
                        {luckyLoading ? '...' : 'Lucky'}
                      </Button>
                      <span className="text-xs text-muted-foreground hidden sm:inline">Sort by</span>
                      <SortDropdown
                        value={filters.sort || SortOption.CHEAPEST}
                        onChange={(sort) => updateFilters({ sort })}
                      />
                    </div>
                  </div>

                  {/* Fix 9: On mobile use infinite scroll, on desktop use pagination */}
                  {isMobile ? (
                    <>
                      <ProductGrid
                        products={mobileProducts.length > 0 ? mobileProducts : products}
                        loading={loading && mobileProducts.length === 0}
                      />
                      {mobileLoadingMore && (
                        <div className="flex justify-center py-6">
                          <div className="w-6 h-6 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                        </div>
                      )}
                      {/* Sentinel for intersection observer */}
                      {!loading && currentPage < totalPages && (
                        <div ref={sentinelRef} className="h-1" />
                      )}
                    </>
                  ) : (
                    <>
                      <ProductGrid
                        products={products}
                        loading={loading}
                      />

                      {/* Desktop pagination */}
                      {!loading && products.length > 0 && totalPages > 1 && (
                        <div className="mt-6">
                          <Pagination>
                            <PaginationContent>
                              <PaginationItem>
                                <PaginationPrevious
                                  onClick={() => currentPage > 1 && handlePageChange(currentPage - 1)}
                                  className={currentPage === 1 ? 'pointer-events-none opacity-50' : ''}
                                />
                              </PaginationItem>

                              {pageNumbers.map((pageNum, idx) =>
                                pageNum === 'ellipsis' ? (
                                  <PaginationItem key={`ellipsis-${idx}`}>
                                    <PaginationEllipsis />
                                  </PaginationItem>
                                ) : (
                                  <PaginationItem key={pageNum}>
                                    <PaginationLink
                                      onClick={() => handlePageChange(pageNum)}
                                      isActive={currentPage === pageNum}
                                    >
                                      {pageNum}
                                    </PaginationLink>
                                  </PaginationItem>
                                )
                              )}

                              <PaginationItem>
                                <PaginationNext
                                  onClick={() => currentPage < totalPages && handlePageChange(currentPage + 1)}
                                  className={currentPage === totalPages ? 'pointer-events-none opacity-50' : ''}
                                />
                              </PaginationItem>
                            </PaginationContent>
                          </Pagination>
                        </div>
                      )}
                    </>
                  )}

                  {!loading && (isMobile ? mobileProducts : products).length === 0 && (
                    <div className="text-center py-12">
                      <p className="text-muted-foreground">
                        No products found. Try adjusting your filters.
                      </p>
                    </div>
                  )}
                </>
            </div>
          </main>
        </div>

      </div>

      <QuickView
        product={luckyProduct}
        isOpen={!!luckyProduct}
        onClose={() => setLuckyProduct(null)}
      />
    </>
  );
};

export default Explore;
