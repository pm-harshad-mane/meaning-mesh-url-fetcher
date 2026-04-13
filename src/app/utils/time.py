from __future__ import annotations

import time


def unix_timestamp() -> int:
    return int(time.time())


def unix_timestamp_ms() -> int:
    return int(time.time() * 1000)
