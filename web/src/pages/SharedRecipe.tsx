import { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { UtensilsCrossed, ArrowLeft, Copy, Check, Bookmark } from 'lucide-react';
import { toast } from 'sonner';
import { api } from '@/lib/api';
import { useAuth } from '@/contexts/AuthContext';
import { useSavedRecipes } from '@/hooks/useSavedRecipes';
import { Button } from '@/components/ui/button';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Skeleton } from '@/components/ui/skeleton';

interface SharedRecipeData {
  id: string;
  title: string;
  description: string | null;
  servings: number;
  image_url: string | null;
  ingredients: Array<{
    id: string;
    description: string;
    quantity: number | null;
    unit: string | null;
    display_name: string;
    optional: boolean;
  }>;
}

export const SharedRecipe = () => {
  const { token } = useParams<{ token: string }>();
  const [recipe, setRecipe] = useState<SharedRecipeData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const { isAuthenticated } = useAuth();
  const { saveRecipe } = useSavedRecipes();

  useEffect(() => {
    if (!token) return;
    setLoading(true);
    api.get<SharedRecipeData>(`/recipes/shared/${token}`)
      .then((res) => setRecipe(res.data))
      .catch(() => setError('Shared recipe not found'))
      .finally(() => setLoading(false));
  }, [token]);

  const handleCopyLink = async () => {
    await navigator.clipboard.writeText(window.location.href);
    setCopied(true);
    toast.success('Link copied');
    setTimeout(() => setCopied(false), 2000);
  };

  const handleSave = async () => {
    if (!recipe) return;
    const ok = await saveRecipe(recipe.id);
    if (ok) toast.success('Recipe saved to your collection');
    else toast.error('Failed to save recipe');
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-secondary">
        <div className="max-w-2xl mx-auto px-4 py-12">
          <Skeleton className="h-8 w-48 mb-4" />
          <Skeleton className="h-64 w-full rounded-lg" />
        </div>
      </div>
    );
  }

  if (error || !recipe) {
    return (
      <div className="min-h-screen bg-secondary flex items-center justify-center">
        <Card className="p-8 text-center max-w-md">
          <UtensilsCrossed className="h-12 w-12 text-muted-foreground mx-auto mb-4" />
          <h2 className="text-xl font-semibold mb-2">Recipe not found</h2>
          <p className="text-sm text-muted-foreground mb-4">This shared recipe may have been removed.</p>
          <Link to="/recipes"><Button>Browse Recipes</Button></Link>
        </Card>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-secondary">
      <div className="bg-primary text-white px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center justify-between">
          <Link to="/" className="text-lg font-bold font-sans tracking-[0.15em]">TROLL-E</Link>
          <Link to="/recipes">
            <Button variant="ghost" size="sm" className="text-white hover:bg-white/10">
              <UtensilsCrossed className="h-4 w-4 mr-1" />Recipes
            </Button>
          </Link>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6">
        <Link to="/recipes" className="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground mb-4">
          <ArrowLeft className="h-4 w-4" />Back to Recipes
        </Link>

        <Card className="p-4 mb-4">
          <div className="flex items-start gap-4 mb-4">
            {recipe.image_url ? (
              <img src={recipe.image_url} alt={recipe.title} className="w-20 h-20 object-cover rounded-lg" />
            ) : (
              <div className="w-20 h-20 bg-gradient-to-br from-amber-400 to-orange-500 rounded-lg flex items-center justify-center">
                <UtensilsCrossed className="h-8 w-8 text-white/80" />
              </div>
            )}
            <div>
              <h1 className="text-xl font-semibold">{recipe.title}</h1>
              {recipe.description && <p className="text-sm text-muted-foreground mt-1">{recipe.description}</p>}
              <div className="flex gap-2 mt-2">
                <Badge variant="secondary" className="text-xs">Serves {recipe.servings}</Badge>
                <Badge variant="secondary" className="text-xs">{recipe.ingredients.length} ingredients</Badge>
              </div>
            </div>
          </div>

          <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide mb-2">Ingredients</h3>
          <div className="space-y-1.5">
            {recipe.ingredients.map((ing) => (
              <div key={ing.id} className="flex items-center gap-2 p-2 bg-secondary rounded">
                <span className="text-sm">{ing.description}</span>
                {ing.optional && <Badge variant="outline" className="text-[10px]">Optional</Badge>}
              </div>
            ))}
          </div>
        </Card>

        <div className="flex gap-2">
          <Link to={`/recipes/${recipe.id}`} className="flex-1">
            <Button className="w-full">
              <UtensilsCrossed className="h-4 w-4 mr-2" />View Full Recipe & Prices
            </Button>
          </Link>
          {isAuthenticated && (
            <Button variant="outline" onClick={handleSave}>
              <Bookmark className="h-4 w-4" />
            </Button>
          )}
          <Button variant="outline" onClick={handleCopyLink}>
            {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
};

export default SharedRecipe;
