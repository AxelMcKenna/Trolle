import { useState, useEffect } from "react";
import { useNavigate, Link } from "react-router-dom";
import { toast } from "sonner";
import { LogOut, User, ShoppingCart, Trash2, Pencil, ArrowLeft, UtensilsCrossed, Bookmark, Crown, TrendingUp, Store, BarChart3 } from "lucide-react";
import everydayRewardsLogo from "@/assets/logos/everyday_rewards.svg";
import nwClubcardLogo from "@/assets/logos/nw_clubcard.svg";
import paknsaveClubcardLogo from "@/assets/logos/paknsave_clubcard.svg";
import { useAuth } from "@/contexts/AuthContext";
import { useSavedTrolleys, SavedTrolley } from "@/hooks/useSavedTrolleys";
import { useSavedRecipes, SavedRecipeItem } from "@/hooks/useSavedRecipes";
import { useTrolleyContext } from "@/contexts/TrolleyContext";
import { useLoyaltyCards } from "@/hooks/useLoyaltyCards";
import { useSavingsStats } from "@/hooks/useSavingsStats";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Checkbox } from "@/components/ui/checkbox";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { api } from "@/lib/api";

interface UserProfile {
  id: string;
  email: string;
  display_name: string | null;
  preferred_radius_km: number;
  saved_trolley_count: number;
}

