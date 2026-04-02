export interface CardResult {
  game: string;
  name: string;
  set_name: string;
  set_code: string;
  card_number: string;
  year: string;
  image_url: string;
  image_url_back?: string;   // back face for double-faced cards
  link: string;
  price_usd: number;
  price_usd_foil: number;
  price_usd_etched: number;
  price_low?: number;
  price_mid?: number;
  price_market?: number;
  prices_map?: Record<string, { low: number; mid: number; market: number }>;
  has_nonfoil: boolean;
  has_foil: boolean;
  source: string;
  artist: string;
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
  name: string;
  set_name: string;
  set_code: string;
  card_number: string;
  year: string;
  link: string;
  image_url: string;
  price_low?: number;
  price_mid?: number;
  price_market?: number;
  price_usd: number;
  price_usd_foil: number;
  price_usd_etched: number;
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
  name: string;
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
}
