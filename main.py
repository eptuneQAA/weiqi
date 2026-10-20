import logging
import sys

from PyQt5.QtCore import QLibraryInfo, Qt, QTranslator
from PyQt5.QtWidgets import QApplication

from weiqi.ui.main_window import MainWindow


def main():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    discovery_enabled = "--no-discovery" not in sys.argv
    argv = [arg for arg in sys.argv if arg != "--no-discovery"]
    app = QApplication(argv)
    app.setApplicationName("围棋")
    translator = QTranslator()
    translations_path = QLibraryInfo.location(QLibraryInfo.TranslationsPath)
    if translator.load("qt_zh_CN", translations_path):
        app.installTranslator(translator)
    window = MainWindow(discovery_enabled=discovery_enabled)
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
