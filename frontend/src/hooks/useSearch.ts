import { useQuery, useQueryClient } from '@tanstack/react-query';
import { searchApi, MtgSearchParams, PokemonSearchParams, BaseballSearchParams } from '../api/search';

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

export function useBaseballSearch(params: BaseballSearchParams, enabled: boolean) {
  return useQuery({
    queryKey: ['search', 'baseball', { ...params, force_refresh: undefined }],
    queryFn: () => searchApi.baseball(params),
    enabled: enabled && !!params.player_name,
    staleTime: 5 * 60 * 1000,
  });
}

/**
 * Returns a function that re-fetches any search query with force_refresh=true,
 * then invalidates the cached result so the fresh data is shown.
 */
export function useForceRefreshSearch() {
  const qc = useQueryClient();

  return async (game: 'mtg' | 'pokemon' | 'baseball', params: MtgSearchParams | PokemonSearchParams | BaseballSearchParams) => {
    const refreshed = await (game === 'mtg'
      ? searchApi.mtg({ ...(params as MtgSearchParams), force_refresh: true })
      : game === 'pokemon'
      ? searchApi.pokemon({ ...(params as PokemonSearchParams), force_refresh: true })
      : searchApi.baseball({ ...(params as BaseballSearchParams), force_refresh: true })
    );

    // Write the fresh result directly into the cache so the UI updates immediately
    qc.setQueryData(
      ['search', game, { ...params, force_refresh: undefined }],
      refreshed,
    );

    return refreshed;
  };
}
