export interface UpcResult {
  name: string;
  manufacturer: string;
  description: string;
  image_url: string;
  price: number | null;
  upc: string;
  category: string;
}

export interface CardResult {
  game: string;
  sport?: string;            // for Sports Cards
  name: string;
  set_name: string;          // also Line/Series for Collectibles
  set_code: string;
  card_number: string;
  year: string;
  image_url: string;
  image_url_back?: string;   // back face for double-faced cards
  link: string;
  manufacturer?: string;     // for Collectibles
  upc?: string;              // for Collectibles
  price_usd: number;
  price_usd_foil: number;
  price_usd_etched: number;
  price_low?: number;
  price_mid?: number;
  price_market?: number;
  // Pokémon: Record<variant, {low, mid, market}>  |  Coins: Record<grade, price_number>
  prices_map?: Record<string, { low: number; mid: number; market: number } | number>;
  has_nonfoil: boolean;
  has_foil: boolean;
  source: string;
  artist: string;
  // Coin-specific (auto-populated from NGC)
  denomination?: string;    // e.g. "$1.00", "$0.25"
  country?: string;         // e.g. "USA"
  coin_or_bill?: string;    // "Coin" | "Bill"
  silver_amount?: number;   // decimal, e.g. 0.90 = 90% silver
  mint_mark?: string;       // e.g. "S", "D", "CC"
  // Coin type selector (MS / MS PL / MS DPL etc.)
  coin_type_options?: string[];
  coin_types_data?: Record<string, {
    prices_map?: Record<string, number>;
    price_usd?: number;
    price_low?: number | null;
    price_market?: number | null;
    link?: string;
    image_url?: string;
    image_url_back?: string;
  }>;
  // Comics-specific
  issue_number?: string;
  story_arc?: string;
  writer?: string;
  comic_artist?: string;
  publisher?: string;
  is_key_issue?: boolean;
  cgc_cert_number?: string;
}

export interface SearchResponse {
  cards: CardResult[];
  total: number;
  shown: number;
  source: string;
}

export interface CollectionCard {
  id: number;
  owner_id: number;
  profile_id: string;
  game: string;
  sport?: string;            // for Sports Cards
  name: string;
  set_name: string;          // also Line/Series for Collectibles
  set_code: string;
  card_number: string;
  year: string;
  link: string;
  image_url: string;
  manufacturer?: string;     // for Collectibles
  upc?: string;              // for Collectibles
  grading_company?: string;
  grade?: string;
  serial_number?: string;    // grading cert number
  print_run?: string;        // serialized print run, e.g. 23/99
  rc?: boolean;
  price_low?: number;
  price_mid?: number;
  price_market?: number;
  price_usd: number;
  price_usd_foil: number;
  price_usd_etched: number;
  // Coin-specific fields
  denomination?: string;    // face value, e.g. "$1.00"
  country?: string;         // e.g. "USA"
  coin_or_bill?: string;    // "Coin" | "Bill"
  silver_amount?: number;   // decimal, e.g. 0.90 = 90% silver
  mint_mark?: string;       // e.g. "S", "D", "CC"
  // Comics-specific fields
  issue_number?: string;
  story_arc?: string;
  writer?: string;
  publisher?: string;
  is_key_issue?: boolean;
  cgc_cert_number?: string;
  quantity: number;
  variant: string;
  paid: number;
  signed: string;
  altered: string;
  notes: string;
  timestamp: string;
}

export interface CollectionStats {
  total_cards: number;
  unique_cards: number;
  unique_sets: number;
  total_value: number;
}

export interface CollectionResponse {
  cards: CollectionCard[];
  stats: CollectionStats;
}

export interface WatchlistItem {
  id: number;
  owner_id: number;
  profile_id: string;
  game: string;
  sport?: string;   // for Sports Cards: "baseball" | "football" | "basketball" | "hockey" | "soccer" | "other"
  name: string;
  set_name: string;
  set_code: string;
  card_number: string;
  year: string;
  link: string;
  image_url: string;
  price_usd: number;
  price_usd_foil: number;
  price_usd_etched: number;
  price_low?: number;
  price_mid?: number;
  price_market?: number;
  quantity: number;
  variant: string;
  target_price: number;
  signed: string;
  altered: string;
  notes: string;
  timestamp: string;
}

export interface CardAddRequest {
  owner_id: string;
  profile_id: string;
  game: string;
  sport?: string;
  name: string;
  manufacturer?: string;
  upc?: string;
  set_name?: string;
  set_code?: string;
  card_number?: string;
  year?: string;
  link?: string;
  image_url?: string;
  price_usd?: number;
  price_usd_foil?: number;
  price_usd_etched?: number;
  price_low?: number;
  price_mid?: number;
  price_market?: number;
  quantity?: number;
  variant?: string;
  paid?: number;
  notes?: string;
  signed?: string;
  altered?: string;
  grading_company?: string;
  grade?: string;
  serial_number?: string;
  print_run?: string;
  rc?: boolean;
  // Coin-specific
  denomination?: string;
  country?: string;
  coin_or_bill?: string;
  silver_amount?: number;
  mint_mark?: string;
  // Comics-specific
  issue_number?: string;
  story_arc?: string;
  writer?: string;
  comic_artist?: string;
  publisher?: string;
  is_key_issue?: boolean;
  cgc_cert_number?: string;
}
