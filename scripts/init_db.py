from __future__ import annotations

import logging

from app import models
from app.db import Base, engine

logging.basicConfig(level=logging.INFO)


def main() -> None:
    logging.info("Creating database tables (if not exist)...")
    Base.metadata.create_all(bind=engine)
    logging.info("Done")


if __name__ == "__main__":
    main()
