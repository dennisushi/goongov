# GitHub Pages Deployment

## ✅ Setup Complete

Your repository is now configured for GitHub Pages deployment!

## 📋 What Was Created

1. **`goongov/index.html`** - Main entry point for GitHub Pages
2. **`.github/workflows/deploy-pages.yml`** - Automated deployment workflow
3. **`goongov/.nojekyll`** - Ensures all files are served (prevents Jekyll processing)

## 🚀 How to Deploy

### Option 1: Automatic (Recommended)

1. **Enable GitHub Pages:**
   - Go to your repository on GitHub
   - Navigate to **Settings** → **Pages**
   - Under "Source", select **"GitHub Actions"**
   - Save

2. **Push your code:**
   ```bash
   git add .
   git commit -m "Add GitHub Pages deployment"
   git push
   ```

3. **Monitor deployment:**
   - Go to **Actions** tab in your repository
   - Watch the "Deploy to GitHub Pages" workflow run
   - Once complete, your site will be live!

### Option 2: Manual Trigger

- Go to **Actions** → **Deploy to GitHub Pages** → **Run workflow**

## 🌐 Access Your Site

After deployment, your site will be available at:
- `https://<username>.github.io/<repository-name>/`

## ⚙️ Backend Configuration

**Important:** The frontend requires a backend API to function.

1. **For local development:** The default `http://localhost:5000` will work
2. **For production:** You need to:
   - Host your backend separately (Heroku, Railway, Render, etc.)
   - Update the API URL in `goongov/index.html`:
     ```javascript
     window.API_BASE_URL = 'https://your-backend-url.com';
     ```
   - Enable CORS on your backend for your GitHub Pages domain

### Backend CORS Example (Flask)

```python
from flask_cors import CORS

app = Flask(__name__)
CORS(app, origins=[
    "https://<username>.github.io",
    "http://localhost:5000"  # for local dev
])
```

## 📁 File Structure After Deployment

```
_site/
├── index.html
├── .nojekyll
└── frontend/
    ├── static/
    │   ├── app.js
    │   ├── style.css
    │   └── images/
    └── ...
```

## 🔧 Troubleshooting

- **404 errors:** Check that `.nojekyll` exists in the deployed site
- **Assets not loading:** Verify paths in `index.html` are correct
- **CORS errors:** Ensure backend CORS is configured for your domain
- **Workflow fails:** Check the Actions tab for error messages

## 📝 Notes

- The workflow only runs when files in `goongov/` change
- Deployment happens automatically on push to `main` or `master`
- The site is served from the root of your repository's Pages site

