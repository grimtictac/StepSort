"""PySide6 main window for StepSort."""

from __future__ import annotations

import os
from pathlib import Path
from typing import List, Optional

from PySide6.QtCore import Qt, QThread, Signal
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QStatusBar,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from stepsort.file_sorter import SortPlan, build_sort_plan, execute_sort_plan
from stepsort.rhythmdb_parser import Track, parse_rhythmdb


class _SortWorker(QThread):
    """Background thread that executes the sort plan."""

    progress = Signal(int, int, str)   # current, total, dest_path
    finished = Signal(int, int)        # success_count, error_count

    def __init__(
        self,
        plan: List[SortPlan],
        copy_mode: bool,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._plan = plan
        self._copy_mode = copy_mode

    def run(self) -> None:
        results = execute_sort_plan(
            self._plan,
            progress_callback=lambda cur, tot, dest: self.progress.emit(
                cur, tot, str(dest)
            ),
            copy=self._copy_mode,
        )
        success = sum(1 for _, err in results if err is None)
        errors = len(results) - success
        self.finished.emit(success, errors)


class MainWindow(QMainWindow):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("StepSort – Music Library Organiser")
        self.setMinimumSize(900, 600)

        self._tracks: List[Track] = []
        self._plan: List[SortPlan] = []
        self._worker: Optional[_SortWorker] = None

        central = QWidget()
        self.setCentralWidget(central)
        root_layout = QVBoxLayout(central)
        root_layout.setSpacing(8)
        root_layout.setContentsMargins(12, 12, 12, 12)

        # ── Path pickers ─────────────────────────────────────────────────────
        root_layout.addLayout(self._make_path_row("RhythmDB XML:", "rhythmdb_edit", self._browse_xml))
        root_layout.addLayout(self._make_path_row("Source Folder:", "source_edit", self._browse_source))
        root_layout.addLayout(self._make_path_row("Target Folder:", "target_edit", self._browse_target))

        # ── Options ──────────────────────────────────────────────────────────
        opts_layout = QHBoxLayout()
        self._copy_checkbox = QCheckBox("Copy files (uncheck to Move)")
        self._copy_checkbox.setChecked(True)
        opts_layout.addWidget(self._copy_checkbox)
        opts_layout.addStretch()

        self._preview_btn = QPushButton("Preview")
        self._preview_btn.clicked.connect(self._on_preview)
        opts_layout.addWidget(self._preview_btn)

        self._sort_btn = QPushButton("Sort!")
        self._sort_btn.setEnabled(False)
        self._sort_btn.clicked.connect(self._on_sort)
        opts_layout.addWidget(self._sort_btn)
        root_layout.addLayout(opts_layout)

        # ── Preview table ─────────────────────────────────────────────────────
        self._table = QTableWidget(0, 5)
        self._table.setHorizontalHeaderLabels(
            ["Artist", "Album", "Title", "Track #", "Destination"]
        )
        self._table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        self._table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self._table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self._table.setAlternatingRowColors(True)
        root_layout.addWidget(self._table)

        # ── Progress bar ──────────────────────────────────────────────────────
        self._progress = QProgressBar()
        self._progress.setVisible(False)
        root_layout.addWidget(self._progress)

        # ── Status bar ────────────────────────────────────────────────────────
        self._status = QStatusBar()
        self.setStatusBar(self._status)
        self._status.showMessage("Ready – select paths and click Preview.")

    # ── Path row helper ───────────────────────────────────────────────────────

    def _make_path_row(
        self, label_text: str, attr_name: str, browse_slot
    ) -> QHBoxLayout:
        layout = QHBoxLayout()
        label = QLabel(label_text)
        label.setFixedWidth(120)
        edit = QLineEdit()
        edit.setPlaceholderText("Click Browse… or type a path")
        browse_btn = QPushButton("Browse…")
        browse_btn.setFixedWidth(90)
        browse_btn.clicked.connect(browse_slot)
        layout.addWidget(label)
        layout.addWidget(edit)
        layout.addWidget(browse_btn)
        setattr(self, f"_{attr_name}", edit)
        return layout

    # ── Browse slots ─────────────────────────────────────────────────────────

    def _browse_xml(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self, "Select rhythmdb.xml", "", "XML Files (*.xml);;All Files (*)"
        )
        if path:
            self._rhythmdb_edit.setText(path)

    def _browse_source(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Source Folder")
        if path:
            self._source_edit.setText(path)

    def _browse_target(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Select Target Folder")
        if path:
            self._target_edit.setText(path)

    # ── Preview ───────────────────────────────────────────────────────────────

    def _on_preview(self) -> None:
        xml_path = self._rhythmdb_edit.text().strip()
        source = self._source_edit.text().strip()
        target = self._target_edit.text().strip()

        if not xml_path or not source or not target:
            QMessageBox.warning(
                self, "Missing Paths", "Please provide the RhythmDB XML, source folder, and target folder."
            )
            return

        # Parse XML
        try:
            self._tracks = parse_rhythmdb(xml_path)
        except Exception as exc:
            QMessageBox.critical(self, "Parse Error", f"Could not parse rhythmdb.xml:\n{exc}")
            return

        # Build plan
        try:
            self._plan = build_sort_plan(self._tracks, source, target)
        except Exception as exc:
            QMessageBox.critical(self, "Plan Error", f"Could not build sort plan:\n{exc}")
            return

        self._populate_table(self._plan)
        self._sort_btn.setEnabled(bool(self._plan))
        self._status.showMessage(
            f"Preview: {len(self._plan)} files matched (out of {len(self._tracks)} entries in XML)."
        )

    def _populate_table(self, plan: List[SortPlan]) -> None:
        self._table.setRowCount(0)
        self._table.setRowCount(len(plan))
        for row, item in enumerate(plan):
            t = item.track
            self._table.setItem(row, 0, QTableWidgetItem(t.album_artist or t.artist))
            self._table.setItem(row, 1, QTableWidgetItem(t.album))
            self._table.setItem(row, 2, QTableWidgetItem(t.title))
            self._table.setItem(row, 3, QTableWidgetItem(str(t.track_number) if t.track_number else ""))
            self._table.setItem(row, 4, QTableWidgetItem(str(item.destination)))

    # ── Sort ──────────────────────────────────────────────────────────────────

    def _on_sort(self) -> None:
        if not self._plan:
            return

        copy_mode = self._copy_checkbox.isChecked()
        reply = QMessageBox.question(
            self,
            "Confirm Sort",
            f"{'Copy' if copy_mode else 'Move'} {len(self._plan)} files to the target folder?\n\nThis cannot be undone.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply != QMessageBox.StandardButton.Yes:
            return

        self._progress.setVisible(True)
        self._progress.setRange(0, len(self._plan))
        self._progress.setValue(0)
        self._sort_btn.setEnabled(False)
        self._preview_btn.setEnabled(False)

        self._worker = _SortWorker(self._plan, copy_mode, parent=self)
        self._worker.progress.connect(self._on_worker_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_worker_progress(self, current: int, total: int, dest: str) -> None:
        self._progress.setValue(current)
        self._status.showMessage(f"Processing {current}/{total}: {dest}")

    def _on_worker_finished(self, success: int, errors: int) -> None:
        self._progress.setVisible(False)
        self._sort_btn.setEnabled(True)
        self._preview_btn.setEnabled(True)

        if errors == 0:
            QMessageBox.information(
                self, "Done", f"Successfully sorted {success} files."
            )
            self._status.showMessage(f"Done – {success} files sorted.")
        else:
            QMessageBox.warning(
                self,
                "Completed with Errors",
                f"Sorted {success} files successfully.\n{errors} file(s) failed – check the status bar.",
            )
            self._status.showMessage(f"Done – {success} OK, {errors} errors.")
