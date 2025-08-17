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

    # Auto-detect headless (e.g., Colab) to run Web UI instead of Tk
    headless = not bool(os.environ.get("DISPLAY")) or os.environ.get("COLAB_GPU") is not None or os.environ.get("COLAB_RELEASE_TAG") is not None
    if headless:
        logging.info("Headless environment detected. Launching Web UI (Gradio)")
        from malzeme.web import MalzemeWebApp

        web_app = MalzemeWebApp()
        # In Colab, share=True opens a public URL; if running locally, you can set share=False
        web_app.run(share=True)
    else:
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

