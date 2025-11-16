# GitHub Pages Deployment Setup

This document explains how to deploy the GoonGov frontend to GitHub Pages.

## Quick Setup

1. **Enable GitHub Pages in your repository settings:**
   - Go to Settings → Pages
   - Under "Source", select "GitHub Actions"
   - Save the settings

2. **Push the code:**
   - The GitHub Actions workflow (`.github/workflows/deploy-pages.yml`) will automatically deploy when you push to `main` or `master` branch
   - Or manually trigger it from the Actions tab → "Deploy to GitHub Pages" → "Run workflow"

3. **Access your site:**
   - After deployment, your site will be available at: `https://<username>.github.io/<repository-name>/`
   - Or if using a custom domain, configure it in Settings → Pages

## File Structure

The deployment workflow copies:
- `goongov/index.html` → root of the deployed site
- `goongov/frontend/` → `frontend/` directory in the deployed site

## Backend API Configuration

**Important:** The frontend needs a backend API to function. By default, it's configured to use `http://localhost:5000`.

For production deployment, you'll need to:

1. **Host your backend separately** (e.g., on Heroku, Railway, Render, etc.)
2. **Update the API URL** in `index.html`:
   ```javascript
   window.API_BASE_URL = 'https://your-backend-url.com';
   ```
3. **Enable CORS** on your backend to allow requests from your GitHub Pages domain

### Backend CORS Setup

If using Flask (as in `backend/app.py`), add CORS support:

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=["https://<username>.github.io"])
```

## Manual Deployment (Alternative)

If you prefer to deploy manually:

1. Create a `gh-pages` branch:
   ```bash
   git checkout --orphan gh-pages
   git rm -rf .
   ```

2. Copy the frontend files:
   ```bash
   cp -r goongov/frontend .
   cp goongov/index.html .
   touch .nojekyll
   ```

3. Commit and push:
   ```bash
   git add .
   git commit -m "Deploy to GitHub Pages"
   git push origin gh-pages
   ```

4. In repository settings, set the source to the `gh-pages` branch.

## Troubleshooting

- **404 errors:** Make sure `.nojekyll` file exists in the root
- **Assets not loading:** Check that paths in `index.html` are correct (should be `frontend/static/...`)
- **CORS errors:** Ensure your backend has CORS enabled for your GitHub Pages domain
- **API not working:** Verify `window.API_BASE_URL` is set correctly in `index.html`

