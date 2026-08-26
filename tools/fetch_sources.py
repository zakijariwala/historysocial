"""Fetch openly licensed source texts, and refuse to fetch anything else.

    python tools/fetch_sources.py --list              what is fetchable
    python tools/fetch_sources.py --supply            what YOU must supply
    python tools/fetch_sources.py openiti:0310Tabari  fetch one catalogue entry
    python tools/fetch_sources.py --all               fetch every entry

Two rules govern this tool, and neither has an override flag:

  1. It downloads from OpenITI and from archive.org only, and from archive.org
     only for imprints published before 1929.
  2. It never downloads a modern translation. SUNY's al-Tabari, the Cambridge
     histories, Modarressi, Pierce and Dakake are in copyright. They are
     registered by hand, from a copy you own, in sources/manifest.yaml.

Anything fetched lands in sources/ as a plain text file and is then registered
by hand with an edition statement. Downloading a file is not the same as
knowing what edition it is; only a human reading the title page settles that.
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "sources"

USER_AGENT = "history-social/1.0 (local research pipeline; contact: repo owner)"

# Everything this tool is allowed to reach for. Each entry names the licence
# at the point of collection, never afterwards.
CATALOGUE = {
    # OpenITI entries name a corpus directory, not a file. The version files in
    # it are renamed between releases, so the directory is listed at fetch time
    # and the largest text version is taken. Guessing a filename here would rot.
    "openiti:tabari-tarikh": {
        "title": "al-Tabari, Ta'rikh al-rusul wa'l-muluk (Arabic)",
        "licence": "CC-BY-SA-4.0 (OpenITI corpus)",
        "note": "Machine-readable. Carries de Goeje's page markers as PageV..P...",
        "openiti": ("0325AH", "0310Tabari", "0310Tabari.Tarikh"),
        "out": "openiti--tabari-tarikh-ara.txt",
    },
    "archive:annalesquosscri01unkngoog": {
        "title": "al-Tabari, Annales, ed. M. J. de Goeje, ser. I (Leiden, Brill, 1879)",
        "licence": "public domain (published before 1929)",
        "published": 1879,
        "note": "The critical Arabic edition every modern translation cites by page.",
        "out": "degoeje--tabari-annales-01.txt",
    },
    "archive:annalesquosscri02goejgoog": {
        "title": "al-Tabari, Annales, ed. M. J. de Goeje, ser. II (Leiden, Brill, 1890)",
        "licence": "public domain (published before 1929)",
        "published": 1890,
        "out": "degoeje--tabari-annales-02.txt",
    },
    "archive:a-t_20210613": {
        "title": "Yaqut, Mu'jam al-buldan, ed. Wustenfeld, vol. I (Leipzig, 1866)",
        "licence": "public domain (published before 1929)",
        "published": 1866,
        "note": "Distances, routes and place descriptions, in Wustenfeld's pagination.",
        "out": "wustenfeld--yaqut-mujam-01.txt",
    },
    "archive:g-z_20210612": {
        "title": "Yaqut, Mu'jam al-buldan, ed. Wustenfeld, vol. II (Leipzig, 1867)",
        "licence": "public domain (published before 1929)",
        "published": 1867,
        "out": "wustenfeld--yaqut-mujam-02.txt",
    },
}

# Named so the operator sees them, and so nothing here is ever downloadable.
SUPPLY_YOURSELF = [
    ("The History of al-Tabari, vol. XXIX (SUNY): al-Mansur and al-Mahdi",
     "In copyright. The chronicle years of the first arrests."),
    ("The History of al-Tabari, vol. XXX (SUNY): the caliphate in equilibrium",
     "In copyright. Harun al-Rashid's reign, the final custody, the death."),
    ("Modarressi, Crisis and Consolidation in the Formative Period of Shi'ite Islam",
     "In copyright. The standing scholarly account of the Waqifa split."),
    ("Dakake, The Charismatic Community",
     "In copyright. Walaya and the shape of the early community."),
    ("Pierce, Twelve Infallible Men",
     "In copyright. The later devotional reception."),
    ("Cambridge History of Iran, vol. 4 / Cambridge History of Islam",
     "In copyright. 'Abbasid administrative background."),
]


def openiti_urls(repo: str, author: str, book: str) -> list[str]:
    """List an OpenITI book directory and return its text versions, largest first.

    The corpus renames version files between releases (`-ara1`, `.mARkdown`,
    `.inProgress`), so a hardcoded filename breaks silently. The directory is
    the stable address.
    """
    import json

    api = (f"https://api.github.com/repos/OpenITI/{repo}/contents/"
           f"data/{author}/{book}")
    req = urllib.request.Request(api, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        listing = json.loads(resp.read())
    files = [f for f in listing
             if f["type"] == "file"
             and not f["name"].endswith((".yml", ".md"))
             and f["size"] > 100_000]
    files.sort(key=lambda f: f["size"], reverse=True)
    return [f["download_url"] for f in files]


def archive_urls(identifier: str, published: int) -> list[str]:
    """The plain-text derivatives of an archive.org item, newest scan first.

    The derivative is NOT always `<identifier>_djvu.txt`: Wustenfeld's Yaqut
    carries its transliterated title, diacritics and all. The metadata endpoint
    is the only reliable way to learn the real name.

    The item's own year is re-read here and checked against 1929, so the rule
    holds even when the catalogue entry above is wrong about the date.
    """
    import json

    req = urllib.request.Request(f"https://archive.org/metadata/{identifier}",
                                 headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp:
        meta = json.loads(resp.read())
    year = str(meta.get("metadata", {}).get("year") or published)[:4]
    if year.isdigit() and int(year) >= 1929:
        raise RuntimeError(f"archive.org item is dated {year}; the cutoff is 1929")
    names = [f["name"] for f in meta.get("files", []) if f["name"].endswith(".txt")]
    if not names:
        raise RuntimeError("the item has no plain-text derivative")
    return [f"https://archive.org/download/{identifier}/"
            f"{urllib.parse.quote(n)}" for n in names]


def fetch_one(key: str, entry: dict, force: bool) -> bool:
    out = SRC / entry["out"]
    if out.exists() and not force:
        print(f"have    {entry['out']}  ({out.stat().st_size:,} bytes)")
        return True
    if key.startswith("archive:") and entry.get("published", 9999) >= 1929:
        print(f"REFUSED {key}: archive.org imprints must predate 1929", file=sys.stderr)
        return False
    try:
        if "openiti" in entry:
            urls = openiti_urls(*entry["openiti"])
        else:
            urls = archive_urls(key.split(":", 1)[1], entry.get("published", 9999))
    except Exception as exc:
        print(f"FAILED  {key}: could not resolve a download URL: {exc}",
              file=sys.stderr)
        return False
    last = None
    for url in urls:
        req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                data = resp.read()
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last = exc
            continue
        SRC.mkdir(parents=True, exist_ok=True)
        out.write_bytes(data)
        print(f"fetched {entry['out']}  ({len(data):,} bytes)  {entry['licence']}")
        print(f"        register it by hand in sources/manifest.yaml")
        return True
    print(f"FAILED  {key}: {last}", file=sys.stderr)
    return False


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="fetch openly licensed sources only")
    ap.add_argument("keys", nargs="*", help="catalogue keys to fetch")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--supply", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-download over an existing file")
    a = ap.parse_args()

    if a.list or not (a.keys or a.all or a.supply):
        print("FETCHABLE (open licence, machine may download)\n")
        for key, e in CATALOGUE.items():
            print(f"  {key}")
            print(f"      {e['title']}")
            print(f"      {e['licence']}")
            if e.get("note"):
                print(f"      {e['note']}")
        print()

    if a.supply or a.list or not (a.keys or a.all):
        print("YOU MUST SUPPLY THESE YOURSELF. The machine will not fetch them.\n")
        for title, why in SUPPLY_YOURSELF:
            print(f"  - {title}")
            print(f"      {why}")
        print("\n  Put the file in sources/, run tools/extract_pages.py, then add a")
        print("  record to sources/manifest.yaml with edition, translator, ISBN and")
        print("  licence filled in. Until `edition` stops saying TODO, tools/db.py")
        print("  will refuse to mark any claim citing it verified.\n")
        if not (a.keys or a.all):
            return 0

    keys = list(CATALOGUE) if a.all else a.keys
    bad = [k for k in keys if k not in CATALOGUE]
    for k in bad:
        print(f"REFUSED {k}: not in the catalogue. Nothing outside it is fetchable.",
              file=sys.stderr)
    # Evaluated eagerly: one failed download must not stop the others.
    results = [fetch_one(k, CATALOGUE[k], a.force) for k in keys if k in CATALOGUE]
    return 0 if all(results) and not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
