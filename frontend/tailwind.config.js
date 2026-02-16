/**
 * D3.7 CHOKE-POINT FILE: tailwind.config.js
 *
 * Cursor workflow:
 *   Contains shadcn color mappings (hsl(var(--xxx))) AND Tremor semantic theme
 *   keys (tremor-brand, tremor-background, tremor-content, tremor-ring).
 *
 * Invariants:
 *   - tremor-brand → hsl(var(--primary))   [D0 primary-500]
 *   - tremor-background → hsl(var(--background))   [D0 background]
 *   - tremor-content → hsl(var(--foreground))   [D0 foreground]
 *   - tremor-ring → hsl(var(--primary))   [D0 primary-500]
 *   - content array must include Tremor node_modules for tree-shaking
 *   - darkMode must be 'class' (not array)
 *
 * Re-validation: `npm run type-check` + `npm run storybook`
 *   Tremor story must render charts with correct colors in both themes.
 *
 * @type {import('tailwindcss').Config}
 */
export default {
  darkMode: 'class',
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
    // D3.7: Include Tremor component classes for tree-shaking
    "./node_modules/@tremor/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
  	extend: {
  		// D3.1: Explicit breakpoint overrides for validation targets
  		screens: {
  			'2xl': '1440px', // Override default 1536px → 1440px per D3.1 spec
  		},
  		colors: {
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar))',
  				foreground: 'hsl(var(--sidebar-foreground))',
  				primary: 'hsl(var(--sidebar-primary))',
  				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  				accent: 'hsl(var(--sidebar-accent))',
  				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  				border: 'hsl(var(--sidebar-border))',
  				ring: 'hsl(var(--sidebar-ring))'
  			},
  			verified: {
  				DEFAULT: 'hsl(var(--verified))',
  				foreground: 'hsl(var(--verified-foreground))'
  			},
  			unverified: {
  				DEFAULT: 'hsl(var(--unverified))',
  				foreground: 'hsl(var(--unverified-foreground))'
  			},
  			'brand-alice': 'hsl(var(--brand-alice) / <alpha-value>)',
  			'brand-jordy': 'hsl(var(--brand-jordy) / <alpha-value>)',
  			'brand-tufts': 'hsl(var(--brand-tufts) / <alpha-value>)',
  			'brand-cool-black': 'hsl(var(--brand-cool-black) / <alpha-value>)',
  			'brand-success': 'hsl(var(--brand-success) / <alpha-value>)',
  			'brand-warning': 'hsl(var(--brand-warning) / <alpha-value>)',
  			'brand-error': 'hsl(var(--brand-error) / <alpha-value>)',
  			'brand-critical': 'hsl(var(--brand-critical) / <alpha-value>)',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			},
  			/* D3.7: Tremor semantic theme keys → D0 tokens (exact mapping per spec) */
  			'tremor-brand': {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))',
  			},
  			'tremor-background': {
  				DEFAULT: 'hsl(var(--background))',
  				foreground: 'hsl(var(--foreground))',
  			},
  			'tremor-content': {
  				DEFAULT: 'hsl(var(--foreground))',
  				muted: 'hsl(var(--muted-foreground))',
  			},
  			'tremor-ring': {
  				DEFAULT: 'hsl(var(--primary))',
  			}
  		},
  		borderColor: {
  			DEFAULT: 'hsl(var(--border))'
  		},
  		borderRadius: {
  			lg: 'var(--radius)',
  			md: 'calc(var(--radius) - 2px)',
  			sm: 'calc(var(--radius) - 4px)'
  		},
  		fontFamily: {
  			sans: [
  				'var(--font-sans)',
  				'system-ui',
  				'sans-serif'
  			],
  			serif: [
  				'var(--font-serif)',
  				'Georgia',
  				'serif'
  			],
  			mono: [
  				'var(--font-mono)',
  				'Menlo',
  				'monospace'
  			]
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
}

