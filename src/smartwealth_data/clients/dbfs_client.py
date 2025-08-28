import os, base64, requests, logging, math

from ..config import settings
log = logging.getLogger(__name__)

class DBFSClient:
    def __init__(self, host: str | None = None, token: str | None = None):
        self.host = (host or settings.databricks_host).rstrip("/")
        self.token = token or settings.databricks_token
        self._hdrs = {"Authorization": f"Bearer {self.token}"}

    def put_file_small(self, local_path: str, dbfs_path: str, overwrite: bool = True):
        """Simple endpoint (<= 1MB)."""
        url = f"{self.host}/api/2.0/dbfs/put"
        with open(local_path, "rb") as f:
            payload = {
                "path": dbfs_path,
                "contents": base64.b64encode(f.read()).decode(),
                "overwrite": overwrite,
            }
        r = requests.post(url, headers=self._hdrs, json=payload, timeout=120)
        if r.status_code >= 400:
            log.error("DBFS put failed: %s", r.text)
            r.raise_for_status()
        log.info("Uploaded %s → %s (small PUT)", local_path, dbfs_path)
        return True

    def put_file(self, local_path: str, dbfs_path: str, overwrite: bool = True, chunk_mb: int = 4):
        """Chunked upload via create/add-block/close. Supports large files."""
        size = os.path.getsize(local_path)
        if size <= 900_000:  # ~0.9MB: use simple PUT
            return self.put_file_small(local_path, dbfs_path, overwrite=overwrite)

        # 1) create handle
        create_url = f"{self.host}/api/2.0/dbfs/create"
        payload = {"path": dbfs_path, "overwrite": overwrite}
        r = requests.post(create_url, headers=self._hdrs, json=payload, timeout=60)
        r.raise_for_status()
        handle = r.json()["handle"]
        log.info("DBFS create handle=%s for %s", handle, dbfs_path)

        # 2) add blocks
        add_url = f"{self.host}/api/2.0/dbfs/add-block"
        chunk_bytes = chunk_mb * 1024 * 1024
        with open(local_path, "rb") as f:
            while True:
                b = f.read(chunk_bytes)
                if not b:
                    break
                payload = {"handle": handle, "data": base64.b64encode(b).decode()}
                r = requests.post(add_url, headers=self._hdrs, json=payload, timeout=120)
                r.raise_for_status()

        # 3) close
        close_url = f"{self.host}/api/2.0/dbfs/close"
        r = requests.post(close_url, headers=self._hdrs, json={"handle": handle}, timeout=60)
        r.raise_for_status()
        log.info("Uploaded %s → %s (chunked)", local_path, dbfs_path)
        return True
