import logging
from pathlib import Path
from ...config import settings
from ...clients.dbfs_client import DBFSClient
from ...clients.sql_client import SQLClient
from ...utils.paths import tmp_path
from ..fetchers.yahoo_earnings_fetcher import YahooEarningsFetcher
from ..loaders.earnings_loader import EarningsCSVLoader

log = logging.getLogger(__name__)

class EarningsIngestPipeline:
    def __init__(self, dbfs_staging_dir: str = "dbfs:/sw/staging"):
        self.fetcher = YahooEarningsFetcher(months_back=settings.months_back)
        self.loader = EarningsCSVLoader()
        self.dbfs = DBFSClient()
        self.sql = SQLClient()
        self.dbfs_dir = dbfs_staging_dir

    def _read_sql(self, path: str) -> str:
        return Path(path).read_text(encoding="utf-8")

    def run(self, tickers: list[str], local_csv_name: str = "earnings_latest.csv"):
        # 1) Fetch
        pdf = self.fetcher.fetch(tickers)
        if pdf.empty:
            raise RuntimeError("No rows fetched. Check tickers or months_back.")

        # 2) Write local CSV
        local_csv = tmp_path(local_csv_name)
        self.loader.write(pdf, local_csv)

        # 3) Upload to DBFS (chunked)
        dbfs_csv = f"{self.dbfs_dir}/{local_csv_name}"
        self.dbfs.put_file(str(local_csv), dbfs_csv, overwrite=True)

        # 4) Ensure DBs + table exist
        self.sql.execute(Path("sql/00_schemas.sql").read_text())
        self.sql.execute(Path("sql/gold_ddl.sql").read_text())

        # 5) COPY INTO (template replace)
        copy_tpl = self._read_sql("sql/copy_into_earnings_template.sql")
        copy_sql = copy_tpl.replace("{{CSV_PATH}}", dbfs_csv)
        self.sql.execute(copy_sql)

        log.info("Pipeline complete → %s.%s", settings.target_db, settings.target_table_earnings)
        return {"rows": len(pdf), "dbfs_csv": dbfs_csv}
