# Hosting Bash Scripts on Custom Domain - Solutions Guide

## Overview
You want to host your `install-chromium.sh` script on your custom domain so users can install your tool with:
```bash
curl -LsSf https://yourdomain.com/install.sh | sh
```

## Solution 1: Vercel (Recommended for your setup)

### ✅ Pros:
- You're already using Vercel for your UI
- Easy to set up
- Free tier available
- CDN distribution
- Custom domain support
- Automatic HTTPS

### ⚠️ Considerations:
- Static files only (no server-side processing)
- 100MB file size limit (your script is only 27KB, so no issue)

### Implementation:

#### Option A: Separate Vercel Project for Scripts
Create a new directory structure for your scripts:

```
scripts-hosting/
├── public/
│   ├── install.sh          # Your install-chromium.sh renamed
│   └── install-chromium.sh # Original name as alias
├── vercel.json
└── package.json
```

**vercel.json:**
```json
{
  "headers": [
    {
      "source": "/(.*\\.sh)",
      "headers": [
        {
          "key": "Content-Type",
          "value": "text/plain; charset=utf-8"
        },
        {
          "key": "Cache-Control",
          "value": "public, max-age=86400"
        }
      ]
    }
  ],
  "redirects": [
    {
      "source": "/install",
      "destination": "/install.sh",
      "permanent": false
    }
  ]
}
```

#### Option B: Add to Existing UI Project
Add your script to your existing `ui/public/` directory:

1. Copy `install-chromium.sh` to `ui/public/install.sh`
2. Update `ui/vercel.json`:

```json
{
  "headers": [
    {
      "source": "/(.*\\.sh)",
      "headers": [
        {
          "key": "Content-Type",
          "value": "text/plain; charset=utf-8"
        }
      ]
    }
  ],
  "rewrites": [
    {
      "source": "/install",
      "destination": "/install.sh"
    },
    {
      "source": "/(.*)",
      "destination": "/index.html"
    }
  ]
}
```

## Solution 2: GitHub Pages + Custom Domain

### ✅ Pros:
- Free
- Direct integration with your GitHub repo
- Automatic updates when you push changes
- Custom domain support

### Implementation:
1. Create a `gh-pages` branch
2. Add your scripts to the root or a `scripts/` directory
3. Enable GitHub Pages in repository settings
4. Configure custom domain

## Solution 3: Netlify

### ✅ Pros:
- Excellent for static sites
- Great free tier
- Easy deployment from Git
- Custom headers and redirects

### Implementation:
Create `netlify.toml`:
```toml
[[headers]]
  for = "/*.sh"
  [headers.values]
    Content-Type = "text/plain; charset=utf-8"
    Cache-Control = "public, max-age=86400"

[[redirects]]
  from = "/install"
  to = "/install.sh"
  status = 302
```

## Solution 4: AWS S3 + CloudFront

### ✅ Pros:
- Highly scalable
- Very reliable
- CDN distribution
- Cost-effective for high traffic

### ⚠️ Cons:
- More complex setup
- Requires AWS knowledge

## Solution 5: GitHub Raw + Custom Domain (Not Recommended)

While you could use GitHub's raw file serving with a CNAME redirect, this:
- Violates GitHub's Terms of Service for high traffic
- No custom headers
- Less reliable

## Recommended Implementation Plan

Given your current setup, I recommend **Option A (Separate Vercel Project)**:

### Step 1: Create the hosting structure
```bash
mkdir scripts-hosting
cd scripts-hosting
mkdir public
```

### Step 2: Set up the files
```bash
# Copy your script
cp ../install-chromium.sh public/install.sh

# Create package.json
echo '{
  "name": "rebrowse-scripts",
  "version": "1.0.0",
  "description": "Installation scripts for Rebrowse"
}' > package.json
```

### Step 3: Configure Vercel
Create the `vercel.json` as shown above.

### Step 4: Deploy
```bash
npx vercel --prod
```

### Step 5: Configure custom domain
In Vercel dashboard, add your custom domain (e.g., `install.rebrowse.dev` or `scripts.yourdomain.com`)

## Usage Examples

After deployment, users can install with:
```bash
# Short URL
curl -LsSf https://yourdomain.com/install | sh

# Explicit script name
curl -LsSf https://yourdomain.com/install.sh | sh

# With error handling
curl -LsSf https://yourdomain.com/install.sh | bash -s -- --help
```

## Security Considerations

1. **HTTPS Only**: Ensure your domain uses HTTPS (Vercel provides this automatically)
2. **Content-Type Headers**: Set proper headers to prevent browsers from executing scripts
3. **Integrity**: Consider adding checksums for script verification
4. **Rate Limiting**: Monitor usage to prevent abuse

## Advanced: Script Versioning

You could also support versioned scripts:
```
public/
├── install.sh          # Latest version
├── v1.0.0/
│   └── install.sh
└── v1.1.0/
    └── install.sh
```

With redirects in `vercel.json`:
```json
{
  "redirects": [
    {
      "source": "/install",
      "destination": "/install.sh"
    },
    {
      "source": "/latest",
      "destination": "/install.sh"
    }
  ]
}
```

## Next Steps

1. Choose your preferred solution (I recommend Vercel Option A)
2. Set up the hosting structure
3. Deploy and test
4. Configure your custom domain
5. Update your documentation with the new installation command

Would you like me to help you implement any of these solutions?