import { useState, useEffect } from 'react';
import { Link, useParams } from 'react-router-dom';
import { toast } from 'sonner';
import {
  Navigation,
  MapPin,
  AlertCircle,
  ArrowLeft,
  UtensilsCrossed,
  Users,
  Bookmark,
  ShoppingCart,
} from 'lucide-react';
import { api } from '@/lib/api';
import { useRecipeDetail } from '@/hooks/useRecipeDetail';
import { useRecipeCost } from '@/hooks/useRecipeCost';
import { useSavedRecipes } from '@/hooks/useSavedRecipes';
import { useAuth } from '@/contexts/AuthContext';
import { useLocationContext } from '@/contexts/LocationContext';
import { useTrolleyContext } from '@/contexts/TrolleyContext';
import { Header } from '@/components/layout/Header';
import { RecipeStoreRankCard } from '@/components/recipes/RecipeStoreRankCard';
import { IngredientBreakdown } from '@/components/recipes/IngredientBreakdown';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';
import { StoreRankSkeleton } from '@/components/trolley/StoreRankSkeleton';
import { ItemBreakdownSkeleton } from '@/components/trolley/ItemBreakdownSkeleton';

export const RecipeDetail = () => {
  const { id } = useParams<{ id: string }>();
  const { recipe, loading: recipeLoading, error: recipeError, fetchRecipe } = useRecipeDetail();
  const { costData, loading: costLoading, error: costError, compareCost } = useRecipeCost();
  const {
    location,
    radiusKm,
    isLocationSet,
    openLocationModal,
    requestAutoLocation,
    loading: locationLoading,
    error: locationError,
  } = useLocationContext();
  const { itemCount, addItems } = useTrolleyContext();
  const [selectedStoreId, setSelectedStoreId] = useState<string | null>(null);
  const [addingToTrolley, setAddingToTrolley] = useState(false);
  const { isAuthenticated } = useAuth();
  const { saveRecipe, unsaveRecipe, checkSaved } = useSavedRecipes();
  const [isSaved, setIsSaved] = useState(false);
  const [savingRecipe, setSavingRecipe] = useState(false);

  // Load recipe
  useEffect(() => {
    if (id) fetchRecipe(id);
  }, [id, fetchRecipe]);

  // Check if recipe is saved
  useEffect(() => {
    if (id && isAuthenticated) {
      checkSaved(id).then(setIsSaved);
    }
  }, [id, isAuthenticated, checkSaved]);

  // Auto-trigger cost comparison when recipe + location are available
  useEffect(() => {
    if (recipe && location && isLocationSet) {
      compareCost(recipe.id, location.lat, location.lon, radiusKm);
    }
  }, [recipe, location, radiusKm, isLocationSet, compareCost]);

  // Auto-select cheapest complete store
  useEffect(() => {
    if (costData?.stores.length && !selectedStoreId) {
      setSelectedStoreId(costData.stores[0].store_id);
    }
  }, [costData, selectedStoreId]);

  const selectedStore = costData?.stores.find((s) => s.store_id === selectedStoreId) ?? null;

  if (recipeLoading) {
    return (
      <div className="min-h-screen bg-secondary">
        <Header showSearch={false} />
        <div className="max-w-6xl mx-auto px-4 py-6">
          <Skeleton className="h-4 w-24 mb-3" />
          <Card className="p-4 bg-card border shadow-sm mb-6">
            <div className="flex items-start gap-4">
              <Skeleton className="w-20 h-20 rounded-lg flex-shrink-0" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-6 w-2/3" />
                <Skeleton className="h-4 w-full" />
                <div className="flex items-center gap-2">
                  <Skeleton className="h-5 w-16 rounded-full" />
                  <Skeleton className="h-5 w-28 rounded-full" />
                </div>
              </div>
            </div>
          </Card>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <Skeleton className="h-4 w-32 mb-3" />
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <StoreRankSkeleton key={i} />
                ))}
              </div>
            </div>
            <div>
              <Skeleton className="h-4 w-40 mb-3" />
              <ItemBreakdownSkeleton />
            </div>
          </div>
        </div>
      </div>
    );
  }

  if (recipeError || !recipe) {
    return (
      <div className="min-h-screen bg-secondary">
        <Header showSearch={false} />
        <div className="max-w-6xl mx-auto px-4 py-24 text-center">
          <AlertCircle className="h-12 w-12 text-destructive mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Recipe not found</h2>
          <Link to="/recipes">
            <Button variant="outline">Back to Recipes</Button>
          </Link>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary">
      {/* Fix 4: Use shared Header for consistent navigation */}
      <Header showSearch={false} />

      {/* Main content */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Recipe info */}
        <div className="mb-6">
          <Link to="/recipes" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-3">
            <ArrowLeft className="h-4 w-4" />
            Back to recipes
          </Link>
          <Card className="p-4 bg-card border shadow-sm">
            <div className="flex items-start gap-4">
              {recipe.image_url ? (
                <img src={recipe.image_url} alt={recipe.title} className="w-20 h-20 object-cover rounded-lg flex-shrink-0" />
              ) : (
                <div className="w-20 h-20 bg-gradient-to-br from-amber-400 to-orange-500 rounded-lg flex items-center justify-center flex-shrink-0">
                  <UtensilsCrossed className="h-8 w-8 text-white/80" />
                </div>
              )}
              <div className="flex-1 min-w-0">
                <h2 className="text-xl font-semibold">{recipe.title}</h2>
                {recipe.description && (
                  <p className="text-sm text-muted-foreground mt-1">{recipe.description}</p>
                )}
                <div className="flex items-center gap-2 mt-2">
                  <Badge variant="secondary" className="text-xs">
                    <Users className="h-3 w-3 mr-1" />
                    Serves {recipe.servings}
                  </Badge>
                  <Badge variant="secondary" className="text-xs">
                    {recipe.ingredients.length} ingredients
                  </Badge>
                  {isAuthenticated && (
                    <Button
                      variant={isSaved ? "default" : "outline"}
                      size="sm"
                      className="ml-auto h-7 text-xs"
                      disabled={savingRecipe}
                      onClick={async () => {
                        setSavingRecipe(true);
                        if (isSaved) {
                          const ok = await unsaveRecipe(recipe.id);
                          if (ok) { setIsSaved(false); toast.info("Recipe unsaved"); }
                        } else {
                          const ok = await saveRecipe(recipe.id);
                          if (ok) { setIsSaved(true); toast.success("Recipe saved"); }
                          else { toast.error("Failed to save recipe"); }
                        }
                        setSavingRecipe(false);
                      }}
                    >
                      <Bookmark className={`h-3 w-3 mr-1 ${isSaved ? "fill-current" : ""}`} />
                      {isSaved ? "Saved" : "Save"}
                    </Button>
                  )}
                </div>
              </div>
            </div>
          </Card>
        </div>
        {/* Fix 7: Show ingredients even without location, with location prompt inline */}
        {!isLocationSet && (
          <>
            {/* Ingredient list — visible without location */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              <div>
                <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
                  Ingredients ({recipe.ingredients.length})
                </h2>
                <Card className="bg-card overflow-hidden">
                  <div className="divide-y">
                    {recipe.ingredients.map((ing) => (
                      <div key={ing.id} className="px-4 py-3 flex items-center gap-3">
                        <div className="w-8 h-8 bg-secondary rounded flex items-center justify-center flex-shrink-0">
                          <UtensilsCrossed className="h-4 w-4 text-muted-foreground/50" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium">{ing.display_name}</p>
                          {ing.optional && (
                            <span className="text-[10px] text-muted-foreground">Optional</span>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </Card>
              </div>

              {/* Location prompt — inline alongside ingredients */}
              <div>
                <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
                  Price Comparison
                </h2>
                <Card className="p-6 text-center bg-card border">
                  <div className="inline-flex items-center justify-center w-12 h-12 rounded-lg bg-secondary mb-4">
                    <Navigation className="h-6 w-6 text-primary" />
                  </div>
                  <h3 className="text-lg font-semibold mb-2">Enable location to compare prices</h3>
                  <p className="text-sm text-muted-foreground mb-5">
                    See which nearby store has the cheapest ingredients for this recipe.
                  </p>
                  {locationError && (
                    <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg">
                      <p className="text-sm text-destructive">{locationError}</p>
                    </div>
                  )}
                  <div className="space-y-2">
                    <Button onClick={requestAutoLocation} disabled={locationLoading} className="w-full">
                      {locationLoading ? 'Getting location...' : (
                        <><Navigation className="h-4 w-4 mr-2" />Use My Location</>
                      )}
                    </Button>
                    <Button onClick={openLocationModal} variant="outline" className="w-full">
                      <MapPin className="h-4 w-4 mr-2" />Set Manually
                    </Button>
                  </div>
                </Card>
              </div>
            </div>
          </>
        )}

        {/* Loading */}
        {isLocationSet && costLoading && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            <div>
              <Skeleton className="h-4 w-32 mb-3" />
              <div className="space-y-2">
                {[1, 2, 3].map((i) => (
                  <StoreRankSkeleton key={i} />
                ))}
              </div>
            </div>
            <div>
              <Skeleton className="h-4 w-40 mb-3" />
              <ItemBreakdownSkeleton />
            </div>
          </div>
        )}

        {/* Error */}
        {isLocationSet && costError && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 mb-4">
            <p className="text-sm text-destructive flex items-center gap-2">
              <AlertCircle className="h-4 w-4" />
              {costError}
            </p>
          </div>
        )}

        {/* Results */}
        {isLocationSet && !costLoading && costData && (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
            {/* Left — Store rankings */}
            <div>
              <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
                Store Rankings
              </h2>
              {costData.stores.length === 0 ? (
                <Card className="p-6 text-center bg-card">
                  <p className="text-sm text-muted-foreground">No nearby stores found</p>
                </Card>
              ) : (
                <div className="space-y-2">
                  {costData.stores.map((store, idx) => (
                    <RecipeStoreRankCard
                      key={store.store_id}
                      store={store}
                      rank={idx + 1}
                      isSelected={store.store_id === selectedStoreId}
                      isBestPrice={idx === 0 && store.is_complete}
                      onClick={() => setSelectedStoreId(store.store_id)}
                    />
                  ))}
                </div>
              )}
            </div>

            {/* Right — Ingredient breakdown */}
            <div>
              <h2 className="text-sm font-semibold text-muted-foreground mb-3 uppercase tracking-wide">
                Ingredient Breakdown
              </h2>
              {selectedStore ? (
                <>
                  <IngredientBreakdown store={selectedStore} />
                  <Button
                    className="w-full mt-3"
                    disabled={addingToTrolley}
                    onClick={async () => {
                      if (!selectedStore || !recipe || !location) return;
                      setAddingToTrolley(true);
                      try {
                        const resp = await api.post<{
                          items: Array<{ product_id: string; name: string; image_url: string | null; price: number }>;
                          matched: number;
                          total_ingredients: number;
                        }>(`/recipes/${recipe.id}/to-trolley`, {
                          store_id: selectedStore.store_id,
                          lat: location.lat,
                          lon: location.lon,
                          radius_km: radiusKm,
                        });
                        const products = resp.data.items.map((item) => ({
                          product_id: item.product_id,
                          name: item.name,
                          image_url: item.image_url,
                          chain: selectedStore.chain,
                        }));
                        addItems(products);
                      } catch {
                        toast.error('Failed to add ingredients to trolley');
                      } finally {
                        setAddingToTrolley(false);
                      }
                    }}
                  >
                    <ShoppingCart className="h-4 w-4 mr-2" />
                    {addingToTrolley ? 'Adding...' : 'Add Ingredients to Trolley'}
                  </Button>
                </>
              ) : (
                <Card className="p-6 text-center bg-card">
                  <p className="text-sm text-muted-foreground">Select a store to see the breakdown</p>
                </Card>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
};

export default RecipeDetail;
