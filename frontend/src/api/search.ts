import client from './client';
import type { SearchResponse } from '../types/card';

export interface MtgSearchParams {
  name: string;
  set_hint?: string;
  collector_number?: string;
  force_refresh?: boolean;
}

export interface PokemonSearchParams {
  name: string;
  set_hint?: string;
  number?: string;
  force_refresh?: boolean;
}

export interface BaseballSearchParams {
  player_name: string;
  year?: string;
  team?: string;
  set_name?: string;
  card_number?: string;
  force_refresh?: boolean;
}

export const searchApi = {
  mtg: (params: MtgSearchParams) =>
    client.get<SearchResponse>('/api/search/mtg', { params }).then((r) => r.data),

  pokemon: (params: PokemonSearchParams) =>
    client.get<SearchResponse>('/api/search/pokemon', { params }).then((r) => r.data),

  baseball: (params: BaseballSearchParams) =>
    client.get<SearchResponse>('/api/search/baseball', { params }).then((r) => r.data),
};
