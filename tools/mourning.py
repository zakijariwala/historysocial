"""Is today inside the mourning window?

    python tools/mourning.py                 # today
    python tools/mourning.py 2026-07-16      # any Gregorian date
    python tools/mourning.py --dates         # the wafat list and where it comes from

The window is Muharram 1 to Safar 30, plus the wafat dates, per Sistani's
published calendar.

THE HONEST LIMIT. The Hijri date computed here uses the tabular (arithmetic)
Islamic calendar. Sistani's calendar is set by sighting, so it can differ from
the tabular date by a day, occasionally two. This tool therefore ADVISES and
never flips a post on its own: near a boundary it says so and tells you to
check the published calendar. Getting Muharram 1 wrong by a day would put an
ornamented cover on the wrong morning.

The wafat dates in tokens/mourning.yaml are left for you to fill from the
published calendar. This file will not guess them, and it will not silently
treat an unfilled list as an empty one: it says how many are missing.
"""

from __future__ import annotations

import argparse
import datetime as dt
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
DATES = ROOT / "tokens" / "mourning.yaml"

MONTHS = ["Muharram", "Safar", "Rabi' al-awwal", "Rabi' al-thani",
          "Jumada al-ula", "Jumada al-akhira", "Rajab", "Sha'ban", "Ramadan",
          "Shawwal", "Dhu al-Qa'da", "Dhu al-Hijja"]


def to_hijri(date: dt.date) -> tuple[int, int, int]:
    """Gregorian -> tabular Hijri (year, month, day). Arithmetic, not sighted."""
    jd = date.toordinal() + 1721425          # proleptic Gregorian -> Julian Day
    days = jd - 1948440 + 10632
    n = (days - 1) // 10631
    days = days - 10631 * n + 354
    j = ((10985 - days) // 5316) * ((50 * days) // 17719) + \
        (days // 5670) * ((43 * days) // 15238)
    days = days - ((30 - j) // 15) * ((17719 * j) // 50) - \
        (j // 16) * ((15238 * j) // 43) + 29
    month = (24 * days) // 709
    day = days - (709 * month) // 24
    year = 30 * n + j - 30
    return year, month, day


def load_dates() -> dict:
    if not DATES.exists():
        return {}
    return yaml.safe_load(DATES.read_text(encoding="utf-8")) or {}


def status(date: dt.date) -> dict:
    year, month, day = to_hijri(date)
    in_window = month in (1, 2)
    boundary = (month == 12 and day >= 28) or (month == 2 and day >= 28) or \
               (month == 1 and day <= 2) or (month == 3 and day <= 2)

    doc = load_dates()
    wafat = doc.get("wafat") or []
    filled = [w for w in wafat
              if not str(w.get("hijri", "")).upper().startswith("TODO")]
    hit = next((w for w in filled
                if w.get("hijri") == f"{month}-{day}"), None)

    return {
        "gregorian": date.isoformat(),
        "hijri": f"{day} {MONTHS[month - 1]} {year}",
        "mourning": bool(in_window or hit),
        "reason": ("Muharram 1 to Safar 30" if in_window else
                   (f'wafat: {hit["name"]}' if hit else "outside the window")),
        "boundary": boundary,
        "wafat_total": len(wafat),
        "wafat_filled": len(filled),
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="mourning window check")
    ap.add_argument("date", nargs="?", help="YYYY-MM-DD, default today")
    ap.add_argument("--dates", action="store_true", help="list the wafat dates")
    a = ap.parse_args()

    if a.dates:
        doc = load_dates()
        print(doc.get("note", "").strip() or "(no note in tokens/mourning.yaml)")
        for w in doc.get("wafat") or []:
            print(f'  {str(w.get("hijri")):<10} {w.get("name")}')
        return 0

    date = dt.date.fromisoformat(a.date) if a.date else dt.date.today()
    st = status(date)
    print(f'{st["gregorian"]}  =  {st["hijri"]} (tabular)')
    print(f'mourning: {"YES" if st["mourning"] else "no"}  ({st["reason"]})')
    if st["boundary"]:
        print("NEAR A BOUNDARY. The tabular date can differ from Sistani's "
              "published calendar by a day. Check it before you post.")
    missing = st["wafat_total"] - st["wafat_filled"]
    if missing:
        print(f"{missing} wafat dates in tokens/mourning.yaml are still TODO, so "
              f"this answer covers Muharram and Safar only.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
