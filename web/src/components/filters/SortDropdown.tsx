import { SortOption } from '@/types';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

interface SortDropdownProps {
  value: SortOption;
  onChange: (value: SortOption) => void;
}

const sortOptions = [
  { value: SortOption.DISCOUNT, label: 'Largest Discount' },
  { value: SortOption.CHEAPEST, label: 'Cheapest' },
  { value: SortOption.UNIT_PRICE, label: 'Best Unit Price' },
  { value: SortOption.DISTANCE, label: 'Nearest Store' },
  { value: SortOption.NEWEST, label: 'Newest' },
];

export const SortDropdown = ({ value, onChange }: SortDropdownProps) => {
  return (
    <Select value={value} onValueChange={onChange}>
      <SelectTrigger id="sort" className="w-full">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {sortOptions.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
};
