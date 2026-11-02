"""Patches tab: write a fixed patch into the car's binary through the XDF and
save the result as a new file. The input binary is never changed."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QFileDialog, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QListWidget, QMessageBox, QPlainTextEdit, QPushButton,
    QSplitter, QVBoxLayout, QWidget,
)

from ..core.xdf import Xdf, load_bin
from .patches import PATCHES, Patch, PatchError, PatchResult, apply_patch


class PatchTab(QWidget):
    TITLE = "Patches"

    def __init__(self, family, state, parent=None):
        super().__init__(parent)
        self.state = state
        self._build()

    def _build(self) -> None:
        root = QHBoxLayout(self)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        root.addWidget(splitter)

        left = QWidget()
        lv = QVBoxLayout(left)
        files = QGroupBox("Files")
        fv = QVBoxLayout(files)
        self.edit_xdf = self._file_row(fv, "XDF", "XDF definition (*.xdf);;All files (*)")
        self.edit_bin = self._file_row(fv, "Binary", "Binary (*.bin *.ori);;All files (*)")
        lv.addWidget(files)

        box = QGroupBox("Patch")
        bv = QVBoxLayout(box)
        self.list = QListWidget()
        self.list.addItems([p.title for p in PATCHES])
        self.list.setMaximumHeight(120)
        self.desc = QPlainTextEdit()
        self.desc.setReadOnly(True)
        bv.addWidget(self.list)
        bv.addWidget(self.desc, 1)
        row = QHBoxLayout()
        self.btn_check = QPushButton("Check")
        self.btn_apply = QPushButton("Apply && Save As...")
        row.addWidget(self.btn_check)
        row.addWidget(self.btn_apply, 1)
        bv.addLayout(row)
        lv.addWidget(box, 1)
        splitter.addWidget(left)

        right = QWidget()
        rv = QVBoxLayout(right)
        rv.addWidget(QLabel("Output"))
        self.console = QPlainTextEdit()
        self.console.setReadOnly(True)
        rv.addWidget(self.console, 1)
        splitter.addWidget(right)
        splitter.setSizes([620, 880])

        self.list.currentRowChanged.connect(self._show_description)
        self.btn_check.clicked.connect(self.on_check)
        self.btn_apply.clicked.connect(self.on_apply)
        self.list.setCurrentRow(0)

    def _file_row(self, layout: QVBoxLayout, label: str, file_filter: str) -> QLineEdit:
        row = QHBoxLayout()
        edit = QLineEdit()
        browse = QPushButton("Browse...")
        row.addWidget(QLabel(label))
        row.addWidget(edit, 1)
        row.addWidget(browse)
        layout.addLayout(row)

        def pick():
            path, _ = QFileDialog.getOpenFileName(self, f"Select {label}", edit.text(), file_filter)
            if path:
                edit.setText(path)

        browse.clicked.connect(pick)
        return edit

    def showEvent(self, event) -> None:
        files = self.state.preset.files
        if not self.edit_xdf.text() and files.get("xdf"):
            self.edit_xdf.setText(str(files["xdf"]))
        if not self.edit_bin.text() and files.get("bin"):
            self.edit_bin.setText(str(files["bin"]))
        super().showEvent(event)

    def _patch(self) -> Patch:
        return PATCHES[max(self.list.currentRow(), 0)]

    def _show_description(self, _row: int) -> None:
        p = self._patch()
        self.desc.setPlainText(p.description + "".join(f"\n\n{r}" for r in p.reminders))

    def log(self, *lines: str) -> None:
        for line in lines:
            self.console.appendPlainText(line)

    def _run(self) -> PatchResult | None:
        self.console.clear()
        xdf_path, bin_path = self.edit_xdf.text().strip(), self.edit_bin.text().strip()
        if not Path(xdf_path).is_file() or not Path(bin_path).is_file():
            QMessageBox.warning(self, "Missing file", "Select the XDF and the binary to patch.")
            return None
        try:
            result = apply_patch(Xdf(xdf_path), load_bin(bin_path), self._patch())
        except PatchError as exc:
            self.log("PATCH NOT APPLIED. Nothing was written.", *[f"  - {p}" for p in exc.problems])
            QMessageBox.warning(self, "Patch not applied",
                                "The patch was not applied:\n\n" + "\n".join(exc.problems))
            return None
        except Exception as exc:  # unreadable XDF or binary
            self.log("PATCH NOT APPLIED. Nothing was written.", f"  - {exc}")
            QMessageBox.critical(self, "Patch not applied", str(exc))
            return None
        self.log(*result.lines)
        return result

    def on_check(self) -> None:
        if self._run() is not None:
            self.log("", "Check only: nothing was saved.")

    def on_apply(self) -> None:
        result = self._run()
        if result is None:
            return
        src = Path(self.edit_bin.text().strip())
        default = src.with_name(f"{src.stem}_{self._patch().key}.bin")
        path, _ = QFileDialog.getSaveFileName(self, "Save patched binary", str(default), "Binary (*.bin);;All files (*)")
        if not path:
            self.log("", "Not saved.")
            return
        if Path(path).resolve() == src.resolve():
            QMessageBox.warning(self, "Choose a new file", "Save the patched binary under a new name; the input binary is kept.")
            self.log("", "Not saved: the input binary is never overwritten.")
            return
        Path(path).write_bytes(result.data)
        self.log("", f"Saved: {path}")
