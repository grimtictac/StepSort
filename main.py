#!/usr/bin/env python3
"""StepSort – Music Library Organiser entry point."""

import sys

from PySide6.QtWidgets import QApplication

from stepsort.main_window import MainWindow


def main() -> None:
    app = QApplication(sys.argv)
    app.setApplicationName("StepSort")
    app.setApplicationDisplayName("StepSort – Music Library Organiser")
    window = MainWindow()
    window.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
