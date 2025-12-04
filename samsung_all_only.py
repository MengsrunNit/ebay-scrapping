import re
from pathlib import Path
import pandas as pd

# ======================
# Config
# ======================
SAMSUNG_MODELS = [
    # S22
    "Galaxy S22", "Galaxy S22+", "Galaxy S22 Ultra",
    # S23
    "Galaxy S23", "Galaxy S23+", "Galaxy S23 Ultra",
    # S24
    "Galaxy S24", "Galaxy S24+", "Galaxy S24 Ultra",
    # S25 (future-proof)
    "Galaxy S25", "Galaxy S25+", "Galaxy S25 Ultra",
]

SAMSUNG_DATA_DIR = Path("Samsung Data/galaxy-s-data")
# ^^ change this if your Samsung CSVs live somewhere else


# ======================
# Shared helpers (storage / condition)
# ======================
def extract_storage(title: str) -> str:
    """
    Extracts storage like '128 GB', '256 GB' from a title string.
    Returns 'Unknown' if no storage is found.
    """
    t = str(title)
    m = re.search(r'(\d{2,4})\s?GB\b', t, flags=re.IGNORECASE)
    return f"{m.group(1)} GB" if m else "Unknown"


def extract_condition(title: str) -> str:
    """
    Extracts condition strictly as:
      - Excellent
      - Very Good
      - Good
      - Unknown (if none matched)
    """
    t = str(title).lower()
    if "excellent" in t:
        return "Excellent"
    # check 'very good' before 'good' to avoid misclassifying
    elif "very good" in t:
        return "Very Good"
    elif "good" in t:
        return "Good"
    else:
        return "Unknown"


# ======================
# Samsung-specific model parsing
# ======================

# Examples this should catch:
# - "Samsung Galaxy S22 Ultra 5G"
# - "Samsung Galaxy S23+ 256GB"
# - "Galaxy S24 Plus 256GB"
# - "S25 Ultra"
SAMSUNG_MODEL_RE = re.compile(
    r'(?:Samsung\s+)?(?:Galaxy\s+)?S'          # Samsung / Galaxy optional, S required
    r'((?:[2-9][0-9]?)(?:\s?(?:\+|Plus|Ultra))?)'  # "22", "22+", "22 Plus", "22 Ultra"
    r'\b(?:\s*5G)?',
    flags=re.IGNORECASE
)


def normalize_samsung_model_token(token: str) -> str | None:
    """
    Normalizes tokens like:
      '22', '22+', '22 Plus', '22 Ultra'
    to canonical forms:
      'Galaxy S22', 'Galaxy S22+', 'Galaxy S22 Ultra'
    """
    t = re.sub(r'\s+', ' ', token.strip())
    m = re.match(r'^([0-9]{2})(?:\s?(\+|Plus|Ultra))?$', t, flags=re.IGNORECASE)
    if not m:
        return None

    num = m.group(1)
    suf = (m.group(2) or "").lower()

    if not suf:
        return f"Galaxy S{num}"
    if suf in {"+", "plus"}:
        return f"Galaxy S{num}+"
    if suf == "ultra":
        return f"Galaxy S{num} Ultra"
    return None


def extract_single_samsung_model_or_none(title: str) -> str | None:
    """
    Returns a single normalized Galaxy S model from the title,
    or None if zero or multiple distinct models are detected.
    """
    t = str(title)
    tokens = [m.group(1) for m in SAMSUNG_MODEL_RE.finditer(t)]
    models: list[str] = []

    for tok in tokens:
        canon = normalize_samsung_model_token(tok)
        if canon:
            models.append(canon)

    # Deduplicate while preserving order
    models = list(dict.fromkeys(models))
    return models[0] if len(models) == 1 else None


