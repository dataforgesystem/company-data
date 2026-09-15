import logging
import sys


class CustomLogger:
    """
    Singleton Logger wrapper for the project.
    """

    def __init__(
        self,
        log_file: str | None = None,
        name: str = __name__,
        level: int = logging.INFO,
    ) -> None:
        # Create a native logger
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.propagate = False
        self.log_file = log_file

        # Prevent adding multiple handlers if instantiated multiple times
        if not self.logger.handlers:
            # Create a reusable log format
            formatter = logging.Formatter(
                fmt="%(asctime)s [%(levelname)s] %(filename)s:%(lineno)d - %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )

            # 1. Console Handler (Streams logs to standard output)
            console_handler = logging.StreamHandler(sys.stdout)
            console_handler.setFormatter(formatter)
            self.logger.addHandler(console_handler)

            # 2. File Handler (Appends logs to a local file)
            if self.log_file is not None:
                file_handler = logging.FileHandler(self.log_file, encoding="utf-8")
                file_handler.setFormatter(formatter)
                self.logger.addHandler(file_handler)

    def get_logger(self) -> logging.Logger:
        """Exposes the underlying native logger instance."""
        return self.logger
