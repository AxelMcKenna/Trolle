import { Checkbox } from '@/components/ui/checkbox';
import { Label } from '@/components/ui/label';

interface MemberPriceToggleProps {
  checked: boolean;
  onChange: (checked: boolean) => void;
}

export const MemberPriceToggle = ({ checked, onChange }: MemberPriceToggleProps) => {
  return (
    <div className="flex items-center space-x-2">
      <Checkbox
        id="member-prices"
        checked={checked}
        onCheckedChange={(checkedState) => onChange(checkedState === true)}
      />
      <Label
        htmlFor="member-prices"
        className="text-sm font-medium cursor-pointer"
      >
        Include member-only prices
      </Label>
    </div>
  );
};
