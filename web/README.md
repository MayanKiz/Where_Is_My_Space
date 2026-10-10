# WIMS Web

Next.js frontend for **Where Is My Space?**

## Requirements

- Node.js 20.9 or newer
- npm

## Run locally

```bash
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Available scripts

- `npm run dev` — start the local development server
- `npm run build` — create a production build
- `npm run start` — serve a production build
- `npm run lint` — run ESLint
- `npm run typecheck` — run TypeScript checks

## Current implementation status

The initial scaffold provides the frontend foundation. Dashboard figures shown by the current UI are **sample presentation data**, not live AI or camera readings. MP4 processing, Supabase persistence and live data wiring are subsequent steps.

Copy `.env.example` to `.env.local` only when setting up local integrations. Do not commit real credentials.
