from datetime import datetime

def start_run():
    return {
        "started_at": datetime.utcnow(),
        "sources_checked": 0,
        "opportunities_found": 0
    }
