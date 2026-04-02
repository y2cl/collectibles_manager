import client from './client';
import type { SetsResponse } from '../types/settings';

export interface MtgSyncResult {
  total: number;
  added: number;
  updated: number;
  unchanged: number;
  csv_path: string;
}

export const setsApi = {
  list: (params: { game?: string; search?: string; set_type?: string; game_type?: string; year?: string; limit?: number; offset?: number }) =>
    client.get<SetsResponse>('/api/sets', { params }).then((r) => r.data),

  ownedCount: (set_code: string, owner_id: string, profile_id = 'default') =>
    client.get<{ set_code: string; owned_count: number }>(`/api/sets/${set_code}/owned-count`, {
      params: { owner_id, profile_id },
    }).then((r) => r.data),

  /** Fetch all MTG sets from Scryfall and save to mtgsets.csv. Can take 10-30s. */
  syncMtgSets: () =>
    client.post<MtgSyncResult>('/api/sets/sync/mtg').then((r) => r.data),

  /** Cached card counts per game per set code. { mtg: { lea: 295 }, pokemon: { base1: 102 } } */
  cacheSummary: () =>
    client.get<{ mtg: Record<string, number>; pokemon: Record<string, number> }>('/api/sets/cache-summary').then((r) => r.data),

  /** Fetch all Pokémon sets from the Pokémon TCG API and save to pokemonsets.csv. */
  syncPokemonSets: () =>
    client.post<MtgSyncResult>('/api/sets/sync/pokemon').then((r) => r.data),

  /** Download all cards in a set into the local cache. Pass game='pokemon' for Pokémon sets. */
  cacheSetCards: (set_code: string, game: 'mtg' | 'pokemon' = 'mtg') =>
    client.post<CacheCardsResult>(`/api/sets/${set_code}/cache-cards`, null, { params: { game } }).then((r) => r.data),
};

export interface CacheCardsResult {
  set_code: string;
  set_name: string;
  total_fetched: number;
  stored: number;
  skipped: number;
}
