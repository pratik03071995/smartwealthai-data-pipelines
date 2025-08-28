import time, json, requests, logging
from ..config import settings
log = logging.getLogger(__name__)

class SQLClient:
    def __init__(self, host: str | None = None, token: str | None = None, warehouse_id: str | None = None):
        self.host = (host or settings.databricks_host).rstrip("/")
        self.token = token or settings.databricks_token
        self.warehouse_id = warehouse_id or settings.databricks_warehouse_id
        self._hdrs = {"Authorization": f"Bearer {self.token}", "Content-Type": "application/json"}

    def execute(self, sql_text: str) -> dict:
        start_url = f"{self.host}/api/2.0/sql/statements"
        payload = {"statement": sql_text, "warehouse_id": self.warehouse_id, "wait_timeout": "0s"}
        r = requests.post(start_url, headers=self._hdrs, data=json.dumps(payload), timeout=60)
        r.raise_for_status()
        sid = r.json()["statement_id"]

        get_url = f"{self.host}/api/2.0/sql/statements/{sid}"
        while True:
            g = requests.get(get_url, headers=self._hdrs, timeout=60)
            g.raise_for_status()
            state = g.json()["status"]["state"]
            if state in ("SUCCEEDED", "FAILED", "CANCELED"):
                if state != "SUCCEEDED":
                    raise RuntimeError(f"SQL failed: {g.text}")
                log.info("SQL SUCCEEDED")
                return g.json()
            time.sleep(1)
