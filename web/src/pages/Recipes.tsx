import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { Search, Plus, UtensilsCrossed, Loader2 } from 'lucide-react';
import { useRecipes } from '@/hooks/useRecipes';
import { RecipeCard } from '@/components/recipes/RecipeCard';
import { Header } from '@/components/layout/Header';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { RecipeCardSkeleton } from '@/components/recipes/RecipeCardSkeleton';

export const Recipes = () => {
  const [query, setQuery] = useState('');
  const [offset, setOffset] = useState(0);
  const [isDebouncing, setIsDebouncing] = useState(false);
  const { recipes, loading, error, fetchRecipes } = useRecipes();
  const limit = 12;

  // Fix 5: Show searching indicator during debounce
  useEffect(() => {
    setIsDebouncing(true);
    const debounceId = window.setTimeout(() => {
      setIsDebouncing(false);
      fetchRecipes({ q: query || undefined, limit, offset });
    }, 300);
    return () => {
      clearTimeout(debounceId);
    };
  }, [query, offset, fetchRecipes]);

  const totalPages = recipes ? Math.ceil(recipes.total / limit) : 0;
  const currentPage = Math.floor(offset / limit) + 1;

  return (
    <div className="min-h-screen bg-secondary">
      {/* Fix 4: Use shared Header for consistent navigation */}
      <Header showSearch={false} />

      {/* Content */}
      <div className="max-w-6xl mx-auto px-4 py-6">
        {/* Page title + actions */}
        <div className="flex items-center justify-between mb-4">
          <h1 className="text-xl font-semibold">Recipes</h1>
          <Link to="/recipes/create">
            <Button size="sm" className="gap-1.5">
              <Plus className="h-4 w-4" />
              <span className="hidden sm:inline">Create Recipe</span>
            </Button>
          </Link>
        </div>

        {/* Search with live feedback */}
        <div className="relative mb-6">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
          <Input
            placeholder="Search recipes..."
            value={query}
            onChange={(e) => {
              setQuery(e.target.value);
              setOffset(0);
            }}
            className="pl-10 pr-10 h-9 text-sm bg-white border shadow-sm"
          />
          {/* Fix 5: Searching indicator */}
          {(isDebouncing || loading) && query && (
            <Loader2 className="absolute right-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground animate-spin" />
          )}
        </div>
        {error && (
          <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-4 mb-4">
            <p className="text-sm text-destructive">{error}</p>
          </div>
        )}

        {loading && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <RecipeCardSkeleton key={i} />
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
