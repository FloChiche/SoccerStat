import os
from typing import Tuple
import pandas as pd


def _extract_primary_position(position_value: str) -> str:
    """
    Return the primary position string. Some rows contain multiple positions like "MF,FW".
    In that case, we keep the first token only.
    """
    if not isinstance(position_value, str) or not position_value:
        return ""
    return position_value.split(",")[0].strip()


def _extract_country_code(nation_value: str) -> Tuple[str, str]:
    """
    Nation column examples look like "eng ENG" or "fr FRA" (language + FIFA code).
    We return a tuple of (language_code, fifa_code). If parsing fails, returns (value, value).
    """
    if not isinstance(nation_value, str) or not nation_value:
        return ("", "")
    parts = nation_value.split()
    if len(parts) >= 2:
        return (parts[0], parts[1])
    return (nation_value, nation_value)


def _extract_competition_name(comp_value: str) -> str:
    """
    Competition column examples: "eng Premier League", "es La Liga", "de Bundesliga",
    "it Serie A", "fr Ligue 1". We keep the league name part after the first space.
    """
    if not isinstance(comp_value, str) or not comp_value:
        return ""
    parts = comp_value.split(" ", 1)
    if len(parts) == 2:
        return parts[1].strip()
    return comp_value


def compute_rate(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """
    Safe division to compute per-match or per-90 rates with zero-denominator protection.
    """
    denom = denominator.replace({0: pd.NA})
    return (numerator / denom).fillna(0)


def load_clean_data(csv_path: str) -> pd.DataFrame:
    """
    Load and clean the player dataset.

    Steps:
    - Read CSV
    - Drop duplicates
    - Basic NA handling (keep rows with essential fields)
    - Normalize Nation into `NationLang` and `NationCode`
    - Normalize Pos to `PrimaryPos`
    - Normalize Comp to simplified league name `League`
    - Add convenience metrics:
        * goals_per_match = Gls / MP
        * assists_per_match = Ast / MP
        * ga_per_match = (G+A) / MP
        * goals_per_90 = Gls_90 (if present) else Gls / 90s
        * assists_per_90 = Ast_90 (if present) else Ast / 90s
        * minutes_per_match = Min / MP
    """
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"CSV not found at {csv_path}")

    df = pd.read_csv(csv_path)

    # De-duplicate
    df = df.drop_duplicates().copy()

    # Keep essential columns if present
    essential = [
        "Player",
        "Nation",
        "Pos",
        "Squad",
        "Comp",
        "MP",
        "Min",
        "Gls",
        "Ast",
        "G+A",
        "90s",
    ]
    missing_essential = [c for c in essential if c not in df.columns]
    if missing_essential:
        # Not all columns are mandatory (e.g., G+A or 90s might be absent in some variations)
        # We will proceed but compute only available metrics.
        pass

    # Basic NA cleanup: For key numeric fields, fill NA with 0 to keep rows usable in charts
    numeric_defaults = {
        col: 0 for col in [c for c in ["MP", "Min", "Gls", "Ast", "G+A", "90s"] if c in df.columns]
    }
    df = df.fillna(value=numeric_defaults)

    # Nation parsing
    if "Nation" in df.columns:
        nation_parsed = df["Nation"].apply(_extract_country_code)
        df["NationLang"] = nation_parsed.apply(lambda t: t[0])
        df["NationCode"] = nation_parsed.apply(lambda t: t[1])

    # Position primary
    if "Pos" in df.columns:
        df["PrimaryPos"] = df["Pos"].apply(_extract_primary_position)

    # League name
    if "Comp" in df.columns:
        df["League"] = df["Comp"].apply(_extract_competition_name)

    # Derived metrics
    if {"Gls", "MP"}.issubset(df.columns):
        df["goals_per_match"] = compute_rate(df["Gls"], df["MP"]) 
    if {"Ast", "MP"}.issubset(df.columns):
        df["assists_per_match"] = compute_rate(df["Ast"], df["MP"]) 
    if {"G+A", "MP"}.issubset(df.columns):
        df["ga_per_match"] = compute_rate(df["G+A"], df["MP"]) 

    # Per 90s
    if "Gls_90" in df.columns:
        df["goals_per_90"] = df["Gls_90"]
    elif {"Gls", "90s"}.issubset(df.columns):
        df["goals_per_90"] = compute_rate(df["Gls"], df["90s"]) 

    if "Ast_90" in df.columns:
        df["assists_per_90"] = df["Ast_90"]
    elif {"Ast", "90s"}.issubset(df.columns):
        df["assists_per_90"] = compute_rate(df["Ast"], df["90s"]) 

    if {"Min", "MP"}.issubset(df.columns):
        df["minutes_per_match"] = compute_rate(df["Min"], df["MP"]) 

    return df


