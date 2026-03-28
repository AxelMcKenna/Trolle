import { useFilters } from '@/hooks/useFilters';
import { Category } from '@/types';
import { cn } from '@/lib/utils';
import {
  Apple,
  Beef,
  Egg,
  Croissant,
  Package,
  Snowflake,
  GlassWater,
  Candy,
  Heart,
  Home,
  Baby,
  Dog,
  Wine,
} from 'lucide-react';
import { ComponentType } from 'react';

interface CategoryDef {
  value: Category;
  label: string;
  icon: ComponentType<{ className?: string }>;
}

const categories: CategoryDef[] = [
  { value: 'Fruit & Vegetables', label: 'Fruit & Veg', icon: Apple },
  { value: 'Meat & Seafood', label: 'Meat & Seafood', icon: Beef },
  { value: 'Chilled, Dairy & Eggs', label: 'Dairy & Eggs', icon: Egg },
  { value: 'Bakery', label: 'Bakery', icon: Croissant },
  { value: 'Pantry', label: 'Pantry', icon: Package },
  { value: 'Frozen', label: 'Frozen', icon: Snowflake },
  { value: 'Drinks', label: 'Drinks', icon: GlassWater },
  { value: 'Snacks & Confectionery', label: 'Snacks', icon: Candy },
  { value: 'Health & Beauty', label: 'Health & Beauty', icon: Heart },
  { value: 'Household', label: 'Household', icon: Home },
  { value: 'Baby & Child', label: 'Baby & Child', icon: Baby },
  { value: 'Pet', label: 'Pet', icon: Dog },
  { value: 'Beer, Wine & Cider', label: 'Beer & Wine', icon: Wine },
];

export const CategoryBar = () => {
  const { filters, updateFilters } = useFilters();
  // Fix 8: Support multi-select — category param is comma-separated
  const activeCategories = filters.category ? filters.category.split(',') : [];

  return (
    <div className="bg-secondary overflow-x-auto [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]">
      <div className="flex justify-center">
        <div className="flex gap-1.5 px-4 pt-4 pb-2.5">
          {categories.map(({ value, label, icon: Icon }) => {
            const isActive = activeCategories.includes(value);
            return (
              <button
                key={value}
                onClick={() => {
                  let next: string[];
                  if (isActive) {
                    next = activeCategories.filter((c) => c !== value);
                  } else {
                    next = [...activeCategories, value];
                  }
                  updateFilters({ category: next.length > 0 ? next.join(',') : undefined });
                }}
                className={cn(
                  'flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-sm font-medium whitespace-nowrap transition-colors',
                  isActive
                    ? 'bg-primary text-white'
                    : 'bg-gray-100 text-gray-700 hover:bg-gray-200'
                )}
              >
                <Icon className="h-3.5 w-3.5" />
                {label}
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
};
