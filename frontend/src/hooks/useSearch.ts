import { useQuery, useQueryClient } from '@tanstack/react-query';
import { searchApi, MtgSearchParams, PokemonSearchParams, SportsSearchParams, CoinSearchParams, ComicSearchParams, ComicIssueSearchParams, ComicFindIssueParams } from '../api/search';

export function useMtgSearch(params: MtgSearchParams, enabled: boolean) {
  return useQuery({
    queryKey: ['search', 'mtg', { ...params, force_refresh: undefined }],
    queryFn: () => searchApi.mtg(params),
    enabled: enabled && !!params.name,
    staleTime: 5 * 60 * 1000,
  });
}

export function usePokemonSearch(params: PokemonSearchParams, enabled: boolean) {
  return useQuery({
    queryKey: ['search', 'pokemon', { ...params, force_refresh: undefined }],
    queryFn: () => searchApi.pokemon(params),
    enabled: enabled && !!params.name,
    staleTime: 5 * 60 * 1000,
  });
}

export function useSportsSearch(params: SportsSearchParams, enabled: boolean) {
  return useQuery({
    queryKey: ['search', 'sports', { ...params, force_refresh: undefined }],
    queryFn: () => searchApi.sports(params),
    enabled: enabled && !!params.player_name,
    staleTime: 5 * 60 * 1000,
  });
}

/** @deprecated use useSportsSearch */
export function useBaseballSearch(params: SportsSearchParams, enabled: boolean) {
  return useSportsSearch(params, enabled);
}

export function useCoinSearch(params: CoinSearchParams, enabled: boolean) {
  return useQuery({
    queryKey: ['search', 'coins', { ...params, force_refresh: undefined }],
    queryFn: () => searchApi.coins(params),
    enabled: enabled && !!params.name,
    staleTime: 5 * 60 * 1000,
  });
}

export function useComicSearch(params: ComicSearchParams, enabled: boolean) {
  return useQuery({
    queryKey: ['search', 'comics', { ...params, force_refresh: undefined }],
    queryFn: () => searchApi.comics(params),
    enabled: enabled && !!params.name,
    staleTime: 5 * 60 * 1000,
  });
}

export function useComicIssueSearch(params: ComicIssueSearchParams, enabled: boolean) {
  return useQuery({
    queryKey: ['search', 'comicIssues', params],
    queryFn: () => searchApi.comicIssues(params),
    enabled: enabled && !!params.volume_id,
    staleTime: 5 * 60 * 1000,
  });
}

export function useComicFindIssue(params: ComicFindIssueParams, enabled: boolean) {
  return useQuery({
    queryKey: ['search', 'comicFindIssue', params],
    queryFn: () => searchApi.comicFindIssue(params),
    enabled: enabled && !!params.name && !!params.issue_number,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Returns a function that re-fetches any search query with force_refresh=true,
 * then invalidates the cached result so the fresh data is shown.
 */
export function useForceRefreshSearch() {
  const qc = useQueryClient();

  return async (game: 'mtg' | 'pokemon' | 'sports' | 'coins' | 'comics', params: MtgSearchParams | PokemonSearchParams | SportsSearchParams | CoinSearchParams | ComicSearchParams) => {
    const refreshed = await (game === 'mtg'
      ? searchApi.mtg({ ...(params as MtgSearchParams), force_refresh: true })
      : game === 'pokemon'
      ? searchApi.pokemon({ ...(params as PokemonSearchParams), force_refresh: true })
      : game === 'coins'
      ? searchApi.coins({ ...(params as CoinSearchParams), force_refresh: true })
      : game === 'comics'
      ? searchApi.comics({ ...(params as ComicSearchParams), force_refresh: true })
      : searchApi.sports({ ...(params as SportsSearchParams), force_refresh: true })
    );

    // Write the fresh result directly into the cache so the UI updates immediately
    qc.setQueryData(
      ['search', game, { ...params, force_refresh: undefined }],
      refreshed,
    );

    return refreshed;
  };
}
