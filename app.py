import logging
import os
import sys


def configure_logging() -> None:
    """
    Configure application-wide logging to both console and a rotating file in ./logs.
    This function is safe to call multiple times; subsequent calls are no-ops.
    """
    if logging.getLogger().handlers:
        return

    os.makedirs("logs", exist_ok=True)
    log_format = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    logging.basicConfig(
        level=logging.INFO,
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(os.path.join("logs", "app.log"), encoding="utf-8"),
        ],
    )


def main() -> None:
    """Application entry point."""
    configure_logging()
    logging.info("Starting Malzeme Takip Sistemi")

    # Import UI lazily to avoid initializing Tk in non-GUI contexts (e.g., tests)
    try:
        from malzeme.ui import MalzemeApp
    except Exception as exc:  # pragma: no cover - startup guard
        logging.exception("UI module import failed: %s", exc)
        raise

    app = MalzemeApp()
    app.run()


if __name__ == "__main__":
    main()

