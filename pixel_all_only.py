import re
from pathlib import Path
import pandas as pd

# ======================
# Config
# ======================
MODELS = [
    "Pixel 6", "Pixel 6 Pro", 
    "Pixel 7", "Pixel 7 Pro",
    "Pixel 8", "Pixel 8 Pro",
    "Pixel 9", "Pixel 9 Pro", "Pixel 9 Pro XL",
    "Pixel 10", "Pixel 10 Pro", "Pixel 10 Pro XL"
]

DATA_DIR = Path("/home/mengsrun/Desktop/scraper/ebay-scrapping/Google Pixel/Pixel_Data")

# ======================
# Helpers
# ======================
def find_csv_for_model(directory: Path, model_name: str) -> Path | None:
    """
    Finds a CSV in directory that matches model_name in a case/format-tolerant way.
    Supports Pixel N, N Pro, N XL, N Pro XL variants.
    """
    m = re.match(
        r'^Pixel\s+([0-9]{1,2})(?:\s+(Pro|XL)(?:\s+XL)?)?$', 
        model_name, flags=re.IGNORECASE
    )
    if not m:
        raise ValueError(f"Model name not recognized: {model_name}")
    num = m.group(1)
    model_tokens = model_name.replace("Pixel", "").strip().split()
    pattern = re.compile(
        r'\bpixel' + ''.join([rf'[\s_-]*{re.escape(tok)}' for tok in model_tokens]) + r'\b.*\.csv$',
        re.IGNORECASE
    )

    candidates = sorted([p for p in directory.glob('*.csv') if pattern.search(p.name)])
    return candidates[0] if candidates else None

# Robust storage extraction
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

# Capture Google Pixel model tokens (6–10, Pro, XL, Pro XL)
MODEL_RE = re.compile(
    r'(?:Google\s+)?Pixel\s+((?:[1-9][0-9]?)(?:\s?(?:Pro|XL|Pro XL|a))?)\b(?:\s*5G)?',
    flags=re.IGNORECASE
)

def normalize_model_token(token: str) -> str | None:
    t = re.sub(r'\s+', ' ', token.strip())
    m = re.match(r'^([1-9][0-9]?)(?:\s?(Pro|XL|Pro XL|a))?$', t, flags=re.IGNORECASE)
    if not m:
        return None
    num = m.group(1)
    suf = (m.group(2) or '').lower()
    if not suf:
        return f'Pixel {num}'
    if suf == 'pro':
        return f'Pixel {num} Pro'
    if suf == 'xl':
        return f'Pixel {num} XL'
    if suf == 'pro xl':
        return f'Pixel {num} Pro XL'
    if suf == 'a':
        return f'Pixel {num}a'
    return None

def extract_single_model_or_none(title: str) -> str | None:
    tokens = [m.group(1) for m in MODEL_RE.finditer(title)]
    models = []
    for tok in tokens:
        canon = normalize_model_token(tok)
        if canon:
            models.append(canon)
    models = list(dict.fromkeys(models))
    return models[0] if len(models) == 1 else None

def clean_and_filter_for_model(df: pd.DataFrame, target_model: str) -> pd.DataFrame:
    tmp = df.copy()

    # Basic columns
    tmp['Storage']   = tmp['Title'].apply(extract_storage)
    tmp['Condition'] = tmp['Title'].apply(extract_condition)
    tmp['PartsOnly'] = tmp['Title'].str.contains('Parts Only', case=False, regex=False)

    # ✅ Convert "Sold Oct 21, 2025" → datetime64
    if 'Sold Date' in tmp.columns:
        tmp['Sold Date'] = (
            pd.to_datetime(
                tmp['Sold Date']
                .astype(str)
                .str.replace(r'^\s*Sold\s+', '', regex=True)  # remove 'Sold '
                .str.replace(r'\s{2,}', ' ', regex=True)      # collapse double spaces
                .str.strip(),
                errors='coerce'
            )
        )

    # Extract a single model
    tmp['Model'] = tmp['Title'].apply(extract_single_model_or_none)
    tmp = tmp[tmp['Model'].notna()].copy()

    # Filter to the requested model
    flag_col = target_model.replace(' ', '_')
    tmp[flag_col] = (tmp['Model'] == target_model)
    tmp = tmp[tmp[flag_col]].copy()

    return tmp

def export_model_subset(directory: Path, model_name: str) -> Path | None:
    src = find_csv_for_model(directory, model_name)
    if src is None:
        print(f"❌ No CSV found for {model_name} in {directory}")
        return None
    print(f"📄 Using file: {src.name}")
    df = pd.read_csv(src)
    subset = clean_and_filter_for_model(df, model_name)
    out_name = f"{model_name.lower().replace(' ', '_')}_only.csv"
    out_path = directory / out_name
    subset.to_csv(out_path, index=False)
    print(f"✅ {model_name}: Exported {len(subset)} rows -> {out_path.name}")
    return out_path

# ======================
# Run for all configured models
# ======================
for model in MODELS:
    export_model_subset(DATA_DIR, model)
