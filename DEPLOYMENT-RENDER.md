# Deploy Menmónica backend to Render and wire GitHub Pages frontend

This guide deploys your Flask backend to Render (free tier) using the blueprint [render.yaml](render.yaml), then points the static frontend (GitHub Pages /docs) to the live API via [docs/config.js](docs/config.js).

Prereqs:
- GitHub repository with this code pushed
- Render account (https://render.com)

## 1) Deploy the backend on Render (Blueprint)

1. Sign in to Render and click: New > Blueprint
2. Choose the GitHub repo that contains this project
3. Render will detect [render.yaml](render.yaml) at the repo root and show a preview:
   - Service type: Web Service
   - Name: menmonica-backend (you may change it)
   - Env: python
   - Plan: Free
   - Health check path: /api/health
   - Build Command: pip install -r requirements.txt
   - Start Command: gunicorn app:app
   - Env Var PYTHON_VERSION=3.11.9
4. Click Apply and Deploy
5. Wait for the first build and deploy to finish (1–5 minutes on free tier)
6. After deploy, open the service in Render and note the public URL, e.g.:
   - https://menmonica-backend.onrender.com
7. Verify the health endpoint:
   - Open https://YOUR-BACKEND.onrender.com/api/health
   - Expected JSON: {"status":"ok"}
8. If health is failing, open Logs in Render to see errors (common issues below)

Notes:
- [app.py](app.py) exposes /api/convert and /api/random_phrase and adds permissive CORS for /api/* so your GitHub Pages origin can call it
- [requirements.txt](requirements.txt) and [render.yaml](render.yaml) are already included

## 2) Verify API endpoints (optional curl)

PowerShell:
- Health:
  Invoke-RestMethod -Uri "https://YOUR-BACKEND.onrender.com/api/health"
- Convert (example):
  Invoke-RestMethod -Method Post -ContentType "application/json" -Uri "https://YOUR-BACKEND.onrender.com/api/convert" -Body '{"number":"3279","maxCombos":10}'

bash/curl:
- Health:
  curl -s https://YOUR-BACKEND.onrender.com/api/health
- Convert:
  curl -s -X POST "https://YOUR-BACKEND.onrender.com/api/convert" -H "Content-Type: application/json" -d '{"number":"3279","maxCombos":10}'

You should get JSON with partitions, totalResults, and combosPreview.

## 3) Point the frontend to the backend

The static site in /docs loads [docs/config.js](docs/config.js) before other scripts. That file sets window.API_BASE.

Option A — quick test (no commit):
- In the browser console on your GitHub Pages site, run:
  localStorage.setItem('api_base', 'https://YOUR-BACKEND.onrender.com')
- Refresh the page and test. The UI will now call YOUR-BACKEND.

Option B — commit the URL:
- Edit [docs/config.js](docs/config.js) and set the hardcoded variable:
  var hardcoded = 'https://YOUR-BACKEND.onrender.com';
- Commit and push to main. GitHub Pages will update /docs automatically.

Both index and practice pages already use window.API_BASE:
- [docs/index.html](docs/index.html) calls (API_BASE ? API_BASE : '') + '/api/convert'
- [docs/practice.html](docs/practice.html) calls (API_BASE ? API_BASE : '') + '/api/random_phrase?words=...'

## 4) End-to-end test

- Open your GitHub Pages site URL (project page): https://USERNAME.github.io/REPO-NAME/
- Type a number like 3279 on the home page
- You should see partitions populate and combinations preview
- Open the browser DevTools Network tab and confirm requests go to:
  https://YOUR-BACKEND.onrender.com/api/convert and /api/random_phrase
- Practice page should fetch a random phrase successfully

## 5) Troubleshooting

- Wrong API base:
  - Ensure [docs/config.js](docs/config.js) has the exact Render URL without trailing slash
  - Clear any old override with:
    localStorage.removeItem('api_base')

- Health check failing:
  - Confirm Render uses healthCheckPath: /api/health (in [render.yaml](render.yaml))
  - Make sure deploy finished successfully; review Render Logs

- CORS errors:
  - The backend sets Access-Control-Allow-Origin: * for /api/* in [app.py](app.py)
  - Verify your browser is calling exactly https://YOUR-BACKEND.onrender.com/api/...

- Large cache files:
  - two_digit_cache.json is large and bundled into the image; that’s fine on Render
  - Free plan memory is limited; if you see OOM in logs, consider Pro plan or reducing cache size

- GitHub Pages paths:
  - Your /docs site already has [.nojekyll](docs/.nojekyll) and [docs/404.html](docs/404.html) for deep links
  - Use relative links (already done in /docs) like learn.html and practice.html

## 6) Summary

- Deploy backend via Blueprint using [render.yaml](render.yaml)
- Verify health at /api/health
- Set frontend API base via [docs/config.js](docs/config.js) or a localStorage override
- Test convert and practice flows on your GitHub Pages site

Once you have the live Render URL, update [docs/config.js](docs/config.js) or tell me the URL and I’ll set it.