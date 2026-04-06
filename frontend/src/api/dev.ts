import client from './client';

export interface RebuildResult {
  success: boolean;
  stdout: string;
  stderr: string;
  exit_code: number;
}

export const devApi = {
  rebuild: () =>
    client.post<RebuildResult>('/api/dev/rebuild').then((r) => r.data),

  restart: () =>
    client.post<{ restarting: boolean }>('/api/dev/restart').then((r) => r.data),

  /** Poll /api/health until it responds OK. Returns true when back up. */
  waitForServer: (maxWaitMs = 30_000, intervalMs = 500): Promise<boolean> => {
    return new Promise((resolve) => {
      const start = Date.now();
      const poll = () => {
        client.get('/api/health', { timeout: 1500 })
          .then(() => resolve(true))
          .catch(() => {
            if (Date.now() - start >= maxWaitMs) {
              resolve(false);
            } else {
              setTimeout(poll, intervalMs);
            }
          });
      };
      // Give the process time to die and the supervisor time to spawn a new worker
      setTimeout(poll, 2000);
    });
  },
};
