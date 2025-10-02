# lib/supa.py
import pandas as pd
from supabase import create_client

def get_client(url, key):
    return create_client(url, key)

def read_full_table(client, table: str) -> pd.DataFrame:
    res = client.table(table).select("*").execute()
    return pd.DataFrame(res.data or [])

def coerce_fr_numbers(df: pd.DataFrame, cols: list) -> pd.DataFrame:
    for c in cols:
        if c in df.columns:
            df[c] = (
                df[c].astype(str)
                .str.replace(" ", "", regex=False)
                .str.replace(",", ".", regex=False)
                .replace({"-": None, "": None})
            )
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df

def coerce_date(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce", dayfirst=True)
    return df
