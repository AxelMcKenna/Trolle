import { useFilters } from '@/hooks/useFilters';
import { SlidersHorizontal } from 'lucide-react';

interface FilterBarProps {
  onOpenFilters: () => void;
}

export const FilterBar = ({ onOpenFilters }: FilterBarProps) => {
  const { activeFilterCount } = useFilters();

  return (
    <button
      onClick={onOpenFilters}
      className="fixed bottom-6 right-4 z-50 lg:hidden flex items-center gap-2 bg-primary text-white pl-4 pr-4 py-3 rounded-full shadow-lg active:scale-95 transition-transform"
    >
      <SlidersHorizontal className="h-4 w-4" />
      <span className="text-sm font-medium">Filters</span>
      {activeFilterCount > 0 && (
        <span className="flex items-center justify-center bg-white text-primary text-xs font-bold rounded-full h-5 min-w-[20px] px-1">
          {activeFilterCount}
        </span>
      )}
    </button>
  );
};
