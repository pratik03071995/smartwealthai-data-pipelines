import time, logging
from functools import wraps
log = logging.getLogger(__name__)

def timeit(fn):
    @wraps(fn)
    def _inner(*args, **kwargs):
        t0 = time.time()
        res = fn(*args, **kwargs)
        log.info(f"{fn.__name__} took {(time.time()-t0):.2f}s")
        return res
    return _inner
