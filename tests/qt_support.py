import os
import time
os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
from PyQt6.QtWidgets import QApplication
from PyQt6.QtTest import QTest

APP = QApplication.instance() or QApplication([])
APP.setQuitOnLastWindowClosed(False)


def wait_until(predicate, timeout=3000):
    deadline = time.monotonic() + timeout / 1000
    while not predicate():
        if time.monotonic() > deadline:
            raise AssertionError('Tempo limite no evento Qt')
        QTest.qWait(5)
