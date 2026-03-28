import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { toast } from 'sonner';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { UtensilsCrossed, Users, Bookmark } from 'lucide-react';
import { RecipeListItem } from '@/types';
import { useAuth } from '@/contexts/AuthContext';
import { useSavedRecipes } from '@/hooks/useSavedRecipes';

const PLACEHOLDER_GRADIENTS = [
  'from-amber-400 to-orange-500',
  'from-emerald-400 to-teal-500',
  'from-violet-400 to-purple-500',
  'from-rose-400 to-pink-500',
  'from-sky-400 to-blue-500',
  'from-lime-400 to-green-500',
];

function getGradient(title: string) {
  let hash = 0;
  for (let i = 0; i < title.length; i++) hash = title.charCodeAt(i) + ((hash << 5) - hash);
  return PLACEHOLDER_GRADIENTS[Math.abs(hash) % PLACEHOLDER_GRADIENTS.length];
}

interface RecipeCardProps {
  recipe: RecipeListItem;
}

export const RecipeCard = ({ recipe }: RecipeCardProps) => {
  const { isAuthenticated } = useAuth();
  const { saveRecipe, unsaveRecipe, checkSaved } = useSavedRecipes();
  const [isSaved, setIsSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isAuthenticated) {
      checkSaved(recipe.id).then(setIsSaved);
    }
  }, [isAuthenticated, recipe.id, checkSaved]);

  const handleToggleSave = async (e: React.MouseEvent) => {
    e.preventDefault(); // Prevent Link navigation
    e.stopPropagation();
    setSaving(true);
    if (isSaved) {
      const ok = await unsaveRecipe(recipe.id);
      if (ok) { setIsSaved(false); toast.info("Recipe unsaved"); }
    } else {
      const ok = await saveRecipe(recipe.id);
      if (ok) { setIsSaved(true); toast.success("Recipe saved"); }
      else { toast.error("Failed to save recipe"); }
    }
    setSaving(false);
  };

  return (
    <Link to={`/recipes/${recipe.id}`}>
      <Card className="p-4 hover:shadow-md transition-all cursor-pointer bg-card h-full flex flex-col relative">
        {isAuthenticated && (
          <button
            onClick={handleToggleSave}
            disabled={saving}
            className="absolute top-2 right-2 z-10 p-1.5 rounded-full bg-white/80 hover:bg-white shadow-sm transition-colors"
            title={isSaved ? "Unsave recipe" : "Save recipe"}
          >
            <Bookmark className={`h-4 w-4 ${isSaved ? "fill-primary text-primary" : "text-gray-400"}`} />
          </button>
        )}
        {recipe.image_url ? (
          <img
            src={recipe.image_url}
            alt={recipe.title}
            className="w-full h-36 object-cover rounded-md mb-3"
          />
        ) : (
          <div className={`w-full h-36 bg-gradient-to-br ${getGradient(recipe.title)} rounded-md mb-3 flex items-center justify-center`}>
            <div className="text-center">
              <UtensilsCrossed className="h-8 w-8 text-white/80 mx-auto mb-1" />
              <span className="text-white/90 text-xs font-medium px-2 line-clamp-1">{recipe.title}</span>
            </div>
          </div>
        )}
        <h3 className="font-semibold text-sm mb-1 truncate">{recipe.title}</h3>
        {recipe.description && (
          <p className="text-xs text-muted-foreground line-clamp-2 mb-3 flex-1">
            {recipe.description}
          </p>
        )}
        <div className="flex items-center gap-2 mt-auto">
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            <Users className="h-3 w-3 mr-0.5" />
            {recipe.servings}
          </Badge>
          <Badge variant="secondary" className="text-[10px] px-1.5 py-0">
            {recipe.ingredient_count} ingredients
          </Badge>
        </div>
      </Card>
    </Link>
  );
};
