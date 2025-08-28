from pathlib import Path
from datetime import datetime
import pandas as pd

class EarningsCSVLoader:
    """Writes normalized earnings rows to a CSV with fixed schema order."""
    COLUMNS = [
        "ticker","earnings_date","eps_estimate","eps_actual","surprise_pct",
        "fiscal_year","fiscal_quarter","company_name","sector","industry",
        "source","ingested_at_utc"
    ]

    def write(self, df: pd.DataFrame, out_path: Path) -> Path:
        df = df.copy()
        df["ingested_at_utc"] = datetime.utcnow().isoformat(timespec="seconds")
        for col in self.COLUMNS:
            if col not in df.columns:
                df[col] = None
        df = df[self.COLUMNS]
        out_path.parent.mkdir(parents=True, exist_ok=True)
        df.to_csv(out_path, index=False)
        return out_path
