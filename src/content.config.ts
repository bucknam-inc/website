import { defineCollection, z } from 'astro:content';
import { glob } from 'astro/loaders';

const pages = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/pages' }),
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    hero: z.string().optional(),
    sourceNode: z.coerce.string().optional(),
  }),
});

const blog = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/blog' }),
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    author: z.string().default('Bucknam Infrastructure'),
    publishDate: z.coerce.date().optional(),
    sourceNode: z.coerce.string().optional(),
  }),
});

const jobs = defineCollection({
  loader: glob({ pattern: '**/*.md', base: './src/content/jobs' }),
  schema: z.object({
    title: z.string(),
    slug: z.string(),
    openForApplications: z.boolean().default(true),
    sourceNode: z.coerce.string().optional(),
  }),
});

const cities = defineCollection({
  loader: glob({ pattern: '**/*.json', base: './src/content/cities' }),
  schema: z.object({
    name: z.string(),
    state: z.string().default('CA'),
    county: z.enum(['Los Angeles', 'Orange', 'San Bernardino', 'Riverside', 'San Diego']),
    placeGeoId: z.string().optional(),
    customGeoJson: z.any().optional(),
    isCustomer: z.boolean().default(false),
    surveyYears: z.array(z.number()).default([]),
  }),
});

export const collections = { pages, blog, jobs, cities };
