---
id: seo-metadata-builder
name: seo-metadata-builder
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: seo-metadata-builder
file_path: skills/seo-metadata-builder.md
name: SEO & Metadata Builder
category: frontend
tags: [seo, metadata, open-graph, twitter-cards, json-ld]
author: opencode-core
version: 1.0.0
description: Generate complete HTML meta tags, Open Graph, Twitter Cards, and JSON-LD structured data.
---

# SEO & Metadata Builder

## Prerequisites & Dependencies
- Node.js 18+ or a build tool (Vite, Webpack, Next.js)
- Mandatory packages: `npm i next-seo` (for Next.js) or manual template generation
- Access to the application's data: page title, description, site URL, author, and entity types
- Optional: `npm i react-helmet` for dynamic meta management in React

## Execution Steps
1. Inventory all pages that need SEO metadata: home, articles, product pages, error pages
2. For each page, collect the required fields: `title`, `description`, `url`, `image`, `type`, `siteName`, and social handles
3. Generate HTML meta tags: `<title>`, `<meta name="description">`, `<meta charset>`, `<meta viewport>`
4. Add Open Graph tags: `og:title`, `og:description`, `og:image`, `og:url`, `og:type`, `og:locale`
5. Add Twitter Card tags: `twitter:card`, `twitter:title`, `twitter:description`, `twitter:image`, `twitter:creator`
6. Generate JSON-LD structured data: `@context`, `@type` (e.g., `Article`, `Product`, `Organization`), and relevant properties (`author`, `datePublished`, `price`, `availability`)
7. Insert all tags into your `_document.js` (Next.js) or `head` component, ensuring they are server-rendered and hydrated correctly
8. Validate your markup: use `Google Search Console`, `Facebook Sharing Debugger`, and `schema.org validators`

```javascript
// Example: Comprehensive SEO component for Next.js using next-seo
import React from 'react';
import { NextSeo } from 'next-seo';

const SeoMetadata = ({ title, description, image, slug }) => (
  <NextSeo
    title={title}
    description={description}
    openGraph={{
      type: 'website',
      url: `https://example.com${slug}`,
      images: [{ url: image, width: 1200, height: 630 }],
    }}
    twitter={{
      card: 'summary_large_image',
      title,
      description,
      images: [image],
    }}
    jsonLD={[
      {
        '@context': 'https://schema.org',
        '@type': 'Organization',
        name: 'Example Corp',
        url: 'https://example.com',
        logo: '/logo.png',
      },
    ]}
  />
);

export default SeoMetadata;
```