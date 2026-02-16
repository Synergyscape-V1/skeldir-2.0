import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import path from 'path';

/**
 * Vite Library Mode Configuration - Design System Build
 *
 * This configuration enables hermetic build isolation for the design system.
 * It targets ONLY the D0/D1/D2 layers, completely ignoring application concerns.
 *
 * Critical Constraint: This build MUST succeed even if src/api/* contains errors.
 *
 * Build Command: npm run build:design-system
 * Output: dist/design-system.{js,es.js,css}
 */

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
      '@assets': path.resolve(__dirname, './src/assets'),
      '@shared': path.resolve(__dirname, './src/shared'),
    },
  },
  build: {
    // Library mode configuration
    lib: {
      entry: path.resolve(__dirname, 'src/design-system.ts'),
      name: 'SkelDirDesignSystem',
      formats: ['es', 'umd'],
      fileName: (format) => `design-system.${format}.js`,
    },
    rollupOptions: {
      // Externalize dependencies to avoid bundling them
      external: ['react', 'react-dom', 'react/jsx-runtime'],
      output: {
        // Global variables to use in UMD build for externalized deps
        globals: {
          react: 'React',
          'react-dom': 'ReactDOM',
          'react/jsx-runtime': 'jsxRuntime',
        },
        // Preserve module structure for better tree-shaking
        preserveModules: false,
      },
    },
    // Ensure CSS is extracted
    cssCodeSplit: false,
    // Output directory
    outDir: 'dist-design-system',
    // Empty the output directory before build
    emptyOutDir: true,
    // Source maps for debugging
    sourcemap: true,
  },
});
