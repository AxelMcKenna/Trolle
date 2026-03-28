export interface Store {
  id: string;
  name: string;
  chain: string;
  lat: number;
  lon: number;
  address?: string | null;
  region?: string | null;
  distance_km?: number | null;
}

export interface StoreListResponse {
  items: Store[];
}

export interface Location {
  lat: number;
  lon: number;
}

export interface Price {
  store_id: string;
  store_name: string;
  chain: string;
  price_nzd: number;
  promo_price_nzd?: number | null;
  promo_text?: string | null;
  promo_ends_at?: string | null;
  is_member_only?: boolean;
  unit_price?: number | null;
  unit_measure?: string | null;
  distance_km?: number | null;
}

export interface Product {
  id: string;
  name: string;
  brand?: string | null;
  category?: string | null;
  chain: string;
  size?: string | null;
  department?: string | null;
  subcategory?: string | null;
  image_url?: string | null;
  product_url?: string | null;
  price: Price;
  last_updated: string;
}

export interface ProductListResponse {
  items: Product[];
  total: number;
}

export type Category =
  | "Fruit & Vegetables"
  | "Meat & Seafood"
  | "Chilled, Dairy & Eggs"
  | "Bakery"
  | "Pantry"
  | "Frozen"
  | "Drinks"
  | "Snacks & Confectionery"
  | "Health & Beauty"
  | "Household"
  | "Baby & Child"
  | "Pet"
  | "Beer, Wine & Cider";

export enum SortOption {
  DISCOUNT = "discount",
  UNIT_PRICE = "unit_price",
  CHEAPEST = "total_price",
  DISTANCE = "distance",
  NEWEST = "newest"
}

export type ChainType = "countdown" | "new_world" | "paknsave";

// Trolley types
export interface TrolleyItem {
  product_id: string;
  name: string;
  brand?: string | null;
  size?: string | null;
  chain: string;
  image_url?: string | null;
  department?: string | null;
  quantity: number;
}

export interface TrolleyStoreItem {
  source_product_id: string;
  source_product_name: string;
  quantity: number;
  available: boolean;
  matched_product_id?: string | null;
  matched_product_name?: string | null;
  price?: number | null;
  line_total?: number | null;
  is_member_only?: boolean;
}

export interface TrolleyStoreBreakdown {
  store_id: string;
  store_name: string;
  chain: string;
  distance_km: number;
  estimated_total: number;
  items_available: number;
  items_total: number;
  is_complete: boolean;
  items: TrolleyStoreItem[];
}

export interface TrolleySummary {
  total_items: number;
  total_stores: number;
  complete_stores: number;
}

export interface TrolleyCompareResponse {
  stores: TrolleyStoreBreakdown[];
  items: TrolleyItem[];
  summary: TrolleySummary;
}

export interface SuggestionProduct {
  product_id: string;
  name: string;
  brand?: string | null;
  size?: string | null;
  image_url?: string | null;
  price_nzd: number;
  promo_price_nzd?: number | null;
  similarity: number;
}

export interface SuggestionItem {
  source_product_id: string;
  suggestions: SuggestionProduct[];
}

export interface TrolleySuggestionsResponse {
  items: SuggestionItem[];
}

// Recipe types
export interface RecipeIngredient {
  id: string;
  description: string;
  quantity?: number | null;
  unit?: string | null;
  display_name: string;
  optional: boolean;
}

export interface Recipe {
  id: string;
  title: string;
  description?: string | null;
  servings: number;
  image_url?: string | null;
  source_url?: string | null;
  is_public: boolean;
  is_seeded: boolean;
  created_by?: string | null;
  ingredients: RecipeIngredient[];
}

export interface RecipeListItem {
  id: string;
  title: string;
  description?: string | null;
  servings: number;
  image_url?: string | null;
  ingredient_count: number;
}

export interface RecipeListResponse {
  items: RecipeListItem[];
  total: number;
}

export interface RecipeIngredientMatch {
  ingredient_id: string;
  ingredient_description: string;
  display_name: string;
  optional: boolean;
  available: boolean;
  matched_product_id?: string | null;
  matched_product_name?: string | null;
  matched_product_image?: string | null;
  price?: number | null;
  quantity?: number | null;
  unit?: string | null;
}

export interface RecipeStoreBreakdown {
  store_id: string;
  store_name: string;
  chain: string;
  distance_km: number;
  estimated_total: number;
  items_available: number;
  items_total: number;
  is_complete: boolean;
  ingredients: RecipeIngredientMatch[];
}

export interface RecipeCostResponse {
  recipe: RecipeListItem;
  stores: RecipeStoreBreakdown[];
  summary: {
    total_ingredients: number;
    total_stores: number;
    complete_stores: number;
  };
}

export interface ProductFilters {
  query?: string;
  category?: string;
  chains?: ChainType[];
  promo_only?: boolean;
  member_prices?: boolean;
  unique_products?: boolean;
  price_min?: number;
  price_max?: number;
  sort?: SortOption;
  store_ids?: string[];
  lat?: number;
  lon?: number;
  radius_km?: number;
  limit?: number;
  offset?: number;
}
