/**
 * D3.7: Storybook main configuration
 * Framework: React + Vite
 * Addons: a11y (quality gate), docs, chromatic, vitest
 *
 * Cursor workflow: `npx storybook@latest init --type react --yes`
 * Then customize this file. Stories live in src/stories/*.stories.tsx.
 */
import type { StorybookConfig } from '@storybook/react-vite'

const config: StorybookConfig = {
  stories: ['../src/**/*.stories.@(js|jsx|mjs|ts|tsx)'],
  addons: [
    '@storybook/addon-a11y',
    '@storybook/addon-docs',
    '@chromatic-com/storybook',
    '@storybook/addon-vitest',
  ],
  framework: '@storybook/react-vite',
}

export default config