const Account = () => {
  const { user, signOut } = useAuth();
  const navigate = useNavigate();
  const { items: trolleyItems } = useTrolleyContext();
  const { loyaltyCards, setLoyaltyCard } = useLoyaltyCards();
  const { trolleys, loading: trolleysLoading, fetchTrolleys, deleteTrolley, updateTrolley } = useSavedTrolleys();
  const { recipes: savedRecipes, loading: recipesLoading, fetchSavedRecipes, unsaveRecipe } = useSavedRecipes();
  const { stats: savingsStats, history: comparisonHistory, loading: savingsLoading } = useSavingsStats();

  const [profile, setProfile] = useState<UserProfile | null>(null);
  const [displayName, setDisplayName] = useState("");
  const [editingName, setEditingName] = useState(false);
  const [profileLoading, setProfileLoading] = useState(true);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");
  const [deleteAccountOpen, setDeleteAccountOpen] = useState(false);
  const [deleteTrolleyTarget, setDeleteTrolleyTarget] = useState<{ id: string; name: string } | null>(null);
  const [unsaveRecipeTarget, setUnsaveRecipeTarget] = useState<{ id: string; title: string } | null>(null);

  useEffect(() => {
    const loadProfile = async () => {
      try {
        const { data } = await api.get<UserProfile>("/users/me");
        setProfile(data);
        setDisplayName(data.display_name ?? "");
      } catch {
        toast.error("Failed to load profile");
      } finally {
        setProfileLoading(false);
      }
    };

    loadProfile();
    fetchTrolleys();
    fetchSavedRecipes();
  }, [fetchTrolleys, fetchSavedRecipes]);

  const handleUpdateName = async () => {
    try {
      const { data } = await api.patch<UserProfile>("/users/me", {
        display_name: displayName,
      });
      setProfile(data);
      setEditingName(false);
      toast.success("Display name updated");
    } catch {
      toast.error("Failed to update name");
    }
  };

  const handleSignOut = async () => {
    await signOut();
    navigate("/");
  };

  const handleDeleteAccount = async () => {
    try {
      await api.delete("/users/me");
      await signOut();
      toast.success("Account deleted");
      navigate("/");
    } catch {
      toast.error("Failed to delete account");
    }
  };

  const handleLoadTrolley = (trolley: SavedTrolley) => {
    // Load trolley items into local storage trolley
    const trolleyItemsMapped = trolley.items.map((item: any) => ({
      product_id: item.product_id,
      name: item.name,
      brand: item.brand ?? null,
      size: item.size ?? null,
      chain: item.chain,
      image_url: item.image_url ?? null,
      department: item.department ?? null,
      quantity: item.quantity ?? 1,
    }));
    localStorage.setItem("trolle.trolley", JSON.stringify(trolleyItemsMapped));
    toast.success(`Loaded "${trolley.name}" into your trolley`);
    navigate("/trolley");
  };

  const handleRename = async (id: string) => {
    if (!renameValue.trim()) return;
    await updateTrolley(id, { name: renameValue.trim() });
    setRenamingId(null);
    toast.success("Trolley renamed");
  };

  const handleDelete = async (id: string) => {
    await deleteTrolley(id);
    toast.success("Trolley deleted");
  };

  if (profileLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gray-50">
        <div className="w-12 h-12 border-4 border-primary border-t-transparent rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <div className="bg-primary text-white px-4 py-3">
        <div className="max-w-2xl mx-auto flex items-center gap-3">
          <Link to="/">
            <Button variant="ghost" size="sm" className="text-white hover:bg-white/10">
              <ArrowLeft className="h-4 w-4" />
            </Button>
          </Link>
          <span className="text-lg font-semibold">Account</span>
        </div>
      </div>

      <div className="max-w-2xl mx-auto px-4 py-6 space-y-6">
        {/* Profile Section */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <div className="flex items-center gap-4 mb-6">
            <div className="w-12 h-12 bg-primary/10 rounded-full flex items-center justify-center text-lg font-bold text-primary">
              {(profile?.display_name?.[0] ?? user?.email?.[0] ?? "U").toUpperCase()}
            </div>
            <div>
              <p className="font-medium">{profile?.display_name || user?.email}</p>
              <p className="text-sm text-gray-500">{user?.email}</p>
            </div>
          </div>

          <div className="space-y-4">
            <div>
              <label className="text-sm font-medium text-gray-700">Display Name</label>
              {editingName ? (
                <div className="flex gap-2 mt-1">
                  <Input
                    value={displayName}
                    onChange={(e) => setDisplayName(e.target.value)}
                    maxLength={100}
                    autoFocus
                    onKeyDown={(e) => e.key === "Enter" && handleUpdateName()}
                  />
                  <Button size="sm" onClick={handleUpdateName}>Save</Button>
                  <Button size="sm" variant="outline" onClick={() => setEditingName(false)}>Cancel</Button>
                </div>
              ) : (
                <div className="flex items-center gap-2 mt-1">
                  <p className="text-gray-600">{profile?.display_name || "Not set"}</p>
                  <button onClick={() => setEditingName(true)} className="text-primary hover:underline text-sm">
                    Edit
                  </button>
                </div>
              )}
            </div>
          </div>
        </div>

        {/* Savings Dashboard */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
            <TrendingUp className="w-5 h-5 text-green-600" />
            Your Savings
          </h2>

          {savingsLoading ? (
            <div className="py-6 text-center text-gray-400">Loading savings...</div>
          ) : !savingsStats || savingsStats.total_comparisons === 0 ? (
            <div className="py-6 text-center text-gray-400">
              <BarChart3 className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p>No comparisons yet</p>
              <p className="text-sm mt-1">Compare your trolley to start tracking savings.</p>
            </div>
          ) : (
            <>
              {/* Stats grid */}
              <div className="grid grid-cols-2 gap-3 mb-4">
                <div className="bg-green-50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-green-700">${savingsStats.total_savings.toFixed(2)}</p>
                  <p className="text-xs text-green-600 mt-0.5">Total saved</p>
                </div>
                <div className="bg-blue-50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-blue-700">{savingsStats.total_comparisons}</p>
                  <p className="text-xs text-blue-600 mt-0.5">Comparisons</p>
                </div>
                <div className="bg-amber-50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-amber-700">${savingsStats.average_savings.toFixed(2)}</p>
                  <p className="text-xs text-amber-600 mt-0.5">Avg. savings</p>
                </div>
                <div className="bg-purple-50 rounded-lg p-3 text-center">
                  <p className="text-2xl font-bold text-purple-700">${savingsStats.savings_this_month.toFixed(2)}</p>
                  <p className="text-xs text-purple-600 mt-0.5">This month</p>
                </div>
              </div>

              {/* Most used store */}
              {savingsStats.most_used_store && (
                <div className="flex items-center gap-2 p-3 bg-gray-50 rounded-lg mb-4">
                  <Store className="w-4 h-4 text-gray-500" />
                  <span className="text-sm text-gray-600">
                    Most savings at <span className="font-semibold text-gray-900">{savingsStats.most_used_store}</span>
                  </span>
                </div>
              )}

              {/* Recent comparisons */}
              {comparisonHistory.length > 0 && (
                <div>
                  <h3 className="text-sm font-medium text-gray-700 mb-2">Recent Comparisons</h3>
                  <div className="space-y-2">
                    {comparisonHistory.slice(0, 5).map((c) => (
                      <div key={c.id} className="flex items-center justify-between py-2 border-b border-gray-100 last:border-0">
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-medium truncate">
                            {c.cheapest_store_name ?? 'Unknown store'}
                          </p>
                          <p className="text-xs text-gray-500">
                            {c.item_count} items &middot; {new Date(c.created_at).toLocaleDateString()}
                          </p>
                        </div>
                        <div className="text-right flex-shrink-0 ml-3">
                          <p className="text-sm font-semibold text-gray-900">${c.cheapest_total.toFixed(2)}</p>
                          {c.savings > 0 && (
                            <p className="text-xs text-green-600 font-medium">Saved ${c.savings.toFixed(2)}</p>
                          )}
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>

        {/* Loyalty Cards Section */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold text-lg mb-2 flex items-center gap-2">
            <Crown className="w-5 h-5 text-amber-500" />
            Loyalty Cards
          </h2>
          <p className="text-sm text-gray-500 mb-4">
            Select which loyalty cards you have. Member-only prices will only be included in comparisons for chains where you hold a card.
          </p>
          <div className="space-y-3">
            {([
              { key: "countdown", logo: everydayRewardsLogo, program: "Everyday Rewards" },
              { key: "new_world", logo: nwClubcardLogo, program: "New World Clubcard" },
              { key: "paknsave", logo: paknsaveClubcardLogo, program: "PAK'nSAVE Sticky Club" },
            ] as const).map(({ key, logo, program }) => (
              <label
                key={key}
                htmlFor={`loyalty-${key}`}
                className="flex items-center gap-3 p-3 border rounded-lg cursor-pointer hover:bg-gray-50 transition-colors"
              >
                <Checkbox
                  id={`loyalty-${key}`}
                  checked={loyaltyCards[key] ?? true}
                  onCheckedChange={(checked) => setLoyaltyCard(key, checked === true)}
                />
                <img src={logo} alt={program} className="h-6 w-6 flex-shrink-0" style={{ objectFit: 'contain' }} />
                <span className="text-sm font-medium">{program}</span>
              </label>
            ))}
          </div>
        </div>

        {/* Saved Trolleys Section */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
            <ShoppingCart className="w-5 h-5" />
            Saved Trolleys
          </h2>

          {trolleysLoading ? (
            <div className="py-8 text-center text-gray-400">Loading...</div>
          ) : trolleys.length === 0 ? (
            <div className="py-8 text-center text-gray-400">
              <ShoppingCart className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p>No saved trolleys yet</p>
              <p className="text-sm mt-1">Save your trolley from the trolley page to see it here.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {trolleys.map((t) => (
                <div key={t.id} className="flex items-center justify-between border rounded-lg p-3 hover:bg-gray-50 transition-colors">
                  <div className="flex-1 min-w-0">
                    {renamingId === t.id ? (
                      <div className="flex gap-2">
                        <Input
                          value={renameValue}
                          onChange={(e) => setRenameValue(e.target.value)}
                          className="h-8 text-sm"
                          autoFocus
                          onKeyDown={(e) => e.key === "Enter" && handleRename(t.id)}
                        />
                        <Button size="sm" onClick={() => handleRename(t.id)}>Save</Button>
                        <Button size="sm" variant="outline" onClick={() => setRenamingId(null)}>Cancel</Button>
                      </div>
                    ) : (
                      <>
                        <p className="font-medium truncate">{t.name}</p>
                        <p className="text-xs text-gray-500">
                          {t.item_count} items &middot; Updated {new Date(t.updated_at).toLocaleDateString()}
                        </p>
                      </>
                    )}
                  </div>
                  {renamingId !== t.id && (
                    <div className="flex items-center gap-1 ml-3">
                      <Button size="sm" variant="ghost" onClick={() => handleLoadTrolley(t)} title="Load into trolley">
                        <ShoppingCart className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => { setRenamingId(t.id); setRenameValue(t.name); }} title="Rename">
                        <Pencil className="h-3.5 w-3.5" />
                      </Button>
                      <Button size="sm" variant="ghost" onClick={() => setDeleteTrolleyTarget({ id: t.id, name: t.name })} title="Delete" className="text-red-500 hover:text-red-700">
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Saved Recipes Section */}
        <div className="bg-white rounded-xl shadow-sm border p-6">
          <h2 className="font-semibold text-lg mb-4 flex items-center gap-2">
            <Bookmark className="w-5 h-5" />
            Saved Recipes
          </h2>

          {recipesLoading ? (
            <div className="py-8 text-center text-gray-400">Loading...</div>
          ) : savedRecipes.length === 0 ? (
            <div className="py-8 text-center text-gray-400">
              <UtensilsCrossed className="w-10 h-10 mx-auto mb-2 opacity-50" />
              <p>No saved recipes yet</p>
              <p className="text-sm mt-1">Save recipes from the recipes page to see them here.</p>
            </div>
          ) : (
            <div className="space-y-3">
              {savedRecipes.map((r) => (
                <div key={r.id} className="flex items-center justify-between border rounded-lg p-3 hover:bg-gray-50 transition-colors">
                  <Link to={`/recipes/${r.recipe_id}`} className="flex-1 min-w-0">
                    <p className="font-medium truncate">{r.title}</p>
                    <p className="text-xs text-gray-500">
                      {r.ingredient_count} ingredients &middot; Serves {r.servings}
                    </p>
                  </Link>
                  <div className="flex items-center gap-1 ml-3">
                    <Link to={`/recipes/${r.recipe_id}`}>
                      <Button size="sm" variant="ghost" title="View recipe">
                        <UtensilsCrossed className="h-3.5 w-3.5" />
                      </Button>
                    </Link>
                    <Button
                      size="sm"
                      variant="ghost"
                      onClick={() => setUnsaveRecipeTarget({ id: r.recipe_id, title: r.title })}
                      title="Remove"
                      className="text-red-500 hover:text-red-700"
                    >
                      <Trash2 className="h-3.5 w-3.5" />
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Actions */}
        <div className="space-y-3">
          <Button variant="outline" className="w-full" onClick={handleSignOut}>
            <LogOut className="w-4 h-4 mr-2" />
            Sign Out
          </Button>
          <Button variant="destructive" className="w-full" onClick={() => setDeleteAccountOpen(true)}>
            <Trash2 className="w-4 h-4 mr-2" />
            Delete Account
          </Button>
        </div>
      </div>

      <ConfirmDialog
        open={deleteAccountOpen}
        onOpenChange={setDeleteAccountOpen}
        title="Delete Account"
        description="Are you sure you want to delete your account? All saved trolleys, recipes, and preferences will be permanently removed. This cannot be undone."
        confirmLabel="Delete Account"
        variant="destructive"
        onConfirm={handleDeleteAccount}
      />

      <ConfirmDialog
        open={!!deleteTrolleyTarget}
        onOpenChange={(open) => !open && setDeleteTrolleyTarget(null)}
        title="Delete Trolley"
        description={`Delete "${deleteTrolleyTarget?.name}"? This cannot be undone.`}
        confirmLabel="Delete"
        variant="destructive"
        onConfirm={() => {
          if (deleteTrolleyTarget) handleDelete(deleteTrolleyTarget.id);
          setDeleteTrolleyTarget(null);
        }}
      />

      <ConfirmDialog
        open={!!unsaveRecipeTarget}
        onOpenChange={(open) => !open && setUnsaveRecipeTarget(null)}
        title="Remove Recipe"
        description={`Remove "${unsaveRecipeTarget?.title}" from your saved recipes?`}
        confirmLabel="Remove"
        variant="destructive"
        onConfirm={async () => {
          if (unsaveRecipeTarget) {
            const ok = await unsaveRecipe(unsaveRecipeTarget.id);
            if (ok) toast.success("Recipe removed");
          }
          setUnsaveRecipeTarget(null);
        }}
      />
    </div>
  );
};

export default Account;
