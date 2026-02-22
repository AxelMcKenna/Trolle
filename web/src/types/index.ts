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

export interface ProductFilters {
  query?: string;
  category?: string;
  chains?: ChainType[];
  promo_only?: boolean;
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
