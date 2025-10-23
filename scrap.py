"""
Parse a saved eBay search results HTML file (no live requests).

- Expects a file named like: "iPhone 15 Pro Max for sale _ eBay.html"
  placed in the same directory as this script, OR pass a filename:
    python scrap_from_file.py --file "iPhone 15 Pro Max for sale _ eBay.html"

- Extracts: Title, Price, Link, Image Link
- Saves CSV next to the script.

Setup:
  pip install beautifulsoup4 pandas
"""

import argparse
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
from bs4 import BeautifulSoup

# -----------------------------
# Config defaults
# -----------------------------
DEFAULT_BASENAME = "iPhone 15 Pro Max for sale _ eBay"
OUTPUT_CSV = "ebay_iphone15promax_from_saved_html.csv"


def find_local_file(basename: str) -> Optional[Path]:
    """
    Try to locate a local HTML file by common extensions, next to this script.
    """
    here = Path(__file__).resolve().parent
    candidates = [
        here / f"{basename}.html",
        here / f"{basename}.htm",
        # Also allow the exact basename if user saved without an extension
        here / basename,
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return p
    # As a fallback, try fuzzy match (same prefix/similar name)
    for p in here.glob("*.htm*"):
        if basename.lower() in p.stem.lower():
            return p
    return None


def is_challenge(html: str) -> bool:
    """
    Detect common interstitial/challenge text (shouldn't happen in a saved results page,
    but useful if the file saved an interstitial by mistake).
    """
    txt = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
    needles = [
        "checking your browser before you access",
        "attention required",
        "enable javascript and cookies",
        "verify you are a human",
    ]
    return any(n in txt for n in needles)


def parse_items(html: str) -> List[Dict[str, Optional[str]]]:
    """
    Parse listing cards from eBay search HTML.
    Robust selectors to survive layout variants.
    """
    soup = BeautifulSoup(html, "html.parser")

    # Preferred: <li class="s-item"> nodes that actually contain a product link
    nodes = soup.select("li.s-item:has(a.s-item__link)")
    if not nodes:
        # Common wrapper variant
        nodes = soup.select("div.s-item__wrapper.clearfix")
    if not nodes:
        # Very generic fallback
        nodes = [c for c in soup.select(".s-item") if c.select_one(".s-item__title")]

    items: List[Dict[str, Optional[str]]] = []
    for node in nodes:
        title_el = (
            node.select_one(".s-item__title") or
            node.select_one("[data-testid='item-title']") or
            node.select_one("h3")
        )
        link_el = (
            node.select_one("a.s-item__link") or
            node.select_one("a[href*='/itm/']")
        )
        price_el = (
            node.select_one(".s-item__price") or
            node.select_one("[data-testid='item-price']")
        )
        img_el = (
            node.select_one("img.s-item__image-img") or
            node.select_one(".s-item__image-wrapper img") or
            node.select_one("img")
        )

        if not (title_el and link_el):
            continue

        title = title_el.get_text(strip=True)
        href = (link_el.get("href") or "").split("?")[0]
        price = price_el.get_text(strip=True) if price_el else None
        image_url = None
        if img_el:
            image_url = img_el.get("src") or img_el.get("data-src") or img_el.get("data-image-src")

        items.append(
            {
                "Title": title,
                "Price": price,
                "Link": href,
                "Image Link": image_url,
            }
        )
    return items


def main():
    parser = argparse.ArgumentParser(description="Parse saved eBay HTML into CSV.")
    parser.add_argument(
        "--file",
        "-f",
        type=str,
        default="",
        help="Path to the saved eBay HTML file (defaults to finding "
             f'"{DEFAULT_BASENAME}.html" next to this script).'
    )
    parser.add_argument(
        "--out",
        "-o",
        type=str,
        default=OUTPUT_CSV,
        help=f"Output CSV filename (default: {OUTPUT_CSV})"
    )
    args = parser.parse_args()

    # Resolve input file
    if args.file:
        src = Path(args.file).expanduser().resolve()
        if not src.exists():
            raise FileNotFoundError(f"File not found: {src}")
    else:
        src = find_local_file(DEFAULT_BASENAME)
        if not src:
            raise FileNotFoundError(
                "Couldn't find a saved HTML file.\n"
                f"Put \"{DEFAULT_BASENAME}.html\" next to this script, or pass --file PATH"
            )

    print(f"Using saved HTML: {src}")

    html = src.read_text(encoding="utf-8", errors="ignore")

    if is_challenge(html):
        raise RuntimeError(
            "The saved HTML appears to be a bot/challenge page, not search results.\n"
            "Open it in a browser to verify, then save the actual results page."
        )

    items = parse_items(html)
    print(f"Parsed {len(items)} items.")

    if not items:
        # Save a copy for inspection
        debug_copy = src.with_name("debug_saved_page.html")
        debug_copy.write_text(html, encoding="utf-8", errors="ignore")
        print(f"No items parsed. Wrote debug copy to: {debug_copy}")
        return

    df = pd.DataFrame(items)
    out_path = Path(args.out).resolve()
    df.to_csv(out_path, index=False)
    print(f"Saved CSV: {out_path}")


if __name__ == "__main__":
    main()
