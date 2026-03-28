import { useState, useEffect, useRef, useMemo } from 'react';
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
import { MapPin } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { SortOption } from '@/types';
import {
  Pagination,
  PaginationContent,
  PaginationEllipsis,
  PaginationItem,
  PaginationLink,
  PaginationNext,
  PaginationPrevious,
} from '@/components/ui/pagination';

export const Explore = () => {
  const FETCH_DEBOUNCE_MS = 220;
  const [searchParams, setSearchParams] = useSearchParams();
  const [searchQuery, setSearchQuery] = useState('');
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const { location, radiusKm, isLocationSet, openLocationModal, requestAutoLocation, loading: locationLoading, error: locationError } = useLocationContext();
  const { filters, updateFilters } = useFilters();
  const { recentlyViewed } = useRecentlyViewed();
  const { products, total, loading, error, currentPage, totalPages, fetchProducts, goToPage, clearProducts } = usePaginatedProducts();
  const page = parseInt(searchParams.get('page') || '1', 10);
  const previousFetchInputsRef = useRef<{ page: number; nonPageKey: string } | null>(null);

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
      <div className="min-h-screen bg-secondary">
        <div className="sticky top-0 z-50 bg-secondary">
          <Header
            query={searchQuery}
            setQuery={setSearchQuery}
            onSearch={handleSearch}
            variant="compact"
          />
          <FilterBar onOpenFilters={() => setIsSidebarOpen(true)} />
        </div>

        <div className="flex">
          <FilterSidebar
            isOpen={isSidebarOpen}
            onClose={() => setIsSidebarOpen(false)}
          />

          <main className="flex-1 overflow-y-auto min-h-screen overscroll-none">
            <CategoryBar />
            <div className="max-w-6xl mx-auto px-4 py-6 pb-32">
              {/* Location banner — soft prompt instead of gate */}
              {!isLocationSet && (
                <div className="mb-4 flex items-center gap-3 p-3 bg-primary/5 border border-primary/15 rounded-lg">
                  <MapPin className="h-4 w-4 text-primary flex-shrink-0" />
                  <p className="text-sm text-muted-foreground flex-1">
                    Set your location to see store distances and nearby prices.
                  </p>
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={requestAutoLocation}
                    disabled={locationLoading}
                    className="flex-shrink-0"
                  >
                    {locationLoading ? 'Locating...' : 'Enable'}
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={openLocationModal}
                    className="flex-shrink-0"
                  >
                    Set manually
                  </Button>
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
                      <span className="text-xs text-muted-foreground hidden sm:inline">Sort by</span>
                      <SortDropdown
                        value={filters.sort || SortOption.CHEAPEST}
                        onChange={(sort) => updateFilters({ sort })}
                      />
                    </div>
                  </div>

                  <ProductGrid
                    products={products}
                    loading={loading}
                  />

                  {/* Pagination */}
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

                  {!loading && products.length === 0 && (
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
  );
};

export default Explore;
