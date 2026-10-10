# WIMS Web + Capture

Next.js frontend for **Where Is My Space?** The `/capture` route is a mobile-first, installable PWA for adding camera sources and uploading video from a phone or computer.

## Requirements

- Node.js 20.9 or newer
- npm

## Run locally

```bash
npm install
cp .env.example .env.local
npm run dev
```

Open [http://localhost:3000](http://localhost:3000). The dashboard is at `/`; the mobile source studio is at `/capture`.

Set `NEXT_PUBLIC_WIMS_API_URL` in `.env.local` to the FastAPI service origin. For local testing this is commonly `http://localhost:8000`, with the API's `CORS_ORIGINS` set to `http://localhost:3000`.

## Phone install

Deploy the web app to an HTTPS domain and open `/capture` on the phone. Use the browser's **Add to Home Screen / Install app** option. The app manifest is served from `/manifest.webmanifest`.

- **Phone camera:** requests camera permission, records a short clip, lets the user review it, then uploads the recording.
- **Screen share:** uses the browser's Screen Capture API when supported. Mobile support varies; the fallback is the phone's built-in screen recorder followed by Video File upload.
- **Video file:** accepts MP4/WebM files up to 100 MiB per file (server configuration can set the limit).
- **CCTV / IP camera:** registers an RTSP/RTSPS source. The server encrypts the URL; stream connection/analysis is not implemented yet.
- **Registered sources:** lists saved source metadata without exposing camera URLs.

The Capture app prompts for a shared beta pairing code configured only on the backend as `WIMS_CAPTURE_ACCESS_CODE`. The code is retained in the current tab's session storage. It is not a full user-account system, so public production use will need stronger access control and rate limits.

## Available scripts

- `npm run dev` — local dev server
- `npm run build` — production build
- `npm run start` — serve a production build
- `npm run lint` — ESLint
- `npm run typecheck` — TypeScript checks

## Current implementation status

Implemented in code: dashboard UI, capture PWA route/manifest, browser camera recording, feature-detected screen recording, MP4/WebM upload client, source registration/list UI, FastAPI endpoints, Supabase migrations for source/job metadata, private temporary video storage, pairing-code checks, and RTSP URL encryption at rest.

**Not yet implemented or verified end-to-end:** AI inference, continuous real-time streaming, occupancy/seat estimation, applying the SQL migrations to a live Supabase project, configuring production secrets, and deploying the frontend/API. All dashboard numbers remain labelled sample data. Upload success is not the same as AI processing success.

Never put `SUPABASE_SERVICE_ROLE_KEY`, `WIMS_CAPTURE_ACCESS_CODE` or `WIMS_SOURCE_ENCRYPTION_KEY` in frontend environment variables.
