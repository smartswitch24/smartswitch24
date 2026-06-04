import { defineConfig } from 'astro/config';
import sitemap from '@astrojs/sitemap';

export default defineConfig({
  site: 'https://smartswitch24.de',
  output: 'static',
  integrations: [
    sitemap({
      filter: (page) =>
        !page.includes('/impressum/') &&
        !page.includes('/datenschutz/'),
    }),
  ],
  vite: {
    resolve: {
      alias: {
        '@': '/src',
      },
    },
  },
});
