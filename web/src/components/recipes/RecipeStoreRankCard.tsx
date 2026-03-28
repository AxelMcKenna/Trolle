import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ChainLogo } from '@/components/stores/logos/ChainLogo';
import { Award, ChevronRight } from 'lucide-react';
import { getChainName } from '@/lib/chainConstants';
import { RecipeStoreBreakdown } from '@/types';

interface RecipeStoreRankCardProps {
  store: RecipeStoreBreakdown;
  rank: number;
  isSelected: boolean;
  isBestPrice: boolean;
  onClick: () => void;
}

export const RecipeStoreRankCard = ({
  store,
  rank,
  isSelected,
  isBestPrice,
  onClick,
}: RecipeStoreRankCardProps) => {
  return (
    <Card
      className={`p-3 cursor-pointer transition-all hover:shadow-sm ${
        isSelected ? 'ring-2 ring-primary bg-primary/5' : 'bg-card'
      }`}
      onClick={onClick}
    >
      <div className="flex items-center gap-3">
        <div className="flex-shrink-0 w-6 text-center">
          <span className="text-xs font-bold text-muted-foreground">#{rank}</span>
        </div>
        <ChainLogo chain={store.chain} className="h-6 w-6 flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-2">
            <p className="text-sm font-medium truncate">{store.store_name}</p>
            {isBestPrice && (
              <Badge className="bg-primary text-white text-[10px] px-1.5 py-0">
                <Award className="h-3 w-3 mr-0.5" />
                Best Price
              </Badge>
            )}
          </div>
          <div className="flex items-center gap-3 text-xs text-muted-foreground mt-0.5">
            <span>{getChainName(store.chain)}</span>
            <span>{store.distance_km} km</span>
            <Badge
              variant={store.is_complete ? 'default' : 'secondary'}
              className="text-[10px] px-1.5 py-0"
            >
              {store.items_available}/{store.items_total} items
            </Badge>
          </div>
        </div>
        <div className="text-right flex-shrink-0">
          <p className="text-lg font-bold text-primary">${store.estimated_total.toFixed(2)}</p>
        </div>
        <ChevronRight className="h-4 w-4 text-muted-foreground flex-shrink-0" />
      </div>
    </Card>
  );
};
