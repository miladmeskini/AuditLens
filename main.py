import sys
import os
import logging
import traceback

from PySide6.QtWidgets import QApplication, QMessageBox
from PySide6.QtGui import QPalette, QColor

from config import GLOBAL_QSS, C
from ui.main_window import MainWindow

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)-8s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger("auditlens")


def main() -> None:
    try:
        os.environ.setdefault("QT_AUTO_SCREEN_SCALE_FACTOR", "1")

        app = QApplication(sys.argv)
        app.setApplicationName("AuditLens")
        app.setApplicationVersion("1.0.0")
        app.setStyleSheet(GLOBAL_QSS)

        palette = QPalette()
        palette.setColor(QPalette.ColorRole.Window,          QColor(C["bg0"]))
        palette.setColor(QPalette.ColorRole.WindowText,      QColor(C["txt"]))
        palette.setColor(QPalette.ColorRole.Base,            QColor(C["bg1"]))
        palette.setColor(QPalette.ColorRole.AlternateBase,   QColor(C["bg3"]))
        palette.setColor(QPalette.ColorRole.ToolTipBase,     QColor(C["bg2"]))
        palette.setColor(QPalette.ColorRole.ToolTipText,     QColor(C["txt"]))
        palette.setColor(QPalette.ColorRole.Text,            QColor(C["txt"]))
        palette.setColor(QPalette.ColorRole.Button,          QColor(C["bg2"]))
        palette.setColor(QPalette.ColorRole.ButtonText,      QColor(C["txt"]))
        palette.setColor(QPalette.ColorRole.Highlight,       QColor(C["blue"]))
        palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#ffffff"))
        app.setPalette(palette)

        window = MainWindow()
        window.show()
        log.info("AuditLens started.")
        sys.exit(app.exec())

    except Exception as e:
        traceback.print_exc()
        try:
            QMessageBox.critical(None, "Fatal Error", str(e))
        except Exception:
            pass
        input("\nPress ENTER to close...")


if __name__ == "__main__":
    main()
