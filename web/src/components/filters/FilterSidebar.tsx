import { useFilters } from '@/hooks/useFilters';
import { ChainFilter } from './ChainFilter';
import { PromoToggle } from './PromoToggle';
import { MemberPriceToggle } from './MemberPriceToggle';
import { PriceRangeFilter } from './PriceRangeFilter';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { X, Sparkles, DollarSign, Store as StoreIcon } from 'lucide-react';

interface FilterSidebarProps {
  isOpen: boolean;
  onClose: () => void;
}

export const FilterSidebar = ({ isOpen, onClose }: FilterSidebarProps) => {
  const { filters, updateFilters, clearFilters, activeFilterCount } = useFilters();

  const handleFilterChange = (updates: Parameters<typeof updateFilters>[0]) => {
    updateFilters(updates);
  };

  return (
    <>
      {/* Mobile overlay */}
      {isOpen && (
        <div
          className="fixed inset-0 bg-black/20 backdrop-blur-sm z-30 lg:hidden"
          onClick={onClose}
        />
      )}

      {/* Sidebar */}
      <aside
        className={`
          fixed lg:sticky top-0 lg:top-0 left-0 h-[100dvh] lg:max-h-screen w-72 bg-white
          transform transition-all duration-300 ease-out z-40
          ${isOpen ? 'translate-x-0 shadow-xl lg:shadow-none' : '-translate-x-full'}
          border-r border-border/40 lg:self-start
        `}
      >
        <div className="h-full flex flex-col">
          {/* Header */}
          <div className="px-6 py-5 border-b border-border/40">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <h2 className="text-lg font-semibold text-primary-gray tracking-tight">Filters</h2>
                {activeFilterCount > 0 && (
                  <Badge className="bg-primary/10 text-primary border-primary/20 text-xs px-2">
                    {activeFilterCount}
                  </Badge>
                )}
              </div>
              <Button
                variant="ghost"
                size="icon"
                onClick={onClose}
                className="lg:hidden -mr-2 hover:bg-gray-100 rounded-lg"
              >
                <X className="h-4 w-4" />
              </Button>
            </div>
            {activeFilterCount > 0 && (
              <Button
                variant="ghost"
                size="sm"
                onClick={clearFilters}
                className="w-full justify-start text-secondary-gray hover:text-primary-gray hover:bg-gray-50 rounded-lg -ml-2"
              >
                <X className="h-4 w-4 mr-2" />
                Clear all filters
              </Button>
            )}
          </div>

          {/* Scrollable filters */}
          <div className="flex-1 overflow-y-auto px-6 py-4 space-y-8 pb-20 lg:pb-4">
            {/* Deals & Promos */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <Sparkles className="h-4 w-4 text-primary" />
                <label className="text-sm font-semibold text-primary-gray">
                  Deals & Promos
                </label>
              </div>
              <div className="space-y-3">
                <PromoToggle
                  checked={filters.promo_only || false}
                  onChange={(promo_only) => handleFilterChange({ promo_only })}
                />
                <MemberPriceToggle
                  checked={filters.member_prices !== false}
                  onChange={(checked) => handleFilterChange({ member_prices: checked ? undefined : false })}
                />
              </div>
            </div>

            {/* Price Range */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <DollarSign className="h-4 w-4 text-primary" />
                <label className="text-sm font-semibold text-primary-gray">
                  Price Range
                </label>
              </div>
              <PriceRangeFilter
                min={filters.price_min}
                max={filters.price_max}
                onChange={(price_min, price_max) => handleFilterChange({ price_min, price_max })}
              />
            </div>

            {/* Chain Filter */}
            <div>
              <div className="flex items-center gap-2 mb-4">
                <StoreIcon className="h-4 w-4 text-primary" />
                <label className="text-sm font-semibold text-primary-gray">
                  Stores
                </label>
              </div>
              <ChainFilter
                selected={filters.chains || []}
                onChange={(chains) => handleFilterChange({ chains })}
              />
            </div>
          </div>

          {/* Mobile done button */}
          <div className="lg:hidden border-t border-border/40 p-4 bg-white">
            <Button onClick={onClose} className="w-full">
              Show Results
            </Button>
          </div>
        </div>
      </aside>
    </>
  );
};
