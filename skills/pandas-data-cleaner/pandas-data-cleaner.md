---
id: pandas-data-cleaner
name: pandas-data-cleaner
category: uncategorized
tags: []
author: opencode-core
version: 1.0.0
description:
---

---
id: pandas-data-cleaner
file_path: skills/pandas-data-cleaner.md
name: Pandas Data Cleaner
category: data-science
tags: [pandas, data-cleaning, data-science, python, normalization]
author: opencode-core
version: 1.0.0
description: Generate Python Pandas scripts to handle missing values, drop duplicates, and normalize column data types.
---

# Pandas Data Cleaner

## Prerequisites & Dependencies
- Python 3.10+ installed
- Mandatory package: `pip install pandas numpy`
- Optional: `pip install scipy` for advanced statistical imputation, `pip install matplotlib` for data visualization
- JupyterLab or VS Code for interactive development

## Execution Steps
1. Load the dataset: `import pandas as pd; df = pd.read_csv('data.csv')` (or Excel, SQL, JSON)
2. Inspect data quality: `df.info()`, `df.isnull().sum()`, `df.duplicated().sum()`, `df.describe()`
3. Handle missing values: 
   - Numerical columns: fill with median (`df['col'].fillna(df['col'].median(), inplace=True)`) or mean
   - Categorical columns: fill with mode (`df['col'].fillna(df['col'].mode()[0], inplace=True)`) or a placeholder like `'Unknown'`
4. Drop duplicate rows: `df.drop_duplicates(inplace=True)` or keep 'first/last' based on timestamp
5. Normalize column data types: convert strings to lowercase, strip whitespace (`df['col'] = df['col'].str.strip().str.lower()`), convert types using `astype('datetime64[ns]')`, `astype('category')`
6. Rename columns to snake_case or a consistent naming convention: `df.columns = [c.lower().replace(' ', '_') for c in df.columns]`
7. Export the cleaned dataset: `df.to_csv('data_cleaned.csv', index=False)` or `df.to_parquet('data_cleaned.parquet')`

```python
# Example: End-to-end data cleaning script
import pandas as pd
import numpy as np

def clean_data(filepath):
    df = pd.read_csv(filepath)

    # Handle missing values
    for col in df.columns:
        if df[col].dtype in ['float64', 'int64']:
            df[col].fillna(df[col].median(), inplace=True)
        else:
            df[col].fillna('Unknown', inplace=True)

    # Drop exact duplicates
    df.drop_duplicates(inplace=True)

    # Normalize column names to snake_case
    df.columns = [c.lower().replace(' ', '_') for c in df.columns]

    # Convert 'date' column to datetime type
    if 'date' in df.columns:
        df['date'] = pd.to_datetime(df['date'])

    # Export cleaned data
    df.to_csv('data_cleaned.csv', index=False)
    return df

if __name__ == '__main__':
    clean_data('raw_data.csv')
```

```bash
pip install pandas numpy
python clean_data.py
```