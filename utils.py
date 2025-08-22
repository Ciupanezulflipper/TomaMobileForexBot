def log_error(msg):
    print("ERROR:", msg)

def expiry_report(*a, **kw):
    return None

def utc_iso():
    import datetime
    return datetime.datetime.utcnow().isoformat()

def safe_getenv(key, default=None):
    import os
    return os.getenv(key, default)
