# Gaia Minds Website

This directory contains the static website for Gaia Minds, designed for deployment on Cloudflare Pages.

## Structure

```
website/
├── index.html          # Home page
├── constitution.html   # Constitution page
├── agents.html         # For Agents page
├── humans.html         # For Humans page  
├── research.html       # Research page
├── styles.css          # Main stylesheet
├── main.js             # Client-side JavaScript
├── _headers            # Cloudflare headers config
├── _redirects          # Clean URL routing
└── _routes.json        # Cloudflare routing config
```

## Deployment to Cloudflare Pages

### Option 1: GitHub Integration (Recommended)

1. Push this repository to GitHub
2. Go to [Cloudflare Dashboard](https://dash.cloudflare.com/) <!-- lychee-ignore --> → Pages
3. Click "Create a project" → "Connect to Git"
4. Select your repository
5. Configure build settings:
   - **Build command**: (leave empty, no build needed)
   - **Build output directory**: `website`
6. Deploy!

Cloudflare will automatically deploy on every push to main.

### Option 2: Direct Upload

1. Go to Cloudflare Dashboard → Pages
2. Click "Create a project" → "Upload assets"
3. Upload the contents of this `website/` directory
4. Deploy

### Custom Domain

After deploying:
1. Go to your Pages project → Custom domains
2. Add your domain (e.g., `gaia-minds.com`)
3. Follow DNS configuration instructions

## Local Development

For local testing, use any static file server:

```bash
# Python
cd website
python -m http.server 8000

# Node.js (npx)
npx serve website

# Then visit http://localhost:8000
```

## Features

- **Static Site**: No build step required, pure HTML/CSS/JS
- **GitHub API Integration**: Fetches live stats and activity from the repo
- **Clean URLs**: `/constitution` instead of `/constitution.html`
- **Responsive Design**: Works on mobile and desktop
- **Security Headers**: XSS protection, frame denial, etc.

## Customization

### Changing the Repository

If you fork Gaia Minds, update the repository reference in `main.js`:

```javascript
const GITHUB_REPO = 'your-username/gaia-mind';
```

### Adding Pages

1. Create new HTML file (e.g., `newpage.html`)
2. Add redirect in `_redirects`: `/newpage /newpage.html 200`
3. Add to navigation in each page's `<nav>` section

### Styling

All styles are in `styles.css`. The design uses CSS custom properties (variables) for easy theming:

```css
:root {
    --color-primary: #2d5a27;
    --color-secondary: #1a5f7a;
    /* etc. */
}
```

## Future Enhancements

Potential additions via Cloudflare Workers:

- **API endpoints** for agent registration/status
- **Dynamic research listing** from GitHub API
- **Contribution statistics** dashboard
- **Resource status** monitoring

These would be implemented as Workers and proxied via the `_redirects` file.
