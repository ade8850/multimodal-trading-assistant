import { defineConfig } from 'astro/config';
import preact from '@astrojs/preact';
import tailwind from '@astrojs/tailwind';

// https://astro.build/config
export default defineConfig({
  integrations: [
    // Enable Preact for interactive components
    preact(),
    // Enable Tailwind
    tailwind()
  ],
  // Configure dev server
  server: {
    port: 3000,
    host: true
  },
  // Set base path for deployment in subdirectory
  base: '/',
  // Set output directory
  outDir: './dist',
  // Set trailingSlash behavior
  trailingSlash: 'always'
});