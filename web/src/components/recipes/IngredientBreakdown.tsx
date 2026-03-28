import { Card } from '@/components/ui/card';
import { ChainLogo } from '@/components/stores/logos/ChainLogo';
import { UtensilsCrossed } from 'lucide-react';
import { RecipeStoreBreakdown } from '@/types';

interface IngredientBreakdownProps {
  store: RecipeStoreBreakdown;
}

export const IngredientBreakdown = ({ store }: IngredientBreakdownProps) => {
  return (
    <Card className="bg-card overflow-hidden">
      <div className="p-4 border-b bg-secondary/50">
        <div className="flex items-center gap-2">
          <ChainLogo chain={store.chain} className="h-5 w-5" />
          <span className="font-medium text-sm">{store.store_name}</span>
        </div>
      </div>
      <div className="divide-y">
        {store.ingredients.map((ingredient) => (
          <div
            key={ingredient.ingredient_id}
            className={`p-3 flex items-center gap-3 ${!ingredient.available ? 'opacity-50' : ''}`}
          >
            {ingredient.matched_product_image ? (
              <img
                src={ingredient.matched_product_image}
                alt={ingredient.display_name}
                className="w-10 h-10 object-contain rounded flex-shrink-0"
              />
            ) : (
              <div className="w-10 h-10 bg-muted rounded flex items-center justify-center flex-shrink-0">
                <UtensilsCrossed className="h-4 w-4 text-muted-foreground/30" />
              </div>
            )}
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium truncate">
                {ingredient.matched_product_name ?? ingredient.display_name}
              </p>
              <p className="text-xs text-muted-foreground truncate">
                {ingredient.ingredient_description}
                {ingredient.optional && ' (optional)'}
              </p>
            </div>
            <div className="text-right flex-shrink-0">
              {ingredient.available && ingredient.price != null ? (
                <p className="text-sm font-semibold">${ingredient.price.toFixed(2)}</p>
              ) : (
                <p className="text-xs text-muted-foreground">
                  {ingredient.optional ? 'Optional' : 'Unavailable'}
                </p>
              )}
            </div>
          </div>
        ))}
      </div>
      <div className="p-4 border-t bg-secondary/50 flex items-center justify-between">
        <span className="text-sm text-muted-foreground">
          {store.items_available}/{store.items_total} ingredients matched
        </span>
        <span className="text-lg font-bold text-primary">
          ${store.estimated_total.toFixed(2)}
        </span>
      </div>
    </Card>
  );
};
