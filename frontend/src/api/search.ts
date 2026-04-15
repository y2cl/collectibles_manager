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

export interface SportsSearchParams {
  player_name: string;
  sport?: string;
  year?: string;
  team?: string;
  set_name?: string;
  card_number?: string;
  force_refresh?: boolean;
}

export interface CoinSearchParams {
  name: string;
  year?: string;
  mint_mark?: string;
  force_refresh?: boolean;
}

export interface ComicSearchParams {
  name: string;
  force_refresh?: boolean;
}

export interface ComicIssueSearchParams {
  volume_id: string;
  issue_number?: string;
}

export interface ComicFindIssueParams {
  name: string;
  issue_number: string;
}

export const searchApi = {
  mtg: (params: MtgSearchParams) =>
    client.get<SearchResponse>('/api/search/mtg', { params }).then((r) => r.data),

  pokemon: (params: PokemonSearchParams) =>
    client.get<SearchResponse>('/api/search/pokemon', { params }).then((r) => r.data),

  sports: (params: SportsSearchParams) =>
    client.get<SearchResponse>('/api/search/sports', { params }).then((r) => r.data),

  coins: (params: CoinSearchParams) =>
    client.get<SearchResponse>('/api/search/coins', { params }).then((r) => r.data),

  comics: (params: ComicSearchParams) =>
    client.get<SearchResponse>('/api/search/comics', { params }).then((r) => r.data),

  comicIssues: (params: ComicIssueSearchParams) =>
    client.get<SearchResponse>('/api/search/comics/issues', { params }).then((r) => r.data),

  comicFindIssue: (params: ComicFindIssueParams) =>
    client.get<SearchResponse>('/api/search/comics/find-issue', { params }).then((r) => r.data),

  /** @deprecated use sports() */
  baseball: (params: SportsSearchParams) =>
    client.get<SearchResponse>('/api/search/sports', { params: { ...params, sport: 'baseball' } }).then((r) => r.data),
};
