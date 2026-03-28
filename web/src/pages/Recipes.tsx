import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Search, Plus, UtensilsCrossed, ShoppingCart, MapPin } from 'lucide-react';
import { useRecipes } from '@/hooks/useRecipes';
import { RecipeCard } from '@/components/recipes/RecipeCard';
import { useTrolleyContext } from '@/contexts/TrolleyContext';
import { useLocationContext } from '@/contexts/LocationContext';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Skeleton } from '@/components/ui/skeleton';

export const Recipes = () => {
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const { recipes, loading, error, fetchRecipes } = useRecipes();
  const { itemCount } = useTrolleyContext();
  const { radiusKm, isLocationSet, openLocationModal } = useLocationContext();
  const limit = 12;

  useEffect(() => {
    const debounceId = window.setTimeout(() => {
      fetchRecipes({ q: query || undefined, limit, offset });
    }, 300);
    return () => clearTimeout(debounceId);
  }, [query, offset, fetchRecipes]);

  const totalPages = recipes ? Math.ceil(recipes.total / limit) : 0;
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="min-h-screen bg-secondary">
      {/* Header bar */}
      <div className="bg-primary text-white px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-3">
            <Link to="/" className="text-lg font-bold font-sans tracking-[0.15em]">TROLL-E</Link>
            <span className="text-white/60">/</span>
            <h1 className="text-sm font-medium">Recipes</h1>
          </div>
          <div className="flex items-center gap-1">
            <Link to="/recipes/create">
              <Button size="sm" variant="secondary" className="gap-1">
                <Plus className="h-4 w-4" />
                <span className="hidden sm:inline">Create Recipe</span>
              </Button>
            </Link>
            <Link to="/explore">
              <Button variant="ghost" size="sm" className="text-white hover:bg-white/10">
                <Search className="h-4 w-4" />
                <span className="hidden sm:inline ml-1">Explore</span>
              </Button>
            </Link>
            <Link to="/trolley">
              <Button variant="ghost" size="sm" className="text-white hover:bg-white/10 relative">
                <ShoppingCart className="h-4 w-4" />
                {itemCount > 0 && (
                  <span className="absolute -top-1 -right-1 bg-white text-primary text-[10px] font-bold rounded-full h-4 min-w-[16px] flex items-center justify-center px-0.5">
                    {itemCount}
                  </span>
                )}
              </Button>
            </Link>
            <Button variant="ghost" size="sm" onClick={openLocationModal} className="text-white hover:bg-white/10">
              <MapPin className="h-4 w-4" />
              <span className="hidden sm:inline ml-1">{isLocationSet ? `${radiusKm} km` : 'Location'}</span>
            </Button>
          </div>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Search */}
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search recipes..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
            className="pl-10 h-9 text-sm bg-white border shadow-sm"
          />
        </div>
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 mb-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {loading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <Skeleton key={i} className="h-56 w-full rounded-lg" />
            ))}
          </div>
        )}

        {!loading && recipes && recipes.items.length === 0 && (
          <div className="flex items-center justify-center py-24">
            <div className="text-center">
              <div className="inline-flex items-center justify-center w-16 h-16 rounded-full bg-white mb-4">
                <UtensilsCrossed className="h-8 w-8 text-muted-foreground" />
              </div>
              <h2 className="text-xl font-semibold mb-2">No recipes found</h2>
              <p className="text-sm text-muted-foreground mb-4">
                {query ? 'Try a different search term' : 'Create your first recipe to get started'}
              </p>
              <Link to="/recipes/create">
                <Button>Create Recipe</Button>
              </Link>
            </div>
          </div>
        )}

        {!loading && recipes && recipes.items.length > 0 && (
          <>
            <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
              {recipes.items.map((recipe) => (
                <RecipeCard key={recipe.id} recipe={recipe} />
              ))}
            </div>

            {/* Pagination */}
            {totalPages > 1 && (
              <div className="flex items-center justify-center gap-2 mt-8">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPage <= 1}
                  onClick={() => setOffset(Math.max(0, offset - limit))}
                >
                  Previous
                </Button>
                <span className="text-sm text-muted-foreground">
                  Page {currentPage} of {totalPages}
                </span>
                <Button
                  variant="outline"
                  size="sm"
                  disabled={currentPage >= totalPages}
                  onClick={() => setOffset(offset + limit)}
                >
                  Next
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};

export default Recipes;
