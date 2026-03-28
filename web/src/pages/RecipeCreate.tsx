import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Plus, Trash2, Loader2 } from 'lucide-react';
import { useRecipeCreate } from '@/hooks/useRecipeCreate';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Card } from '@/components/ui/card';

export const RecipeCreate = () => {
  const navigate = useNavigate();
  const { loading, error, createRecipe } = useRecipeCreate();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [servings, setServings] = useState(4);
  const [ingredients, setIngredients] = useState<string[]>(['']);

  const addIngredient = () => {
    setIngredients([...ingredients, '']);
  };

  const removeIngredient = (index: number) => {
    if (ingredients.length <= 1) return;
    setIngredients(ingredients.filter((_, i) => i !== index));
  };

  const updateIngredient = (index: number, value: string) => {
    const updated = [...ingredients];
    updated[index] = value;
    setIngredients(updated);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    const validIngredients = ingredients.filter((i) => i.trim());
    if (!title.trim() || validIngredients.length === 0) return;

    const result = await createRecipe({
      title: title.trim(),
      description: description.trim() || undefined,
      servings,
      ingredients: validIngredients.map((desc) => ({ description: desc.trim() })),
    });

    if (result) {
      navigate(`/recipes/${result.id}`);
    }
  };

  return (
    <div className="min-h-screen bg-secondary">
      {/* Header bar */}
      <div className="bg-primary text-white px-4 py-3">
        <div className="max-w-6xl mx-auto flex items-center gap-3">
          <Link to="/" className="text-lg font-semibold">TROLL-E</Link>
          <span className="text-white/60">/</span>
          <Link to="/recipes" className="text-sm text-white/80 hover:text-white">Recipes</Link>
          <span className="text-white/60">/</span>
          <h1 className="text-sm font-medium">Create Recipe</h1>
        </div>
      </div>

      {/* Form */}
      <div className="max-w-2xl mx-auto px-4 py-6">
        <Card className="p-6 bg-card">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="text-sm font-medium mb-1.5 block">Recipe Title</label>
              <Input
                placeholder="e.g. Spaghetti Bolognese"
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                required
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-1.5 block">Description (optional)</label>
              <Input
                placeholder="A short description of the recipe"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-1.5 block">Servings</label>
              <Input
                type="number"
                min={1}
                max={100}
                value={servings}
                onChange={(e) => setServings(Number(e.target.value) || 4)}
                className="w-24"
              />
            </div>

            <div>
              <label className="text-sm font-medium mb-1.5 block">Ingredients</label>
              <p className="text-xs text-muted-foreground mb-3">
                Enter each ingredient as you'd write it (e.g. "500g chicken breast", "2 tbsp olive oil")
              </p>
              <div className="space-y-2">
                {ingredients.map((ing, idx) => (
                  <div key={idx} className="flex items-center gap-2">
                    <Input
                      placeholder={`Ingredient ${idx + 1}`}
                      value={ing}
                      onChange={(e) => updateIngredient(idx, e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') {
                          e.preventDefault();
                          addIngredient();
                        }
                      }}
                    />
                    <Button
                      type="button"
                      variant="ghost"
                      size="sm"
                      className="flex-shrink-0 text-muted-foreground hover:text-destructive"
                      onClick={() => removeIngredient(idx)}
                      disabled={ingredients.length <= 1}
                    >
                      <Trash2 className="h-4 w-4" />
                    </Button>
                  </div>
                ))}
              </div>
              <Button
                type="button"
                variant="outline"
                size="sm"
                className="mt-3 gap-1"
                onClick={addIngredient}
              >
                <Plus className="h-4 w-4" />
                Add Ingredient
              </Button>
            </div>

            {error && (
              <div className="bg-destructive/10 border border-destructive/20 rounded-lg p-3">
                <p className="text-sm text-destructive">{error}</p>
              </div>
            )}

            <div className="flex items-center gap-3 pt-2">
              <Button type="submit" disabled={loading || !title.trim() || !ingredients.some(i => i.trim())}>
                {loading ? (
                  <><Loader2 className="h-4 w-4 mr-2 animate-spin" />Creating...</>
                ) : (
                  'Create Recipe'
                )}
              </Button>
              <Link to="/recipes">
                <Button type="button" variant="outline">Cancel</Button>
              </Link>
            </div>
          </form>
        </Card>
      </div>
    </div>
  );
};

export default RecipeCreate;
