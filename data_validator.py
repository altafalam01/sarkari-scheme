"""
Data validation — checks schemes.csv for common issues at startup.
"""

import pandas as pd
import os

VALID_STATES = [
    "All", "Andhra Pradesh", "Assam", "Bihar", "Chhattisgarh", "Delhi", "Goa",
    "Gujarat", "Haryana", "Himachal Pradesh", "Jammu and Kashmir", "Jharkhand",
    "Karnataka", "Kerala", "Madhya Pradesh", "Maharashtra", "Odisha", "Punjab",
    "Rajasthan", "Tamil Nadu", "Telangana", "Uttar Pradesh", "Uttarakhand", "West Bengal"
]

def validate_schemes_data(filepath):
    """Returns list of warning strings (empty if no issues)."""
    warnings = []
    
    if not os.path.exists(filepath):
        warnings.append(f"Data file not found: {filepath}")
        return warnings
    
    try:
        df = pd.read_csv(filepath)
    except Exception as e:
        warnings.append(f"Error reading CSV: {e}")
        return warnings
    
    # Check for empty required fields
    required = ["scheme_name", "category_type", "applicable_state", "description", "benefits", "apply_link"]
    for col in required:
        empty_count = df[col].isna().sum()
        if empty_count > 0:
            warnings.append(f"Column '{col}' has {empty_count} empty values")
    
    # Check states
    for state in df["applicable_state"].unique():
        if state not in VALID_STATES:
            warnings.append(f"Unknown state in data: '{state}'")
    
    # Check URLs
    for i, row in df.iterrows():
        link = str(row["apply_link"])
        if not link.startswith("http"):
            warnings.append(f"Row {i} ({row['scheme_name']}): Invalid apply_link '{link}'")
    
    # Check age ranges
    for i, row in df.iterrows():
        min_age = row.get("min_age")
        max_age = row.get("max_age")
        if pd.notna(min_age) and pd.notna(max_age):
            if min_age > max_age:
                warnings.append(f"Row {i} ({row['scheme_name']}): min_age > max_age")
    
    # Check duplicate scheme names
    duplicates = df[df.duplicated("scheme_name", keep=False)]
    if len(duplicates) > 0:
        warnings.append(f"Duplicate scheme names found: {list(duplicates['scheme_name'])}")
    
    return warnings

if __name__ == "__main__":
    warnings = validate_schemes_data("data/schemes.csv")
    if warnings:
        print("⚠️ Data issues found:")
        for w in warnings:
            print(f"  - {w}")
    else:
        print("✅ Data looks good")