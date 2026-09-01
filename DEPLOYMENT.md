# Deployment

The publishing and review surface is a static web app deployed to Cloudflare Pages
at `https://history-social.pages.dev`, protected by Cloudflare Access.

Rendering runs locally. Slides are built to `site/data/` and deployed directly using
the Wrangler CLI.

---

## 1. The Deployment Workflow

Rendering and site generation happen on the developer machine:

```bash
# 1. Lint every post marked ready
python tools/lint_post.py --all-ready

# 2. Render all ready posts to out/<post>/
python render/render.py --all-ready

# 3. Assemble site/data/ (index.json, slides, and zip packages)
python tools/build_site.py

# 4. Deploy site/ to Cloudflare Pages
npx wrangler pages deploy site --project-name=history-social --branch=main --commit-dirty=true
```

---

## 2. Preview Builds (Drafts)

To inspect unverified candidate posts or cover tests on a phone:

```bash
# Assemble site/data/ with preview flag (renders red banner in UI)
python tools/build_site.py --preview --all-drafts

# Deploy preview
npx wrangler pages deploy site --project-name=history-social --branch=preview
```

---

## 3. Configuring Cloudflare Access

The review site must not be public. Set up Cloudflare Access in Zero Trust:

1. Navigate to **Cloudflare Dashboard** → **Zero Trust** → **Access** → **Applications**.
2. Click **Add an Application** → select **Self-hosted**.
3. Configure application parameters:
   - **Application name:** `history-social-review`
   - **Application domain:** `history-social.pages.dev` (and any custom domain attached)
   - **Session Duration:** `1 month`
4. Define the Access Policy:
   - **Policy Name:** `Reviewers`
   - **Action:** `Allow`
   - **Rules:** `Include` → `Emails` → enter authorized reviewer email addresses.
5. Identity Provider:
   - Enable **One-Time PIN (OTP)** or configure Google/GitHub OAuth.
6. Save the application.
7. **Verification:** Open `https://history-social.pages.dev` in a private window; verify that the Cloudflare Access login modal appears.

---

## 4. Cache Invalidation and Deployment Pruning

Cloudflare Pages caches assets at the edge. When older deployments are removed or
when an asset is re-rendered with identical filenames, stale cached assets may persist:

1. **Deploying Updates:** A new `wrangler pages deploy` triggers a fresh deployment ID
   and updates the production alias automatically.
2. **Purging Edge Cache:** If updated cards or deleted deployments still resolve from
   edge cache:
   - Cloudflare Dashboard → **Caching** → **Configuration** → **Purge Everything**
   - Or via CLI / API: purge cache on the parent zone if bound to a custom domain.
3. **Deployment List:** Inspect live deployments with:
   ```bash
   npx wrangler pages deployment list --project-name=history-social
   ```
