from __future__ import annotations

from pathlib import Path
from typing import Any


def build_fan_signals(structured_dir: str | Path, out: str | Path | None = None) -> list[dict[str, Any]]:
    import pandas as pd

    directory = Path(structured_dir)
    exposures = _read(directory / "company_product_channel.csv")
    if exposures.empty:
        return []

    exposures = exposures.copy()
    exposures["company_id"] = exposures["company_id"].fillna(exposures.get("stock_code", ""))
    exposures["exposure_weight"] = _num(exposures.get("exposure_weight"), default=0.0)
    exposures = exposures[exposures["product_id"].fillna("").eq("fan") | exposures["product_name"].fillna("").str.contains("风扇", na=False)]
    if exposures.empty:
        return []

    dates = _signal_dates(directory)
    base = exposures.assign(_key=1).merge(pd.DataFrame({"date": dates, "_key": 1}), on="_key").drop(columns="_key")

    weather = _weather_signal(directory / "weather_metrics.csv")
    sales = _sales_signal(directory / "sales_metrics.csv")
    cost = _cost_pressure_signal(directory)
    market = _market_signal(directory / "market_features.csv")

    result = base.merge(weather, on="date", how="left")
    result = result.merge(sales, on="date", how="left")
    result = result.merge(cost, on="date", how="left")
    result = result.merge(market, on=["stock_code", "date"], how="left")

    for col in [
        "weather_index",
        "sales_index",
        "cost_pressure_index",
        "market_confirmation_index",
    ]:
        if col not in result:
            result[col] = 0.0
        result[col] = result[col].fillna(0.0)

    result["weather_signal"] = result["weather_index"] * result["exposure_weight"]
    result["sales_signal"] = result["sales_index"] * result["exposure_weight"]
    result["cost_pressure_signal"] = result["cost_pressure_index"] * result["exposure_weight"]
    result["market_confirmation_signal"] = result["market_confirmation_index"]
    result["combined_signal"] = (
        0.35 * _z(result["weather_signal"])
        + 0.35 * _z(result["sales_signal"])
        - 0.15 * _z(result["cost_pressure_signal"])
        + 0.15 * _z(result["market_confirmation_signal"])
    )

    columns = [
        "date",
        "company_id",
        "company_name",
        "stock_code",
        "product_id",
        "product_name",
        "exposure_weight",
        "weather_signal",
        "sales_signal",
        "cost_pressure_signal",
        "market_confirmation_signal",
        "combined_signal",
    ]
    records = result[columns].sort_values(["date", "stock_code", "company_id"]).to_dict("records")

    if out is not None:
        out_path = Path(out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        result[columns].to_csv(out_path, index=False, encoding="utf-8-sig")

    return records


def _read(path: Path):
    import pandas as pd

    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path, dtype=str)


def _num(series, default: float = 0.0):
    import pandas as pd

    if series is None:
        return default
    return pd.to_numeric(series, errors="coerce").fillna(default)


def _signal_dates(directory: Path) -> list[str]:
    dates: set[str] = set()
    for filename in ["weather_metrics.csv", "sales_metrics.csv", "commodity_prices.csv", "market_features.csv"]:
        df = _read(directory / filename)
        if not df.empty and "date" in df:
            dates.update(str(d) for d in df["date"].dropna().unique())
    return sorted(dates)


def _weather_signal(path: Path):
    import pandas as pd

    df = _read(path)
    if df.empty:
        return pd.DataFrame(columns=["date", "weather_index"])
    max_temp = _num(df.get("max_temp"))
    high_days = _num(df.get("high_temp_days"))
    population = _num(df.get("population_weight"), default=1.0)
    demand = _num(df.get("demand_weight"), default=1.0)
    heat_excess = (max_temp - 30.0).clip(lower=0.0)
    df["weather_index"] = (heat_excess + high_days * 2.0) * population * demand
    return df.groupby("date", as_index=False)["weather_index"].sum()


def _sales_signal(path: Path):
    import pandas as pd

    df = _read(path)
    if df.empty:
        return pd.DataFrame(columns=["date", "sales_index"])
    yoy_amount = _num(df.get("yoy_amount"))
    yoy_volume = _num(df.get("yoy_volume"))
    asp = _num(df.get("asp"))
    asp_norm = (asp / asp.replace(0, pd.NA).median()).fillna(0.0)
    df["sales_index"] = yoy_amount * 0.55 + yoy_volume * 0.35 + asp_norm * 0.10
    return df.groupby("date", as_index=False)["sales_index"].mean()


def _cost_pressure_signal(directory: Path):
    import pandas as pd

    prices = _read(directory / "commodity_prices.csv")
    exposure = _read(directory / "material_exposure.csv")
    if prices.empty or exposure.empty:
        return pd.DataFrame(columns=["date", "cost_pressure_index"])
    prices["change_pct"] = _num(prices.get("change_pct"))
    exposure["cost_weight"] = _num(exposure.get("cost_weight"))
    merged = prices.merge(exposure[["material_id", "cost_weight"]], on="material_id", how="left")
    merged["cost_pressure_index"] = merged["change_pct"] * merged["cost_weight"].fillna(0.0)
    return merged.groupby("date", as_index=False)["cost_pressure_index"].sum()


def _market_signal(path: Path):
    import pandas as pd

    df = _read(path)
    if df.empty:
        return pd.DataFrame(columns=["stock_code", "date", "market_confirmation_index"])
    turnover = _num(df.get("turnover_zscore"))
    inflow = _num(df.get("main_net_inflow"))
    imbalance = _num(df.get("order_imbalance"))
    inflow_scaled = inflow / max(float(inflow.abs().max()), 1.0)
    df["market_confirmation_index"] = turnover * 0.4 + inflow_scaled * 0.4 + imbalance * 0.2
    return df[["stock_code", "date", "market_confirmation_index"]]


def _z(series):
    std = series.std()
    if std == 0 or std != std:
        return series * 0.0
    return (series - series.mean()) / std
