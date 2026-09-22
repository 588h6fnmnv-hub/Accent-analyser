# VoiceLens Frontend - Vercel Deployment Guide

## Prerequisites

1. **Vercel Account** - Sign up at [vercel.com](https://vercel.com)
2. **VoiceLens FastAPI Backend** - Deployed separately (see below)
3. **Git Repository** - Push frontend code to GitHub/GitLab/Bitbucket

## Deployment Steps

### 1. Deploy FastAPI Backend First

Deploy the VoiceLens FastAPI backend to a service that supports Python ML workloads:

**Options:**
- **Railway** - `railway up` from the `voicelens` directory
- **Render** - Web Service with Docker
- **Fly.io** - `fly launch` then `fly deploy`
- **Google Cloud Run** - Container deployment
- **AWS ECS/Fargate** - Container deployment
- **Hugging Face Spaces** - Docker space

**Required Backend Environment Variables:**
```bash
VOICELENS_ALLOWED_ORIGINS=https://your-vercel-app.vercel.app,https://your-custom-domain.com
VOICELENS_MAX_FILE_SIZE=50000000
VOICELENS_TARGET_SAMPLE_RATE=16000
VOICELENS_WHISPER_MODEL=base.en
VOICELENS_LOG_LEVEL=INFO
```

**Important:** Set `VOICELENS_ALLOWED_ORIGINS` to your Vercel frontend URL(s) - NOT `*` if using credentials.

### 2. Deploy Frontend to Vercel

#### Option A: Vercel Dashboard (Recommended)

1. Go to [vercel.com/new](https://vercel.com/new)
2. Import your Git repository
3. Set **Root Directory** to `frontend`
4. Vercel will auto-detect Next.js
5. Add Environment Variables (see below)
6. Click **Deploy**

#### Option B: Vercel CLI

```bash
cd frontend
vercel login
vercel --prod
```

### 3. Configure Environment Variables in Vercel

Go to **Settings → Environment Variables** and add:

| Name | Value | Environment |
|------|-------|-------------|
| `NEXT_PUBLIC_API_URL` | `https://your-backend-domain.com` | Production, Preview, Development |

**Note:** The backend URL must be HTTPS for production (required for microphone access).

### 4. Configure Custom Domain (Optional)

1. Go to **Settings → Domains**
2. Add your custom domain (e.g., `voicelens.example.com`)
3. Update `VOICELENS_ALLOWED_ORIGINS` in backend to include the custom domain
4. Redeploy backend

### 5. Verify PWA Installation

After deployment:
1. Open the app on iPhone Safari
2. Tap Share → "Add to Home Screen"
3. App should install as standalone PWA
4. Test recording flow end-to-end

## Project Structure

```
frontend/
├── public/
│   ├── manifest.json          # PWA manifest
│   ├── sw.js                  # Service worker
│   ├── icons/                 # PWA icons (72-512px)
│   ├── apple-touch-icon.png   # iOS home screen icon
│   └── favicon-*.png          # Favicons
├── src/
│   ├── app/
│   │   ├── layout.tsx         # Root layout with PWA meta tags
│   │   ├── page.tsx           # Redirects to /analyze
│   │   ├── analyze/
│   │   │   └── page.tsx       # Main recording flow
│   │   └── results/
│   │       └── page.tsx       # Results display
│   ├── components/ui/
│   │   ├── Button.tsx
│   │   └── Card.tsx
│   └── lib/
│       ├── api.ts             # API client with error handling
│       └── audio.ts           # MediaRecorder wrapper
├── next.config.ts             # Next.js config (standalone output)
├── .env.example               # Environment template
└── package.json
```

## App Flow

```
Home (/) → Redirect → Analyze (/analyze)
    ↓
[Ready to Record] → [Recording...] → [Stop] → [Analyzing...] → Results (/results)
    ↑                                                                      ↓
    ←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←←
    (New Analysis button)
```

## Features Implemented

- ✅ **PWA** - Installable on iPhone Home Screen
- ✅ **Responsive** - Mobile-first, works on iPhone Safari & desktop
- ✅ **Microphone Recording** - MediaRecorder API with Opus/WebM
- ✅ **Error Handling** - Permission denied, network errors, timeouts, empty recordings
- ✅ **Real Backend Integration** - No fake data
- ✅ **Dark/Light Mode** - Automatic via `prefers-color-scheme`
- ✅ **Vercel Compatible** - Standalone output, no local filesystem deps
- ✅ **TypeScript** - Strict type checking passes
- ✅ **Service Worker** - Caches static assets only (not API responses)

## Testing Locally

```bash
# Terminal 1: Start FastAPI backend
cd voicelens
source .venv/bin/activate
python -m voicelens serve

# Terminal 2: Start Next.js frontend
cd frontend
npm run dev
```

Open http://localhost:3000 - should redirect to /analyze

## Backend CORS Configuration

The FastAPI backend uses `VOICELENS_ALLOWED_ORIGINS` environment variable.

**For production, set to your Vercel URL(s):**
```bash
VOICELENS_ALLOWED_ORIGINS=https://your-app.vercel.app,https://your-custom-domain.com
```

**Do NOT use `*` with `allow_credentials=True`** - This is a security vulnerability.

## Troubleshooting

### Microphone not working on iPhone
- Ensure backend URL is HTTPS (required for `getUserMedia`)
- Check Safari Settings → VoiceLens → Microphone = Allow
- Verify `VOICELENS_ALLOWED_ORIGINS` includes your Vercel domain

### CORS Errors
- Backend `VOICELENS_ALLOWED_ORIGINS` must match frontend origin exactly
- Include both `https://*.vercel.app` and custom domains
- No trailing slashes

### Build Failures
- Run `npm run build` locally first
- Check TypeScript errors: `npx tsc --noEmit`
- Ensure all imports resolve correctly

### API Timeout
- Analysis can take 30-120 seconds for long audio
- Frontend has 120s timeout configured
- Consider increasing backend timeout for very long recordings

## File Size Limits

- **Frontend**: No limit (static files)
- **Backend**: `VOICELENS_MAX_FILE_SIZE` (default 50MB)
- **Vercel**: 50MB request body limit (Pro plan: 100MB)

For longer recordings, consider chunked upload or backend preprocessing.