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

  /** Aggregate Sports Cards from the collection into sets with insert sub-rows. */
  sportsSummary: (owner_id: string, profile_id = 'default', sport?: string) =>
    client.get<{ sets: SportsSetRow[] }>('/api/sets/sports-summary', {
      params: { owner_id, profile_id, ...(sport && sport !== 'all' ? { sport } : {}) },
    }).then((r) => r.data),

  /** List user-defined sports card set catalog entries. */
  sportsCatalog: (owner_id: string, profile_id = 'default', sport?: string) =>
    client.get<{ sets: SportsCatalogEntry[] }>('/api/sets/sports-catalog', {
      params: { owner_id, profile_id, ...(sport && sport !== 'all' ? { sport } : {}) },
    }).then((r) => r.data),

  /** Create a new sports card set catalog entry. */
  createSportsSet: (payload: SportsCatalogCreate) =>
    client.post<SportsCatalogEntry>('/api/sets/sports-catalog', payload).then((r) => r.data),

  /** Update a sports card set catalog entry. */
  updateSportsSet: (id: number, payload: SportsCatalogUpdate) =>
    client.patch<SportsCatalogEntry>(`/api/sets/sports-catalog/${id}`, payload).then((r) => r.data),

  /** Delete a sports card set catalog entry. */
  deleteSportsSet: (id: number) =>
    client.delete(`/api/sets/sports-catalog/${id}`).then((r) => r.data),
};

export interface SportsInsertRow {
  insert: string;
  year: string;
  owned: number;
  paid: number;
  value: number;
  card_count: number | null;
  link: string;
  notes: string;
  catalog_id: number | null;
}

export interface SportsSetRow {
  set_name: string;
  year: string;
  owned: number;
  paid: number;
  value: number;
  card_count: number | null;
  link: string;
  notes: string;
  catalog_id: number | null;
  inserts: SportsInsertRow[];
}

export interface SportsCatalogEntry {
  id: number;
  sport: string | null;
  set_name: string;
  insert_name: string;
  year: string;
  card_count: number | null;
  link: string;
  notes: string;
}

export interface SportsCatalogCreate {
  owner_id: string;
  profile_id: string;
  sport?: string;
  set_name: string;
  insert_name?: string;
  year?: string;
  card_count?: number | null;
  link?: string;
  notes?: string;
}

export interface SportsCatalogUpdate {
  sport?: string;
  set_name?: string;
  insert_name?: string;
  year?: string;
  card_count?: number | null;
  link?: string;
  notes?: string;
}

export interface CacheCardsResult {
  set_code: string;
  set_name: string;
  total_fetched: number;
  stored: number;
  skipped: number;
}
