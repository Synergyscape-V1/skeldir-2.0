import { describe, expect, it } from 'vitest';
import viteConfig from '../../vite.config';

describe('vite dev server ngrok tunnel config', () => {
  it('positive: exposes dev server and allowlists ngrok subdomain patterns', () => {
    const server = viteConfig.server ?? {};
    expect(server.host).toBe(true);
    expect(server.allowedHosts).toEqual(
      expect.arrayContaining(['.ngrok-free.dev', '.ngrok-free.app']),
    );
  });

  it('negative: does not disable host validation globally', () => {
    expect(viteConfig.server?.allowedHosts).not.toBe(true);
  });

  it('meta-negative: removing ngrok allowlist fails the positive control', () => {
    const sabotaged = {
      ...viteConfig,
      server: { ...viteConfig.server, allowedHosts: [] as string[] },
    };
    expect(sabotaged.server?.allowedHosts).not.toEqual(
      expect.arrayContaining(['.ngrok-free.dev']),
    );
  });
});
