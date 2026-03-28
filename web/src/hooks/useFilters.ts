import { useSearchParams } from 'react-router-dom';
import { useMemo, useCallback, useEffect, useRef } from 'react';
import { ProductFilters, SortOption, ChainType } from '@/types';

const FILTER_STORAGE_KEY = 'trolle.lastFilters';

export const useFilters = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const latestSearchParamsRef = useRef(new URLSearchParams(searchParams));
  const hydratedRef = useRef(false);

  useEffect(() => {
    latestSearchParamsRef.current = new URLSearchParams(searchParams);
  }, [searchParams]);

  // Hydrate from localStorage on first mount when URL has no filter params
  useEffect(() => {
    if (hydratedRef.current) return;
    hydratedRef.current = true;

    const hasUrlFilters = searchParams.toString().length > 0;
    if (hasUrlFilters) return;

    try {
      const stored = localStorage.getItem(FILTER_STORAGE_KEY);
      if (stored) {
        const savedParams = new URLSearchParams(stored);
        // Only restore non-page filter params
        savedParams.delete('page');
        if (savedParams.toString()) {
          setSearchParams(savedParams);
        }
      }
    } catch { /* ignore */ }
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Persist filter params to localStorage on change (excluding page)
  useEffect(() => {
    const toSave = new URLSearchParams(searchParams);
    toSave.delete('page');
    if (toSave.toString()) {
      localStorage.setItem(FILTER_STORAGE_KEY, toSave.toString());
    }
  }, [searchParams]);

  const filters: ProductFilters = useMemo(() => {
    const query = searchParams.get('q') || undefined;
    const category = searchParams.get('category') || undefined;
    const chainParam = searchParams.get('chain');
    const chains = chainParam ? (chainParam.split(',') as ChainType[]) : undefined;
    const promo_only = searchParams.get('promo_only') === 'true' ? true : undefined;
    const member_prices = searchParams.get('member_prices') === 'false' ? false : undefined;
    const price_min = searchParams.get('price_min') ? parseFloat(searchParams.get('price_min')!) : undefined;
    const price_max = searchParams.get('price_max') ? parseFloat(searchParams.get('price_max')!) : undefined;
    const sortParam = searchParams.get('sort') as SortOption | null;
    const sort = sortParam || (promo_only ? SortOption.DISCOUNT : SortOption.CHEAPEST);
    const storeIdsParam = searchParams.get('store_ids');
    const store_ids = storeIdsParam ? storeIdsParam.split(',') : undefined;

    return {
      query,
      category,
      chains,
      promo_only,
      member_prices,
      price_min,
      price_max,
      sort,
      store_ids,
    };
  }, [searchParams]);

  const updateFilters = useCallback((updates: Partial<ProductFilters>) => {
    const newParams = new URLSearchParams(latestSearchParamsRef.current);
    if (Object.keys(updates).length > 0) {
      newParams.delete('page');
    }

    Object.entries(updates).forEach(([key, value]) => {
      if (value === undefined || value === null || value === '') {
        newParams.delete(key);
      } else if (key === 'chains' && Array.isArray(value)) {
        if (value.length === 0) {
          newParams.delete('chain');
        } else {
          newParams.set('chain', value.join(','));
        }
      } else if (key === 'store_ids' && Array.isArray(value)) {
        if (value.length === 0) {
          newParams.delete('store_ids');
        } else {
          newParams.set('store_ids', value.join(','));
        }
      } else if (key === 'promo_only') {
        if (value) {
          newParams.set('promo_only', 'true');
        } else {
          newParams.delete('promo_only');
        }
      } else if (key === 'member_prices') {
        if (value === false) {
          newParams.set('member_prices', 'false');
        } else {
          newParams.delete('member_prices');
        }
      } else {
        newParams.set(key, String(value));
      }
    });

    latestSearchParamsRef.current = new URLSearchParams(newParams);
    setSearchParams(newParams);
  }, [setSearchParams]);

  const clearFilters = useCallback(() => {
    latestSearchParamsRef.current = new URLSearchParams();
    setSearchParams({});
  }, [setSearchParams]);

  const hasActiveFilters = useMemo(() => {
    return !!(
      filters.query ||
      filters.category ||
      filters.chains?.length ||
      filters.promo_only ||
      filters.price_min ||
      filters.price_max ||
      (filters.sort && filters.sort !== SortOption.CHEAPEST)
    );
  }, [filters]);

  const activeFilterCount = useMemo(() => {
    let count = 0;
    if (filters.category) count++;
    if (filters.chains?.length) count += filters.chains.length;
    if (filters.promo_only) count++;
    if (filters.member_prices === false) count++;
    if (filters.price_min || filters.price_max) count++;
    if (filters.sort && filters.sort !== SortOption.CHEAPEST) count++;
    return count;
  }, [filters]);

  return {
    filters,
    updateFilters,
    clearFilters,
    hasActiveFilters,
    activeFilterCount,
  };
};
