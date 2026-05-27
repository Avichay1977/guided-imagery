from dataclasses import dataclass, asdict
from pathlib import Path
import pandas as pd


@dataclass
class DataQualityReport:
    source_path: str
    rows_loaded: int = 0
    rows_after_cleaning: int = 0
    duplicate_timestamps_removed: int = 0
    invalid_timestamps_removed: int = 0
    missing_ohlc_rows_removed: int = 0
    negative_or_zero_price_rows_removed: int = 0
    invalid_geometry_rows_corrected: int = 0
    missing_volume_filled: int = 0
    adjusted_ohlc_applied: bool = False


class DataLoader:
    """
    שכבת טעינה וניקוי נתוני OHLCV.

    עקרונות:
    - לא מבצע forward-fill או backward-fill למחירי OHLC.
    - לא מייצר מידע עתידי.
    - אוכף סכמה קבועה.
    - מתקן High/Low גיאומטריים בלבד.
    - מאפשר התאמת OHLC לפי adjusted_close כאשר קיים ומופעל במפורש.
    """

    REQUIRED_COLUMNS = ["open", "high", "low", "close", "volume"]
    OPTIONAL_COLUMNS = ["adjusted_close", "symbol"]

    def __init__(
        self,
        column_mapping: dict | None = None,
        use_adjusted_close: bool = False,
        correct_invalid_geometry: bool = True,
        drop_zero_volume: bool = False,
    ):
        self.column_mapping = column_mapping or {}
        self.use_adjusted_close = use_adjusted_close
        self.correct_invalid_geometry = correct_invalid_geometry
        self.drop_zero_volume = drop_zero_volume
        self.last_report: DataQualityReport | None = None

    def load_from_csv(self, file_path: str | Path) -> pd.DataFrame:
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"Data file not found: {path.resolve()}")

        df = pd.read_csv(path)

        report = DataQualityReport(
            source_path=str(path.resolve()),
            rows_loaded=len(df),
        )

        if self.column_mapping:
            df = df.rename(columns=self.column_mapping)

        df.columns = [str(col).strip().lower() for col in df.columns]

        if "timestamp" not in df.columns:
            raise ValueError(
                "CSV must contain 'timestamp' column or provide column_mapping."
            )

        df = self._parse_timestamp_index(df, report)
        df = self._enforce_schema(df)
        df = self._coerce_numeric_columns(df)
        df = self._remove_duplicate_timestamps(df, report)
        df = self._sanitize_core_data(df, report)

        if self.use_adjusted_close:
            df = self._apply_adjusted_ohlc_if_available(df, report)

        df = df.sort_index()
        df = df[self._output_columns(df)]

        report.rows_after_cleaning = len(df)
        self.last_report = report

        return df

    # --------------------------------------------------
    # Pipeline Steps
    # --------------------------------------------------

    def _parse_timestamp_index(
        self,
        df: pd.DataFrame,
        report: DataQualityReport,
    ) -> pd.DataFrame:
        df = df.copy()

        df["timestamp"] = pd.to_datetime(
            df["timestamp"],
            errors="coerce",
            utc=False,
        )

        invalid_ts = df["timestamp"].isna()
        report.invalid_timestamps_removed = int(invalid_ts.sum())

        df = df.loc[~invalid_ts].copy()
        df = df.set_index("timestamp")
        df = df.sort_index()

        return df

    def _enforce_schema(self, df: pd.DataFrame) -> pd.DataFrame:
        missing = set(self.REQUIRED_COLUMNS) - set(df.columns)

        if missing:
            raise ValueError(f"Missing required OHLCV columns: {missing}")

        return df

    def _coerce_numeric_columns(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()

        numeric_columns = self.REQUIRED_COLUMNS + ["adjusted_close"]

        for col in numeric_columns:
            if col in df.columns:
                df[col] = pd.to_numeric(df[col], errors="coerce")

        return df

    def _remove_duplicate_timestamps(
        self,
        df: pd.DataFrame,
        report: DataQualityReport,
    ) -> pd.DataFrame:
        duplicate_mask = df.index.duplicated(keep="last")
        report.duplicate_timestamps_removed = int(duplicate_mask.sum())

        return df.loc[~duplicate_mask].copy()

    def _sanitize_core_data(
        self,
        df: pd.DataFrame,
        report: DataQualityReport,
    ) -> pd.DataFrame:
        df = df.copy()

        # אין השלמות מחירים. שורת OHLC חסרה נפסלת.
        ohlc_missing = df[["open", "high", "low", "close"]].isna().any(axis=1)
        report.missing_ohlc_rows_removed = int(ohlc_missing.sum())
        df = df.loc[~ohlc_missing].copy()

        # Volume חסר לא משלים מידע עתידי. הוא רק מחליש סיגנלי נפח.
        volume_missing = df["volume"].isna()
        report.missing_volume_filled = int(volume_missing.sum())
        df.loc[volume_missing, "volume"] = 0.0

        if self.drop_zero_volume:
            df = df.loc[df["volume"] > 0].copy()

        non_positive_prices = (
            (df["open"] <= 0)
            | (df["high"] <= 0)
            | (df["low"] <= 0)
            | (df["close"] <= 0)
        )

        report.negative_or_zero_price_rows_removed = int(
            non_positive_prices.sum()
        )

        df = df.loc[~non_positive_prices].copy()

        invalid_geometry = (
            (df["high"] < df["low"])
            | (df["high"] < df["open"])
            | (df["high"] < df["close"])
            | (df["low"] > df["open"])
            | (df["low"] > df["close"])
        )

        report.invalid_geometry_rows_corrected = int(invalid_geometry.sum())

        if invalid_geometry.any():
            if not self.correct_invalid_geometry:
                df = df.loc[~invalid_geometry].copy()
            else:
                ohlc_cols = ["open", "high", "low", "close"]

                df.loc[invalid_geometry, "high"] = df.loc[
                    invalid_geometry,
                    ohlc_cols,
                ].max(axis=1)

                df.loc[invalid_geometry, "low"] = df.loc[
                    invalid_geometry,
                    ohlc_cols,
                ].min(axis=1)

        return df

    def _apply_adjusted_ohlc_if_available(
        self,
        df: pd.DataFrame,
        report: DataQualityReport,
    ) -> pd.DataFrame:
        """
        התאמת OHLC לפי adjusted_close.
        להשתמש רק אם הדאטה מכיל close גולמי ו-adjusted_close תקין.
        לא להפעיל אם הקובץ כבר מותאם מראש.
        """
        df = df.copy()

        if "adjusted_close" not in df.columns:
            raise ValueError(
                "use_adjusted_close=True but 'adjusted_close' column is missing."
            )

        df["adjusted_close"] = pd.to_numeric(
            df["adjusted_close"],
            errors="coerce",
        )

        valid_adjusted = (
            df["adjusted_close"].notna()
            & (df["adjusted_close"] > 0)
            & (df["close"] > 0)
        )

        if not valid_adjusted.all():
            bad_count = int((~valid_adjusted).sum())
            raise ValueError(
                f"Invalid adjusted_close values found in {bad_count} rows."
            )

        adjustment_ratio = df["adjusted_close"] / df["close"]

        for col in ["open", "high", "low", "close"]:
            df[col] = df[col] * adjustment_ratio

        report.adjusted_ohlc_applied = True

        return df

    def _output_columns(self, df: pd.DataFrame) -> list[str]:
        cols = self.REQUIRED_COLUMNS.copy()

        for optional in self.OPTIONAL_COLUMNS:
            if optional in df.columns:
                cols.append(optional)

        return cols

    # --------------------------------------------------
    # Diagnostics
    # --------------------------------------------------

    def get_last_report(self) -> dict:
        if self.last_report is None:
            return {}

        return asdict(self.last_report)
