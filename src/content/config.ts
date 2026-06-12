import { defineCollection, z } from 'astro:content';

const blog = defineCollection({
  type: 'content',
  schema: z.object({
    title: z.string(),
    description: z.string(),
    pubDate: z.coerce.date(),
    author: z.string().default('SmartSwitch24'),
    lang: z.enum(['de', 'ar']),
    category: z.enum([
      'strom',
      'gas',
      'handy',
      'smartphones',
      'tablets',
      'smartwatches',
      'reisen',
      'finanzen',
      'ratgeber',
    ]),
    tags: z.array(z.string()).default([]),
    draft: z.boolean().default(false),
    faqs: z
      .array(z.object({ q: z.string(), a: z.string() }))
      .optional(),
    cta: z
      .object({ text: z.string(), href: z.string(), label: z.string() })
      .optional(),
    heroImage: z.string().optional(),
    heroImageAlt: z.string().optional(),
  }),
});

export const collections = { blog };
