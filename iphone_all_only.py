import re
from pathlib import Path
import pandas as pd

# ======================
# Config
# ======================
IPHONE_MODELS = [
    "iPhone 12", "iPhone 12 Pro", "iPhone 12 Pro Max",
    "iPhone 13", "iPhone 13 Pro", "iPhone 13 Pro Max",
    "iPhone 14", "iPhone 14 Pro", "iPhone 14 Pro Max",
    "iPhone 15", "iPhone 15 Pro", "iPhone 15 Pro Max",
    "iPhone 16", "iPhone 16 Pro", "iPhone 16 Pro Max",
    "iPhone 17", "iPhone 17 Pro", "iPhone 17 Pro Max",
]

# Set to the directory that contains your iPhone CSVs
IPHONE_DIR = Path("/home/mengsrun/Desktop/scraper/ebay-scrapping/Iphone Data")

# ======================
# Helpers
# ======================

def find_csv_for_iphone(directory: Path, model_name: str) -> Path | None:
    """
    Find a CSV for 'iPhone N', 'iPhone N Pro', or 'iPhone N Pro Max' (case/format tolerant).
    Ensures base models won't match 'Pro/Pro Max' files by using negative lookaheads where needed.
    """
    m = re.match(r'^iPhone\s+([0-9]{2})(?:\s+(Pro)(?:\s+Max)?)?$', model_name, flags=re.IGNORECASE)
    if not m:
        raise ValueError(f"Model name not recognized: {model_name}")
    num = m.group(1)
    is_pro = bool(m.group(2))
    is_pro_max = model_name.strip().lower().endswith("pro max")

    if is_pro_max:
        # Must include 'pro' and 'max'
        pattern = re.compile(rf'\biphone[\s_-]*{num}[\s_-]*pro[\s_-]*max\b.*\.csv$', re.IGNORECASE)
    elif is_pro:
        # Must include 'pro' but NOT 'max'
        pattern = re.compile(rf'\biphone[\s_-]*{num}[\s_-]*pro\b(?![\s_-]*max).*\.csv$', re.IGNORECASE)
    else:
        # Base: must be just the number, NOT followed by pro/pro max
        pattern = re.compile(rf'\biphone[\s_-]*{num}\b(?![\s_-]*(?:pro|max)).*\.csv$', re.IGNORECASE)

    candidates = sorted([p for p in directory.glob('*.csv') if pattern.search(p.name)])
    return candidates[0] if candidates else None


# Reuse your robust storage/condition helpers
def extract_storage(title: str) -> str:
    m = re.search(r'(\d{2,4})\s?GB\b', title, flags=re.IGNORECASE)
    return f"{m.group(1)} GB" if m else "Unknown"

def extract_condition(title: str) -> str:
    if 'Excellent' in title:
        return 'Excellent'
    elif 'Very' in title:
        return 'Very Good'
    elif 'Good' in title:
        return 'Good'
    else:
        return 'Unknown'


# ---- iPhone model extraction from TITLE ----
# Order matters: match 'Pro Max' before 'Pro'
IPHONE_MODEL_RE = re.compile(
    r'(?:Apple\s+)?iPhone\s+((?:[1-9][0-9]?)(?:\s?(?:Pro\s+Max|Pro|Plus|Mini|Max))?)\b',
    flags=re.IGNORECASE
)

def normalize_iphone_token(token: str) -> str | None:
    """
    Canonicalize captured token like:
      '15 pro max' -> 'iPhone 15 Pro Max'
      '14 pro'     -> 'iPhone 14 Pro'
      '13'         -> 'iPhone 13'
    """
    t = re.sub(r'\s+', ' ', token.strip())
    m = re.match(r'^([1-9][0-9]?)(?:\s?(Pro\s+Max|Pro|Plus|Mini|Max))?$', t, flags=re.IGNORECASE)
    if not m:
        return None
    num = m.group(1)
    suf = (m.group(2) or '').strip().lower()
    if not suf:
        return f'iPhone {num}'
    if suf == 'pro max':
        return f'iPhone {num} Pro Max'
    if suf == 'pro':
        return f'iPhone {num} Pro'
    if suf == 'plus':
        return f'iPhone {num} Plus'
    if suf == 'mini':
        return f'iPhone {num} Mini'
    if suf == 'max':
        # some sellers write 'iPhone 12 Max' (rare) -> keep as 'Max'
        return f'iPhone {num} Max'
    return None

def extract_single_iphone_model_or_none(title: str) -> str | None:
    tokens = [m.group(1) for m in IPHONE_MODEL_RE.finditer(title)]
    models = []
    for tok in tokens:
        canon = normalize_iphone_token(tok)
        if canon:
            models.append(canon)
    models = list(dict.fromkeys(models))  # dedupe, keep order
    return models[0] if len(models) == 1 else None  # only if exactly one clear model


def clean_and_filter_for_iphone(df: pd.DataFrame, target_model: str) -> pd.DataFrame:
    """
    Apply the pipeline and return only rows where Model == target_model.
    Also converts 'Sold Date' into a datetime column 'Sold Date Parsed'.
    """
    tmp = df.copy()

    # Basic columns
    tmp['Storage']   = tmp['Title'].apply(extract_storage)
    tmp['Condition'] = tmp['Title'].apply(extract_condition)
    tmp['PartsOnly'] = tmp['Title'].str.contains('Parts Only', case=False, regex=False)

    # Parse a single, unambiguous iPhone model
    tmp['Model'] = tmp['Title'].apply(extract_single_iphone_model_or_none)

    # Keep only rows with exactly one model
    tmp = tmp[tmp['Model'].notna()].copy()

    # Convert "Sold Date" like "Sold Oct 21, 2025" -> datetime
    # Convert "Sold Date" like "Sold Oct 21, 2025" -> datetime
    if 'Sold Date' in tmp.columns:
        tmp['Sold Date'] = (
            pd.to_datetime(
                tmp['Sold Date']
                .astype(str)
                .str.replace(r'^\s*Sold\s+', '', regex=True)
                .str.strip(),
                errors='coerce'
            )
        )


    # Filter to the requested model
    flag_col = target_model.replace(' ', '_')
    tmp[flag_col] = (tmp['Model'].str.casefold() == target_model.casefold())
    tmp = tmp[tmp[flag_col]].copy()

    return tmp


def export_iphone_subset(directory: Path, model_name: str) -> Path | None:
    """
    Load the model-specific iPhone CSV, run the pipeline, and export an '_only.csv' file.
    """
    src = find_csv_for_iphone(directory, model_name)
    if src is None:
        print(f"❌ No CSV found for {model_name} in {directory}")
        return None

    print(f"📄 Using file: {src.name}")
    df = pd.read_csv(src)

    subset = clean_and_filter_for_iphone(df, model_name)

    out_name = f"{model_name.lower().replace(' ', '_')}_only.csv"
    out_path = directory / out_name
    subset.to_csv(out_path, index=False)

    print(f"✅ {model_name}: Exported {len(subset)} rows -> {out_path.name}")
    return out_path

# ======================
# Run for all configured iPhone models
# ======================
for model in IPHONE_MODELS:
    export_iphone_subset(IPHONE_DIR, model)
