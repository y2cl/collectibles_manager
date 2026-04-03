import client from './client';
import type { UpcResult } from '../types/card';

export interface ImageResult {
  url: string;
  thumbnail: string;
  title: string;
  source: string;
}

export interface ImageSearchResponse {
  results: ImageResult[];
  query: string;
  configured: boolean;
}

export interface PsaCertResult {
  player: string;
  year: string;
  brand: string;
  set_name: string;
  card_number: string;
  grade: string;
  subject: string;
}

export const lookupApi = {
  upc: (code: string) =>
    client.get<UpcResult>('/api/lookup/upc', { params: { code } }).then((r) => r.data),

  images: (q: string, num = 10) =>
    client.get<ImageSearchResponse>('/api/lookup/images', { params: { q, num } }).then((r) => r.data),

  psaCert: (certNumber: string) =>
    client.get<PsaCertResult>(`/api/lookup/psa/${encodeURIComponent(certNumber)}`).then((r) => r.data),
};
