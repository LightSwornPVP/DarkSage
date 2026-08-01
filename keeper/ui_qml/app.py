from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import cast

from PySide6.QtCore import QCoreApplication, QTimer, QUrl
from PySide6.QtGui import QGuiApplication, QIcon
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuick import QQuickWindow

from keeper.app.service import KeeperApplication
from keeper.ui_qml.controller import KeeperDesktopController, NAVIGATION


def run_desktop(
    application: KeeperApplication,
    *,
    smoke: bool = False,
    screenshot_directory: Path | None = None,
    test_fixture: bool = False,
) -> int:
    if smoke and "QT_QPA_PLATFORM" not in os.environ:
        os.environ["QT_QPA_PLATFORM"] = "offscreen"
    QCoreApplication.setOrganizationName("Keeper")
    QCoreApplication.setApplicationName("Keeper")
    existing = QGuiApplication.instance()
    qt_app = (
        cast(QGuiApplication, existing) if existing else QGuiApplication(sys.argv[:1])
    )
    assets = Path(__file__).resolve().parents[1] / "assets"
    icon_path = assets / "keeper-official.png"
    qt_app.setWindowIcon(QIcon(str(icon_path)))
    engine = QQmlApplicationEngine()
    controller = KeeperDesktopController(application, test_fixture=test_fixture)
    engine.rootContext().setContextProperty("keeper", controller)
    engine.rootContext().setContextProperty(
        "keeperIcon", QUrl.fromLocalFile(str(icon_path))
    )
    qml_path = Path(__file__).with_name("qml") / "Main.qml"
    engine.load(QUrl.fromLocalFile(str(qml_path)))
    if not engine.rootObjects():
        return 70
    root = engine.rootObjects()[0]
    if smoke:
        target = (
            screenshot_directory or application.data_directory / "ui-smoke"
        ).resolve()
        target.mkdir(parents=True, exist_ok=True)
        captured: list[str] = []
        failure: list[str] = []
        finished = False

        def finish() -> None:
            nonlocal finished
            if finished:
                return
            finished = True
            evidence = {
                "ui_smoke": "failed" if failure else "passed",
                "rendered_pages": len(captured),
                "pages": captured,
                "environment": controller.state_snapshot().get("environment"),
                "output": str(target),
                "failure": failure[0] if failure else None,
            }
            (target / "ui-smoke-evidence.json").write_text(
                json.dumps(evidence, indent=2), encoding="utf-8"
            )
            qt_app.exit(1 if failure else 0)

        def capture(index: int = 0) -> None:
            if index >= len(NAVIGATION):
                finish()
                return
            try:
                page = NAVIGATION[index]
                controller.navigate(page)
            except Exception as error:
                failure.append(str(error))
                finish()
                return

            def grab_settled_frame() -> None:
                try:
                    if not isinstance(root, QQuickWindow):
                        raise TypeError("QML root is not a QQuickWindow")
                    image = root.grabWindow()
                    safe_name = page.lower().replace(" ", "-") + ".png"
                    if image.isNull() or not image.save(str(target / safe_name)):
                        raise OSError(f"could not save rendered page: {page}")
                    captured.append(page)
                except Exception as error:
                    failure.append(str(error))
                    finish()
                    return
                QTimer.singleShot(90, lambda: capture(index + 1))

            QTimer.singleShot(180, grab_settled_frame)

        # A callback exception must never leave a package smoke hanging forever.
        def timeout() -> None:
            if finished:
                return
            failure.append("UI smoke timed out")
            finish()

        QTimer.singleShot(15_000, timeout)
        QTimer.singleShot(350, capture)
    return int(qt_app.exec())


__all__ = ["run_desktop"]
