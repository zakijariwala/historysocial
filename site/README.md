# Site Contract — Review & Publishing Surface

The mobile web application in `site/` is the review and publishing surface for the
Instagram carousel pipeline. It is designed to run in mobile Safari behind Cloudflare
Access.

---

## 1. Responsibilities

- **Review on device:** View rendered 1080x1350 PNG slides in a swipeable container with exact mobile proportions.
- **Synchronous clipboard copy:** Copy full Instagram post captions with a single tap.
- **Asset packaging:** Provide direct downloads for individual PNG slides and the full post `.zip` bundle.
- **Publication status:** Filter between Today, Ready, and Archive views based on post metadata.

---

## 2. Data Contract

The frontend is entirely static and fetches only from its own origin at `data/`:

### `data/index.json`
An array of post objects:

```json
[
  {
    "id": "musa-bridge",
    "title": "the bridge of baghdad",
    "label": "the imam who spent nineteen years in custody",
    "pillar": "collision",
    "ink": "iron",
    "occasion": "normal",
    "status": "ready",
    "caption": "Full post caption text...",
    "zip": "musa-bridge.zip",
    "slides": [
      "musa-bridge/01.png",
      "musa-bridge/02.png"
    ],
    "posted_on": null
  }
]
```

### `data/meta.json` (Optional Preview Banner)
When present (generated via `tools/build_site.py --preview`), renders a warning banner at the top of the interface:

```json
{
  "unreviewed": true,
  "note": "Preview build, 2026-09-01. These cards have not all passed the linter..."
}
```

---

## 3. Browser & Platform Constraints

- **iOS Clipboard Behavior:** iOS Safari allows `navigator.clipboard.writeText` only when executed synchronously inside a direct user tap event handler with zero preceding `await` ticks. Captions are therefore embedded directly in `data/index.json` and kept in memory.
- **Authentication:** Authentication is delegated completely to Cloudflare Access at the edge. The client application contains no auth tokens, API keys, or backend credentials.
- **Regeneration:** `site/data/` is completely replaced on every run of `tools/build_site.py`. Never hand-edit files inside `site/data/`.
