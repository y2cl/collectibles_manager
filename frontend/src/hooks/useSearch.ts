import { useQuery, useQueryClient } from '@tanstack/react-query';
import { searchApi, MtgSearchParams, PokemonSearchParams, SportsSearchParams } from '../api/search';

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

/**
 * Returns a function that re-fetches any search query with force_refresh=true,
 * then invalidates the cached result so the fresh data is shown.
 */
export function useForceRefreshSearch() {
  const qc = useQueryClient();

  return async (game: 'mtg' | 'pokemon' | 'sports', params: MtgSearchParams | PokemonSearchParams | SportsSearchParams) => {
    const refreshed = await (game === 'mtg'
      ? searchApi.mtg({ ...(params as MtgSearchParams), force_refresh: true })
      : game === 'pokemon'
      ? searchApi.pokemon({ ...(params as PokemonSearchParams), force_refresh: true })
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
