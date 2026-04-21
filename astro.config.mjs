import { defineConfig } from 'astro/config';
import tailwind from '@astrojs/tailwind';

export default defineConfig({
  site: 'https://bucknam-inc.com',
  integrations: [tailwind()],
  build: { format: 'file' },
});
