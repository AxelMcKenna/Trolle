import { Category } from '@/types';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface CategoryFilterProps {
  value?: string;
  onChange: (category?: string) => void;
}

const categories: { value: Category; label: string; group: string }[] = [
  // Fresh
  { value: 'Fruit & Vegetables', label: 'Fruit & Vegetables', group: 'Fresh' },
  { value: 'Meat & Seafood', label: 'Meat & Seafood', group: 'Fresh' },
  { value: 'Chilled, Dairy & Eggs', label: 'Dairy & Eggs', group: 'Fresh' },
  { value: 'Bakery', label: 'Bakery', group: 'Fresh' },

  // Pantry & Frozen
  { value: 'Pantry', label: 'Pantry', group: 'Pantry & Frozen' },
  { value: 'Frozen', label: 'Frozen', group: 'Pantry & Frozen' },
  { value: 'Drinks', label: 'Drinks', group: 'Pantry & Frozen' },
  { value: 'Snacks & Confectionery', label: 'Snacks & Confectionery', group: 'Pantry & Frozen' },

  // Non-Food
  { value: 'Health & Beauty', label: 'Health & Beauty', group: 'Non-Food' },
  { value: 'Household', label: 'Household', group: 'Non-Food' },
  { value: 'Baby & Child', label: 'Baby & Child', group: 'Non-Food' },
  { value: 'Pet', label: 'Pet', group: 'Non-Food' },

  // Alcohol
  { value: 'Beer, Wine & Cider', label: 'Beer, Wine & Cider', group: 'Other' },
];

const groupedCategories = categories.reduce((acc, cat) => {
  if (!acc[cat.group]) {
    acc[cat.group] = [];
  }
  acc[cat.group].push(cat);
  return acc;
}, {} as Record<string, typeof categories>);

export const CategoryFilter = ({ value, onChange }: CategoryFilterProps) => {
  return (
    <Select
      value={value || 'all'}
      onValueChange={(val) => onChange(val === 'all' ? undefined : val)}
    >
      <SelectTrigger id="category" className="w-full">
        <SelectValue placeholder="All Categories" />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value="all">All Categories</SelectItem>
        {Object.entries(groupedCategories).map(([group, items]) => (
          <div key={group}>
            <div className="px-2 py-1.5 text-xs font-semibold text-muted-foreground">
              {group}
            </div>
            {items.map((cat) => (
              <SelectItem key={cat.value} value={cat.value}>
                {cat.label}
              </SelectItem>
            ))}
          </div>
        ))}
      </SelectContent>
    </Select>
  );
};
