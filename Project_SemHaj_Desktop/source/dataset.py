"""Чтение и проверка выгрузок вакансий без объединения снимков."""
from pathlib import Path
import numpy as np
import pandas as pd

REQUIRED = {"vacancy_id", "name", "area_name", "category"}

def load_dataset(path: Path) -> tuple[pd.DataFrame, dict]:
    """Прочитать CSV, удалить дубли и привести измеряемые поля."""
    raw = pd.read_csv(path, low_memory=False)
    missing = REQUIRED - set(raw.columns)
    if missing:
        raise ValueError("Нет обязательных столбцов: " + ", ".join(sorted(missing)))
    raw_count = len(raw)
    data = raw.dropna(subset=["vacancy_id", "name", "area_name", "category"]).copy()
    data["vacancy_id"] = data["vacancy_id"].astype(str).str.replace(r"\.0$", "", regex=True)
    if "snapshot_date" in data:
        data = data.sort_values("snapshot_date", na_position="first")
    data = data.drop_duplicates("vacancy_id", keep="last")
    for col in ["salary_from_rub", "salary_to_rub", "responses_count", "total_responses_count"]:
        data[col] = pd.to_numeric(data.get(col, pd.Series(index=data.index, dtype=float)), errors="coerce")
        data.loc[~np.isfinite(data[col]) | (data[col] < 0), col] = np.nan
    data["salary"] = data[["salary_from_rub", "salary_to_rub"]].mean(axis=1)
    monthly = data.get("salary_mode", pd.Series("MONTH", index=data.index)).eq("MONTH")
    data.loc[~monthly | (data["salary"] <= 0), "salary"] = np.nan
    for col in ["is_remote", "is_hybrid", "is_on_site", "is_field_work"]:
        data[col] = data.get(col, pd.Series(False, index=data.index)).astype(str).str.lower().isin(["true", "1", "1.0"])
    for col in ["company", "work_formats", "publication_time", "snapshot_date"]:
        data[col] = data.get(col, pd.Series("", index=data.index)).fillna("").astype(str)
    for col in ["name", "area_name", "category"]:
        data[col] = data[col].astype(str).str.strip()
    data = data[(data["name"] != "") & (data["area_name"] != "") & (data["category"] != "")]
    report = {"source": path.name, "raw_rows": raw_count, "rows": len(data),
              "removed_rows": raw_count - len(data), "cities": data.area_name.nunique(),
              "categories": data.category.nunique(), "salary_known": int(data.salary.notna().sum()),
              "responses_known": int(data.responses_count.notna().sum()),
              "snapshot_dates": sorted(data.snapshot_date.unique().tolist()),
              "missing_by_column": raw.isna().sum().astype(int).to_dict()}
    return data, report
