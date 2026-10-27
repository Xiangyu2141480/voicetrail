"""Prepare the pinned CPU model, printing measured download progress."""
import argparse
import json
import threading

from backend.app.config import Settings
from backend.app.embedding import EmbeddingModel


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--offline", action="store_true", help="Require existing verified weights")
    args = parser.parse_args()
    settings = Settings.from_env()
    settings.prepare()
    model = EmbeddingModel(settings.data_dir / "models")
    finished = threading.Event()

    def progress():
        while not finished.wait(2):
            print(json.dumps(model.status()), flush=True)

    reporter = threading.Thread(target=progress, daemon=True)
    reporter.start()
    try:
        model.load(offline=args.offline)
    finally:
        finished.set()
        reporter.join()
    print(json.dumps(model.status(), indent=2))


if __name__ == "__main__":
    main()