# ======================
# CSV file resolution for Samsung Galaxy S-series
# ======================
def find_csv_for_samsung_model(directory: Path, model_name: str) -> Path | None:
    """
    Finds a CSV in directory that matches a Samsung Galaxy S model (S22–S25)
    in a case/format-tolerant way.

    Supports:
      - Galaxy S22, S22+, S22 Ultra
      - Handles filenames like:
        'samsung_galaxy_s22_ultra_5g_oct-2025.csv',
        'Galaxy-S23-plus-data.csv', etc.
    """
    m = re.match(
        r'^(?:Samsung\s+)?(?:Galaxy\s+)?S([0-9]{2})(?:\s?(\+|Plus|Ultra))?$',
        model_name,
        flags=re.IGNORECASE
    )
    if not m:
        raise ValueError(f"Model name not recognized: {model_name}")

    num = m.group(1)
    suf = (m.group(2) or "").lower()

    # Tokens that should appear (in order) in the filename
    tokens: list[str] = ["(?:samsung|galaxy)", f"s{num}"]
    if suf in {"+", "plus"}:
        # allow either '+' or 'plus' in the filename
        tokens.append("(?:\\+|plus)")
    elif suf == "ultra":
        tokens.append("ultra")

    # Build a loose ordered pattern: .*token1.*token2.*...\.csv
    pattern_str = r""
    for tok in tokens:
        # treat regex tokens vs literal
        if tok.startswith("(?:"):
            pattern_str += r".*" + tok
        else:
            pattern_str += r".*" + re.escape(tok)
    pattern_str += r".*\.csv$"

    pattern = re.compile(pattern_str, re.IGNORECASE)

    candidates = sorted(
        [p for p in directory.glob("*.csv") if pattern.search(p.name)]
    )
    return candidates[0] if candidates else None


# ======================
# Cleaning / filtering for a specific Samsung model
# ======================
def clean_and_filter_for_samsung(df: pd.DataFrame, target_model: str) -> pd.DataFrame:
    """
    - Adds Storage, Condition, PartsOnly, Sold Date (parsed) columns
    - Extracts detected Samsung model from each Title
    - Filters rows down to only the target_model
    """
    tmp = df.copy()

    # Basic columns
    tmp["Title"] = tmp["Title"].astype(str)
    tmp["Storage"] = tmp["Title"].apply(extract_storage)
    tmp["Condition"] = tmp["Title"].apply(extract_condition)
    tmp["PartsOnly"] = tmp["Title"].str.contains(
        "Parts Only", case=False, regex=False
    )

    # Convert "Sold Oct 21, 2025" -> datetime64
    if "Sold Date" in tmp.columns:
        tmp["Sold Date"] = pd.to_datetime(
            tmp["Sold Date"]
            .astype(str)
            .str.replace(r"^\s*Sold\s+", "", regex=True)  # remove 'Sold '
            .str.replace(r"\s{2,}", " ", regex=True)      # collapse double spaces
            .str.strip(),
            errors="coerce",
        )

    # Extract detected Samsung model
    tmp["Model"] = tmp["Title"].apply(extract_single_samsung_model_or_none)
    tmp = tmp[tmp["Model"].notna()].copy()

    # Filter to the requested model
    flag_col = (
        target_model.replace(" ", "_")
        .replace("+", "Plus")
    )
    tmp[flag_col] = (tmp["Model"] == target_model)
    tmp = tmp[tmp[flag_col]].copy()

    return tmp


def export_samsung_model_subset(directory: Path, model_name: str) -> Path | None:
    """
    For a given Samsung model:
      - find a matching CSV
      - clean & filter rows down to just that model
      - write out `<canonical_name>_only.csv`
    """
    src = find_csv_for_samsung_model(directory, model_name)
    if src is None:
        print(f"❌ No CSV found for {model_name} in {directory}")
        return None

    print(f"📄 Using file: {src.name}")
    df = pd.read_csv(src)
    subset = clean_and_filter_for_samsung(df, model_name)

    out_name = (
        model_name.lower()
        .replace(" ", "_")
        .replace("+", "plus")
        + "_only.csv"
    )
    out_path = directory / out_name
    subset.to_csv(out_path, index=False)
    print(f"✅ {model_name}: Exported {len(subset)} rows -> {out_path.name}")
    return out_path


# ======================
# Run for all configured Samsung models
# ======================
if __name__ == "__main__":
    for model in SAMSUNG_MODELS:
        export_samsung_model_subset(SAMSUNG_DATA_DIR, model)
