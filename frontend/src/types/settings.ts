export interface ApiSourceConfig {
  source_id: string;
  name: string;
  game: string;
  enabled: boolean;
  free: boolean;
  description: string;
}

export interface AppSettings {
  duplicate_strategy: string;
  paid_merge_strategy: string;
  auto_backup_enabled: boolean;
  backup_retention: number;
  api_source_config: Record<string, unknown>;
}

export interface SetEntry {
  game: string;
  name: string;
  code: string;
  year: string;
  released_at: string;   // full ISO date e.g. "2024-01-19" — used for precise date sorting
  set_type: string;
  game_type: string;
  card_count: string;
  icon_url: string;
  scryfall_uri: string;
}

export interface SetsResponse {
  sets: SetEntry[];
  total: number;
}

export interface ImportCsvResponse {
  imported: number;
  ambiguous: number;
  ambiguities: Array<{
    id: number;
    row_data: Record<string, unknown>;
    candidates: unknown[];
  }>;
}
