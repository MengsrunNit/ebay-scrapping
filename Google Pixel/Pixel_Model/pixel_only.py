import re
from pathlib import Path
import pandas as pd

# ======================
# Config
# ======================
# Models you want to process. Add/remove freely.
MODELS = ["Pixel 7"]

# Directory containing your CSV files (use Path.cwd() for current folder)
DATA_DIR = Path("/home/mengsrun/Desktop/scraper/ebay-scrapping/")

# ======================
# Helpers
# ======================
def find_csv_for_model(directory: Path, model_name: str) -> Path | None:
    """
    Locate a CSV in `directory` that matches the given model name in a case/format-tolerant way.
    Accepts variations like spaces/underscores/dashes, any extra suffix/prefix.
    """
    # Build a robust regex for the filename (case-insensitive)
    # e.g. Pixel 7 Pro -> \bpixel[\s_-]*7[\s_-]*pro\b.*\.csv
    m = re.match(r'^Pixel\s+([0-9]{1,2})\s+Pro$', model_name, flags=re.IGNORECASE)
    if not m:
        raise ValueError(f"Model name not recognized: {model_name}")
    num = m.group(1)

    pattern = re.compile(rf'\bpixel[\s_-]*{num}[\s_-]*pro\b.*\.csv$', re.IGNORECASE)

    # Scan directory for CSVs and return the first match (sorted for determinism)
    candidates = sorted([p for p in directory.glob('*.csv') if pattern.search(p.name)])
    return candidates[0] if candidates else None

# Robust storage: first occurrence like "128GB", "256 GB"
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

# Capture Google Pixel model tokens (6, 7, 7a, 7 Pro, 9, 10 Pro, etc.)
MODEL_RE = re.compile(
    r'(?:Google\s+)?Pixel\s+((?:[1-9][0-9]?)(?:\s?(?:Pro|XL|a))?)\b(?:\s*5G)?',
    flags=re.IGNORECASE
)

def normalize_model_token(token: str) -> str | None:
    t = re.sub(r'\s+', ' ', token.strip())
    m = re.match(r'^([1-9][0-9]?)(?:\s?(Pro|XL|a))?$', t, flags=re.IGNORECASE)
    if not m:
        return None
    num = m.group(1)
    suf = m.group(2)
    if not suf:
        return f'Pixel {num}'
    suf_l = suf.lower()
    if suf_l == 'pro':
        return f'Pixel {num} Pro'
    if suf_l == 'xl':
        return f'Pixel {num} XL'
    if suf_l == 'a':
        return f'Pixel {num}a'
    return None

def extract_single_model_or_none(title: str) -> str | None:
    tokens = [m.group(1) for m in MODEL_RE.finditer(title)]
    models = []
    for tok in tokens:
        canon = normalize_model_token(tok)
        if canon:
            models.append(canon)
    # dedupe, keep order
    models = list(dict.fromkeys(models))
    return models[0] if len(models) == 1 else None  # None if 0 or >1 models

def clean_and_filter_for_model(df: pd.DataFrame, target_model: str) -> pd.DataFrame:
    """
    Apply your existing pipeline and return only rows where Model == target_model.
    """
    tmp = df.copy()

    # Basic columns
    tmp['Storage']   = tmp['Title'].apply(extract_storage)
    tmp['Condition'] = tmp['Title'].apply(extract_condition)
    tmp['PartsOnly'] = tmp['Title'].str.contains('Parts Only', case=False, regex=False)

    # Extract a single unambiguous model
    tmp['Model'] = tmp['Title'].apply(extract_single_model_or_none)

    # Keep only rows with exactly one model detected
    tmp = tmp[tmp['Model'].notna()].copy()

    # Flag and filter
    flag_col = target_model.replace(' ', '_')
    tmp[flag_col] = (tmp['Model'] == target_model)
    tmp = tmp[tmp[flag_col]].copy()

    return tmp

def export_model_subset(directory: Path, model_name: str) -> Path | None:
    """
    Load the model-specific CSV, run the pipeline, and export an '_only.csv' file.
    Returns the output path or None if source file not found.
    """
    src = find_csv_for_model(directory, model_name)
    if src is None:
        print(f"❌ No CSV found for {model_name} in {directory}")
        return None

    print(f"📄 Using file: {src.name}")
    df = pd.read_csv(src)

    subset = clean_and_filter_for_model(df, model_name)

    out_name = f"{model_name.lower().replace(' ', '_')}_only.csv"  # e.g., pixel_7_pro_only.csv
    out_path = directory / out_name
    subset.to_csv(out_path, index=False)

    print(f"✅ {model_name}: Exported {len(subset)} rows -> {out_path.name}")
    return out_path

# ======================
# Run for all configured models
# ======================
for model in MODELS:
    export_model_subset(DATA_DIR, model)
