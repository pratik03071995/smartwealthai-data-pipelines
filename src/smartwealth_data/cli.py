import typer, logging
from .logging_config import setup_logging
from .services.pipelines.earnings_ingest_pipeline import EarningsIngestPipeline

app = typer.Typer(add_completion=False)

@app.command()
def earnings(
    tickers: str = typer.Option(..., help="Comma-separated tickers, e.g. AAPL,MSFT,NVDA"),
    dbfs_staging_dir: str = typer.Option("dbfs:/sw/staging", help="DBFS directory for staging CSV"),
    csv_name: str = typer.Option("earnings_latest.csv", help="Staged file name"),
    log_level: str = typer.Option("INFO", help="Logging level"),
):
    setup_logging(log_level)
    pipeline = EarningsIngestPipeline(dbfs_staging_dir=dbfs_staging_dir)
    result = pipeline.run([t.strip().upper() for t in tickers.split(",") if t.strip()], local_csv_name=csv_name)
    logging.getLogger(__name__).info("Done: %s", result)

def main():
    app()

if __name__ == "__main__":
    main()
