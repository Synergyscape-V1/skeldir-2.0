/**
 * D3.7: Storybook preview configuration
 * - Imports D0 tokens (index.css + brand colors) so all stories render with Skeldir theme
 * - Configures dark mode toggle via toolbar
 * - Enables a11y addon checks
 *
 * Cursor workflow: Run `npm run storybook` to validate stories render with correct tokens.
 * Invariant: All shadcn/Tremor components must inherit D0 tokens from CSS variables.
 */
import type { Preview } from '@storybook/react-vite'

// Import D0 token stylesheets so stories render with the Skeldir theme
import '../src/index.css'

const preview: Preview = {
  parameters: {
    controls: {
      matchers: {
        color: /(background|color)$/i,
        date: /Date$/i,
      },
    },
    a11y: {
      // 'error' - fail tests on a11y violations (D3.7 quality gate: 0 critical)
      test: 'error',
    },
    backgrounds: {
      disable: true, // We use CSS variables for theming, not Storybook backgrounds
    },
  },
  globalTypes: {
    theme: {
      name: 'Theme',
      description: 'Toggle light/dark mode',
      toolbar: {
        icon: 'paintbrush',
        items: [
          { value: 'light', title: 'Light', icon: 'sun' },
          { value: 'dark', title: 'Dark', icon: 'moon' },
        ],
        dynamicTitle: true,
      },
    },
  },
  initialGlobals: {
    theme: 'light',
  },
  decorators: [
    (Story, context) => {
      const theme = context.globals.theme || 'light'
      // Apply dark class to the root element for Tailwind dark mode
      document.documentElement.classList.toggle('dark', theme === 'dark')
      return Story()
    },
  ],
}

export default preview
