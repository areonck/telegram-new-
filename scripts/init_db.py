from __future__ import annotations

import logging
import pathlib
import sys

# Allow running as a script from the repo root without installing the package.
ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import models  # noqa: E402  pylint: disable=wrong-import-position
from app.db import Base, engine  # noqa: E402  pylint: disable=wrong-import-position

logging.basicConfig(level=logging.INFO)


def main() -> None:
    logging.info("Creating database tables (if not exist)...")
    Base.metadata.create_all(bind=engine)
    logging.info("Done")


if __name__ == "__main__":
    main()
