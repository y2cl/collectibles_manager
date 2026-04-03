import client from './client';

export interface ChangelogEntry {
  filename: string;
  date: string;
  version: string;
  title: string;
}

export interface ChangelogDetail extends ChangelogEntry {
  content: string;
}

export const changelogApi = {
  list: () =>
    client.get<ChangelogEntry[]>('/api/changelog').then((r) => r.data),

  get: (filename: string) =>
    client.get<ChangelogDetail>(`/api/changelog/${encodeURIComponent(filename)}`).then((r) => r.data),
};
