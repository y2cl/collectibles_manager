export interface Profile {
  id: number;
  owner_id: number;
  profile_id: string;
  created_at: string;
}

export interface Owner {
  id: number;
  owner_id: string;
  label: string;
  created_at: string;
  profiles: Profile[];
}

export interface OwnerPreferences {
  default_owner_id: string | null;
  active_profiles: Record<string, string>; // { owner_id_slug: profile_id }
}
