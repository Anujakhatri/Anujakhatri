import json
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

from lxml import etree

# Repo root = parent of this script (script lives at repo root for the workflow).
REPO = Path(__file__).resolve().parent
SVG_NS = "http://www.w3.org/2000/svg"
STATS_FILE = REPO / "cache" / "stats.json"

# Live stats come from cache/stats.json (written by update.py in CI).
DEFAULT_STATS = {"repos": 17, "stars": 4, "followers": 15, "starred": 0, "commits": 0, "code_lines": 0}


def load_stats() -> dict:
    if not STATS_FILE.exists():
        return dict(DEFAULT_STATS)
    try:
        data = json.loads(STATS_FILE.read_text(encoding="utf-8"))
        return {
            "repos":     int(data.get("repos",     DEFAULT_STATS["repos"])),
            "stars":     int(data.get("stars",     DEFAULT_STATS["stars"])),
            "followers": int(data.get("followers", DEFAULT_STATS["followers"])),
            "starred":   int(data.get("starred",   DEFAULT_STATS["starred"])),
            "commits":   int(data.get("commits",   DEFAULT_STATS["commits"])),
            "code_lines": int(data.get("code_lines", DEFAULT_STATS["code_lines"])),
        }
    except (json.JSONDecodeError, KeyError, ValueError):
        return dict(DEFAULT_STATS)


STATS = load_stats()


KOMAREV_URL = (
    "https://komarev.com/ghpvc/"
    "?username=anujakhatri&label=Profile%20views&color=0e75b6&style=flat"
)
CACHE_FILE        = REPO / ".profile_views_cache.json"
CACHE_TTL_SECONDS = 24 * 60 * 60   # 24h


def fetch_profile_views() -> str:
    """Same fallback chain as before: cache < TTL, live fetch, stale cache, '-'."""
    now = time.time()

    # 1) Try cache first.
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            if (now - data.get("fetched_at", 0)) < CACHE_TTL_SECONDS:
                return data["count"]
        except (json.JSONDecodeError, KeyError):
            pass

    # 2) Fetch fresh.
    try:
        with urllib.request.urlopen(KOMAREV_URL, timeout=10) as resp:
            svg_bytes = resp.read()
        root = ET.fromstring(svg_bytes)
        numeric_texts = [
            (t.text or "").strip()
            for t in root.iter(f"{{{SVG_NS}}}text")
            if (t.text or "").strip() and any(c.isdigit() for c in (t.text or ""))
        ]
        if numeric_texts:
            count = numeric_texts[-1]
            CACHE_FILE.write_text(
                json.dumps({"count": count, "fetched_at": now}, indent=2),
                encoding="utf-8",
            )
            print(f"[fetch_profile_views] live fetch OK -> count={count!r}")
            return count
        print("[fetch_profile_views] live fetch returned SVG with no numeric <text> elements")
    except Exception as e:
        print(f"[fetch_profile_views] live fetch FAILED: {type(e).__name__}: {e}")

    # 3) Stale-cache fallback.
    if CACHE_FILE.exists():
        try:
            data = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
            return data.get("count", "-")
        except (json.JSONDecodeError, KeyError):
            pass

    return "-"


PADDED_WIDTHS = {
    "repos_value":       6,    # "    17" -> 4 leading spaces + 2 digits
    "followers_value":   0,    # "15" - no pad in current SVG
    "starred_value":     6,    # "     0" -> 5 leading spaces + 1 digit, matches repos visual width
    "commits_value":     6,
    "code_lines_value":  6,
    "profile_views_text": 0,   # full badge string; no padding needed
}


def _pad_to_width(raw: str, target_width: int) -> str:
    if len(raw) >= target_width:
        return raw
    return " " * (target_width - len(raw)) + raw


def apply_value_update(svg_path: Path, value_map: dict) -> int:
    """
    Open svg_path, find tspans by id, replace .text with padded values.
    Leaves everything else (including all other tspans) untouched.
    Returns the number of ids that were successfully updated.
    """
    parser = etree.XMLParser(remove_blank_text=False)
    tree = etree.parse(str(svg_path), parser)
    root = tree.getroot()

    updated = 0
    for tspan_id, new_value in value_map.items():
        target_width = PADDED_WIDTHS.get(tspan_id, 0)
        raw = str(new_value)
        padded = _pad_to_width(raw, target_width)
        if len(raw) > target_width and target_width > 0:
            print(
                f"  WARN: {svg_path.name}: {tspan_id!r} value {raw!r} is "
                f"wider than expected pad width {target_width} - manual re-tune needed"
            )

        # XPath: any element with @id=tspan_id, anywhere in the tree.
        matches = root.xpath(f".//*[@id='{tspan_id}']")
        if not matches:
            print(f"  WARN: {svg_path.name}: no element found with id={tspan_id!r}")
            continue
        for el in matches:
            old = el.text
            el.text = padded
            print(
                f"  {svg_path.name}: {tspan_id!r} "
                f"{old!r} -> {padded!r}"
            )
            updated += 1

    tree.write(
        str(svg_path),
        encoding="utf-8",
        xml_declaration=True,
    )
    return updated


def main():
    print(f"Stats used: {STATS}")
    profile_views = fetch_profile_views()
    print(f"Profile views: {profile_views}")

    value_map = {
        "repos_value":     STATS["repos"],
        "followers_value": STATS["followers"],
        "starred_value":   STATS["starred"],
        "commits_value":   STATS["commits"],
        "code_lines_value": STATS["code_lines"],
        "profile_views_text": f"· {profile_views} profile views",
    }

    for svg_name in ("dark.svg", "light.svg"):
        svg_path = REPO / svg_name
        if not svg_path.exists():
            print(f"  WARN: {svg_path} not found, skipping")
            continue
        n = apply_value_update(svg_path, value_map)
        print(f"  Updated {n} id(s) in {svg_path}")


if __name__ == "__main__":
    main()
