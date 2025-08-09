/*
  Configure where the backend API lives.

  Option A (GitHub Pages, recommended):
    - Deploy the Flask backend to Render (render.yaml provided).
    - Use the Render URL as the API base, no trailing slash.
    - You can also override at runtime via localStorage:
        localStorage.setItem('api_base', 'https://your-backend.onrender.com')

  Option B (local dev with Flask):
    - Set to empty string '' to call same-origin when running Flask locally.

  Do NOT include a trailing slash.
*/
(function () {
  function trim(u) { return (u || '').replace(/\/+$/, ''); }
  // 1) Hardcoded default (edit this after deploy if Render gives a different URL)
  var hardcoded = 'https://menmonica-backend.onrender.com'; // change if your Render URL differs
  // 2) Allow runtime override via localStorage
  var fromLS = null;
  try { fromLS = localStorage.getItem('api_base'); } catch (_) {}
  // 3) Fallback to same-origin (useful for local Flask dev)
  var sameOrigin = '';
  window.API_BASE = trim(fromLS || hardcoded || sameOrigin);
})();