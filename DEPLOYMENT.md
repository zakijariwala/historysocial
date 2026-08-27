# Deployment

Fifteen minutes, once. After that every push to `main` renders and deploys.

Nothing here has been run: this environment had no Cloudflare account and no
token, and creating one is an outward-facing action. See BLOCKED.md.

---

## 1. Create the Pages project

```
npx wrangler pages project create history-social --production-branch main
```

The project name must match the one in `.github/workflows/render.yml`:

```yaml
command: pages deploy site --project-name=history-social --commit-dirty=true
```

## 2. Create the API token

Cloudflare dashboard → My Profile → API Tokens → Create Token → **Custom
token**.

Give it exactly these permissions and nothing else:

| Scope   | Resource                | Permission |
|---------|-------------------------|------------|
| Account | Cloudflare Pages        | Edit       |

That single permission is all `wrangler pages deploy` needs. Do not add Workers
Scripts, D1, R2, Zone or DNS permissions: this pipeline uses none of them, and
a deploy token that can edit DNS is a bad trade for zero convenience.

Under **Account Resources**, restrict the token to the one account that owns
the Pages project. Under **TTL**, set an expiry you will actually rotate on,
one year at the outside.

Copy the token once. Cloudflare will not show it again.

## 3. Find the account ID

Dashboard → Workers & Pages → the right-hand sidebar shows **Account ID**. It
is a 32-character hex string. It is not a secret in the way the token is, but
it goes in Actions secrets anyway so that neither value is ever in the
repository.

## 4. Put both into GitHub Actions secrets

Repository → Settings → Secrets and variables → Actions → New repository
secret:

```
CLOUDFLARE_API_TOKEN     the token from step 2
CLOUDFLARE_ACCOUNT_ID    the id from step 3
```

Never in the repository. Never in frontend JavaScript. The site is static and
has no credentials of its own; the only thing it fetches is `index.json` from
its own origin.

## 5. Put Cloudflare Access in front of it

Zero Trust dashboard → Access → Applications → Add an application → **Self
hosted**.

- Application domain: your Pages domain, `history-social.pages.dev`, or the
  custom domain if you attach one.
- Session duration: 1 month, so the phone does not re-authenticate weekly.
- Policy: **Allow**, with a rule of `Emails` → your own address. Add anyone
  else who reviews.
- Identity provider: One-time PIN is enough for one or two people and needs no
  setup. Google or GitHub is smoother on a phone if you already use one.

Free for up to 50 users. Write no auth code: the application never sees an
unauthenticated request.

**Check it.** Open the domain in a private window. You should get the Access
login and not the site.

## 6. First run

```
git push origin main
```

Watch the run. The steps, in order:

1. checkout
2. install Python dependencies
3. install Chromium through Playwright
4. install the bundled fonts and **fail the job if `fc-list` cannot see them**
5. apply migrations
6. **run the linters over every post marked `ready`** ← the gate
7. render
8. build `site/`
9. upload `out/` as an artifact, kept 14 days
10. deploy to Pages

Step 6 stops everything if a post has a placeholder, an unverified claim, an
unreviewed cover or a prose violation. That is the design. Nothing after it
runs.

If no post is marked `ready`, the render step prints `nothing to render`, the
site builds with an empty `posts` array, and the app shows its empty state.

## 7. Manual runs

Actions → **render and deploy** → Run workflow. The `post` input renders one
post by id instead of everything marked ready. Useful for re-rendering after a
token change without touching the rest of the archive.

---

## Rotating the token

1. Create the new token with the same single permission.
2. Update `CLOUDFLARE_API_TOKEN` in Actions secrets.
3. Run the workflow by hand to confirm the deploy still works.
4. Delete the old token in the Cloudflare dashboard.

## If the deploy fails

**`Authentication error [code: 10000]`** - the token lacks Pages:Edit, or it is
scoped to the wrong account.

**`Project not found`** - the `--project-name` in the workflow does not match
the project created in step 1.

**Fonts render as boxes** - step 4 failed and the job continued anyway. The
`fc-list | grep` guard exists to prevent this; if it is ever removed, put it
back.

**A slide overflows on the runner and not locally** - Chromium broke a line
differently. Shorten the slide in the essay file, reload it, and push. Do not
reduce the type size to fit; that changes the system for every post.
