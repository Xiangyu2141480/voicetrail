"""Single-instance local launcher; no reload and no duplicate model workers."""
import fcntl

import uvicorn

from backend.app.config import Settings


def main():
    settings = Settings.from_env()
    settings.prepare()
    with (settings.data_dir / "server.lock").open("w") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise SystemExit("Another VoiceTrail instance uses this data directory.")
        uvicorn.run("backend.app.main:create_app", factory=True,
                    host="127.0.0.1", port=settings.port, workers=1, access_log=False)


if __name__ == "__main__":
    main()
