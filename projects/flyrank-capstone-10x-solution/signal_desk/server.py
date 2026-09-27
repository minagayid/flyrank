from __future__ import annotations

from signal_desk.api import make_server
from signal_desk.config import HOST, PORT
from signal_desk.database import initialize
from signal_desk.worker import JobWorker


def main() -> None:
    initialize()
    worker = JobWorker()
    worker.start()
    server = make_server(HOST, PORT)
    print(f"Signal Desk API listening on http://{HOST}:{PORT} (Ctrl+C to stop)")
    try:
        server.serve_forever(poll_interval=0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        worker.stop()


if __name__ == "__main__":
    main()
