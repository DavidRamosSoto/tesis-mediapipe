"""Interfaz grafica local para el analisis de pose humana."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import numpy as np
from numpy.typing import NDArray
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtCore import QObject, Qt, QThread, Signal, Slot
from PySide6.QtGui import QCloseEvent, QColor, QImage, QPainter, QPixmap, QResizeEvent
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QComboBox,
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStyle,
    QToolButton,
    QVBoxLayout,
    QWidget,
)

from Tesis import (
    DEFAULT_RESULTS_DIR,
    DEFAULT_VIDEO,
    EXERCISE_CONFIGS,
    EXERCISE_OPTION_COLORS,
    ExerciseConfig,
    process_video,
)


class ProcessWorker(QObject):
    finished = Signal()
    failed = Signal(str)
    frame_ready = Signal(object)
    measurement_ready = Signal(int, float)

    def __init__(
        self,
        input_path: Path,
        output_dir: Path,
        show_preview: bool,
        exercise_name: str,
    ) -> None:
        super().__init__()
        self.input_path = input_path
        self.output_dir = output_dir
        self.show_preview = show_preview
        self.exercise_name = exercise_name

    @Slot()
    def run(self) -> None:
        try:
            frame_callback = self.frame_ready.emit if self.show_preview else None
            process_video(
                self.input_path,
                self.output_dir,
                display=False,
                frame_callback=frame_callback,
                exercise_name=self.exercise_name,
                measurement_callback=self.measurement_ready.emit,
            )
        except (OSError, RuntimeError, ValueError) as error:
            self.failed.emit(str(error))
        else:
            self.finished.emit()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self._thread: QThread | None = None
        self._worker: ProcessWorker | None = None
        self._current_pixmap: QPixmap | None = None
        self._compact_layout: bool | None = None
        self._selected_exercise = ""
        self._minimum_angle: float | None = None
        self._maximum_angle: float | None = None
        self.setWindowTitle("Analisis de pose humana")
        self.setMinimumSize(560, 520)
        self._build_interface()
        self._apply_style()
        self.resize(1000, 800)

    def _build_interface(self) -> None:
        content_widget = QWidget()
        content_widget.setObjectName("content")
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(36, 32, 36, 32)
        self.content_layout.setSpacing(22)

        title = QLabel("Analisis de pose humana")
        title.setObjectName("title")
        title.setWordWrap(True)
        title.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Preferred,
        )
        subtitle = QLabel(
            "Selecciona un video para detectar landmarks y exportar el analisis."
        )
        subtitle.setObjectName("subtitle")
        subtitle.setWordWrap(True)

        form = QGridLayout()
        form.setHorizontalSpacing(12)
        form.setVerticalSpacing(16)

        self.input_edit = QLineEdit(str(DEFAULT_VIDEO))
        self.input_edit.setPlaceholderText("Selecciona un archivo de video")
        input_button = self._browse_button(
            QStyle.StandardPixmap.SP_DialogOpenButton,
            "Seleccionar video",
            self._select_input,
        )

        self.output_edit = QLineEdit(str(DEFAULT_RESULTS_DIR))
        self.output_edit.setPlaceholderText("Selecciona la carpeta de resultados")
        output_button = self._browse_button(
            QStyle.StandardPixmap.SP_DirOpenIcon,
            "Seleccionar carpeta de resultados",
            self._select_output,
        )

        self.exercise_combo = QComboBox()
        self.exercise_combo.setToolTip("Seleccionar ejercicio para el analisis")
        self.exercise_combo.setSizeAdjustPolicy(
            QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon
        )
        self.exercise_combo.setMinimumContentsLength(28)
        first_configured_index = -1
        for configuration, option_color in zip(
            EXERCISE_CONFIGS, EXERCISE_OPTION_COLORS, strict=True
        ):
            option_index = self.exercise_combo.count()
            self.exercise_combo.addItem(configuration.name, configuration)
            self.exercise_combo.setItemData(
                option_index,
                QColor(option_color),
                Qt.ItemDataRole.BackgroundRole,
            )
            if (
                first_configured_index < 0
                and configuration.angle_landmarks is not None
            ):
                first_configured_index = self.exercise_combo.count() - 1
        if first_configured_index >= 0:
            self.exercise_combo.setCurrentIndex(first_configured_index)
        self.exercise_combo.currentIndexChanged.connect(
            self._update_exercise_selector_color
        )
        self._update_exercise_selector_color(self.exercise_combo.currentIndex())

        form.addWidget(QLabel("Ejercicio"), 0, 0, 1, 2)
        form.addWidget(self.exercise_combo, 1, 0, 1, 2)
        form.addWidget(QLabel("Video de entrada"), 2, 0, 1, 2)
        form.addWidget(self.input_edit, 3, 0)
        form.addWidget(input_button, 3, 1)
        form.addWidget(QLabel("Carpeta de resultados"), 4, 0, 1, 2)
        form.addWidget(self.output_edit, 5, 0)
        form.addWidget(output_button, 5, 1)
        form.setColumnStretch(0, 1)

        self.display_checkbox = QCheckBox("Mostrar video en la interfaz")
        self.display_checkbox.setChecked(True)

        self.preview_label = QLabel("Vista previa")
        self.preview_label.setObjectName("preview")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumSize(320, 180)
        self.preview_label.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )

        self.angle_series = QLineSeries()
        self.angle_series.setName("Angulo medido")
        angle_pen = self.angle_series.pen()
        angle_pen.setColor(QColor("#26734d"))
        angle_pen.setWidthF(2.5)
        self.angle_series.setPen(angle_pen)
        self.angle_series.setPointsVisible(True)
        self.angle_series.setMarkerSize(6)
        self.angle_chart = QChart()
        self.angle_chart.addSeries(self.angle_series)
        self.angle_chart.setTitle("Angulo vs frame")
        self.angle_chart.setBackgroundVisible(False)
        self.angle_chart.legend().hide()

        self.frame_axis = QValueAxis()
        self.frame_axis.setTitleText("Frame")
        self.frame_axis.setLabelFormat("%d")
        self.frame_axis.setRange(0, 1)
        self.angle_axis = QValueAxis()
        self.angle_axis.setTitleText("Angulo (grados)")
        self.angle_axis.setLabelFormat("%.1f")
        self.angle_axis.setTickCount(6)
        self.angle_axis.setRange(0, 180)
        self.angle_chart.addAxis(self.frame_axis, Qt.AlignmentFlag.AlignBottom)
        self.angle_chart.addAxis(self.angle_axis, Qt.AlignmentFlag.AlignLeft)
        self.angle_series.attachAxis(self.frame_axis)
        self.angle_series.attachAxis(self.angle_axis)

        self.angle_chart_view = QChartView(self.angle_chart)
        self.angle_chart_view.setObjectName("angleChart")
        self.angle_chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.angle_chart_view.setMinimumSize(320, 360)
        self.angle_chart_view.setSizePolicy(
            QSizePolicy.Policy.Ignored,
            QSizePolicy.Policy.Expanding,
        )
        self.angle_chart_view.setVisible(False)

        self.progress = QProgressBar()
        self.progress.setRange(0, 1)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)

        self.status_label = QLabel("Listo para procesar")
        self.status_label.setObjectName("status")
        self.status_label.setWordWrap(True)

        self.actions_layout = QGridLayout()
        self.actions_layout.setHorizontalSpacing(12)
        self.actions_layout.setVerticalSpacing(8)
        self.open_results_button = QPushButton("Abrir resultados")
        self.open_results_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_DirOpenIcon)
        )
        self.open_results_button.clicked.connect(self._open_results)

        self.process_button = QPushButton("Procesar video")
        self.process_button.setObjectName("primaryButton")
        self.process_button.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_MediaPlay)
        )
        self.process_button.clicked.connect(self._start_processing)

        self.content_layout.addWidget(title)
        self.content_layout.addWidget(subtitle)
        self.content_layout.addSpacing(6)
        self.content_layout.addLayout(form)
        self.content_layout.addWidget(self.display_checkbox)
        self.content_layout.addWidget(self.preview_label, 1)
        self.content_layout.addWidget(self.angle_chart_view, 1)
        self.content_layout.addWidget(self.progress)
        self.content_layout.addWidget(self.status_label)
        self.content_layout.addLayout(self.actions_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setObjectName("contentScroll")
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setVerticalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAsNeeded
        )
        self.scroll_area.setWidget(content_widget)

        self.scroll_indicator = QPushButton("Ver mas contenido")
        self.scroll_indicator.setObjectName("scrollIndicator")
        self.scroll_indicator.setIcon(
            self.style().standardIcon(QStyle.StandardPixmap.SP_ArrowDown)
        )
        self.scroll_indicator.setToolTip("Desplazar hacia el contenido oculto")
        self.scroll_indicator.clicked.connect(self._scroll_to_hidden_content)
        self.scroll_indicator.setVisible(False)

        root_widget = QWidget()
        root_layout = QVBoxLayout(root_widget)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)
        root_layout.addWidget(self.scroll_area, 1)
        root_layout.addWidget(self.scroll_indicator)
        self.setCentralWidget(root_widget)

        vertical_scrollbar = self.scroll_area.verticalScrollBar()
        vertical_scrollbar.rangeChanged.connect(self._scroll_range_changed)
        vertical_scrollbar.valueChanged.connect(self._scroll_value_changed)
        self._update_responsive_layout()

    def _browse_button(
        self,
        icon: QStyle.StandardPixmap,
        tooltip: str,
        callback: object,
    ) -> QToolButton:
        button = QToolButton()
        button.setIcon(self.style().standardIcon(icon))
        button.setToolTip(tooltip)
        button.setFixedSize(40, 36)
        button.clicked.connect(callback)  # type: ignore[arg-type]
        return button

    @Slot(int)
    def _update_exercise_selector_color(self, index: int) -> None:
        color = self.exercise_combo.itemData(index, Qt.ItemDataRole.BackgroundRole)
        if not isinstance(color, QColor):
            return
        color_name = color.name()
        self.exercise_combo.setStyleSheet(
            f"QComboBox {{ background-color: {color_name}; }}"
            f"QComboBox:disabled {{ background-color: {color_name}; }}"
        )

    @Slot()
    def _select_input(self) -> None:
        selected_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar video",
            self.input_edit.text(),
            "Videos (*.mp4 *.avi *.mov *.mkv);;Todos los archivos (*)",
        )
        if selected_path:
            self.input_edit.setText(selected_path)

    @Slot()
    def _select_output(self) -> None:
        selected_path = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de resultados",
            self.output_edit.text(),
        )
        if selected_path:
            self.output_edit.setText(selected_path)

    @Slot()
    def _start_processing(self) -> None:
        input_path = Path(self.input_edit.text().strip()).expanduser()
        output_dir = Path(self.output_edit.text().strip()).expanduser()

        if not input_path.is_file():
            QMessageBox.warning(self, "Video no encontrado", "Selecciona un video valido.")
            return
        if not self.output_edit.text().strip():
            QMessageBox.warning(
                self, "Carpeta no valida", "Selecciona una carpeta de resultados."
            )
            return

        exercise_configuration = self.exercise_combo.currentData()
        if not isinstance(exercise_configuration, ExerciseConfig):
            QMessageBox.warning(
                self,
                "Ejercicio no disponible",
                "No se pudo cargar la configuracion del ejercicio.",
            )
            return
        if exercise_configuration.angle_landmarks is None:
            QMessageBox.warning(
                self,
                "Configuracion pendiente",
                f"El ejercicio '{exercise_configuration.name}' no tiene valores "
                "numericos completos en K, k_prev y k_post.",
            )
            return

        self._set_processing_state(True)
        self._selected_exercise = exercise_configuration.name
        self.status_label.setText(
            f"Procesando {input_path.name}: {self._selected_exercise}..."
        )
        self._current_pixmap = None
        self.preview_label.clear()
        self.preview_label.setText("Preparando vista previa...")
        self.angle_series.clear()
        self.frame_axis.setRange(0, 1)
        self.angle_axis.setRange(0, 180)
        self._minimum_angle = None
        self._maximum_angle = None
        self.angle_chart.setTitle(f"{self._selected_exercise}: angulo vs frame")
        self.angle_chart_view.setVisible(False)

        self._thread = QThread(self)
        self._worker = ProcessWorker(
            input_path,
            output_dir,
            self.display_checkbox.isChecked(),
            self._selected_exercise,
        )
        self._worker.moveToThread(self._thread)
        self._thread.started.connect(self._worker.run)
        self._worker.finished.connect(self._processing_succeeded)
        self._worker.failed.connect(self._processing_failed)
        self._worker.frame_ready.connect(self._update_preview)
        self._worker.measurement_ready.connect(self._update_angle_chart)
        self._worker.finished.connect(self._thread.quit)
        self._worker.failed.connect(self._thread.quit)
        self._thread.finished.connect(self._worker.deleteLater)
        self._thread.finished.connect(self._thread_finished)
        self._thread.start()

    @Slot()
    def _processing_succeeded(self) -> None:
        self._set_processing_state(False)
        self.status_label.setText("Procesamiento completado. Los archivos estan listos.")
        QMessageBox.information(
            self,
            "Proceso completado",
            f"Ejercicio: {self._selected_exercise}\n\n"
            "Se generaron el CSV, el video anotado y el archivo Excel.",
        )

    @Slot(str)
    def _processing_failed(self, message: str) -> None:
        self._set_processing_state(False)
        self.status_label.setText("No se pudo completar el procesamiento.")
        QMessageBox.critical(self, "Error de procesamiento", message)

    @Slot()
    def _thread_finished(self) -> None:
        if self._thread is not None:
            self._thread.deleteLater()
        self._thread = None
        self._worker = None

    def _set_processing_state(self, processing: bool) -> None:
        self.input_edit.setEnabled(not processing)
        self.output_edit.setEnabled(not processing)
        self.exercise_combo.setEnabled(not processing)
        self.display_checkbox.setEnabled(not processing)
        self.process_button.setEnabled(not processing)
        self.open_results_button.setEnabled(not processing)
        self.progress.setRange(0, 0 if processing else 1)
        if not processing:
            self.progress.setValue(1)

    @Slot(object)
    def _update_preview(self, frame: NDArray[np.uint8]) -> None:
        height, width, channels = frame.shape
        bytes_per_line = channels * width
        image = QImage(
            frame.data,
            width,
            height,
            bytes_per_line,
            QImage.Format.Format_BGR888,
        ).copy()
        self._current_pixmap = QPixmap.fromImage(image)
        self._show_current_pixmap()

    def _show_current_pixmap(self) -> None:
        if self._current_pixmap is None:
            return
        scaled_pixmap = self._current_pixmap.scaled(
            self.preview_label.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.preview_label.setPixmap(scaled_pixmap)

    @Slot(int, float)
    def _update_angle_chart(self, frame: int, angle: float) -> None:
        self.angle_series.append(frame, angle)
        self.frame_axis.setRange(0, max(1, frame))
        self._minimum_angle = (
            angle if self._minimum_angle is None else min(self._minimum_angle, angle)
        )
        self._maximum_angle = (
            angle if self._maximum_angle is None else max(self._maximum_angle, angle)
        )
        self._update_angle_axis_range()
        if not self.angle_chart_view.isVisible():
            self.angle_chart_view.setVisible(True)

    def _update_angle_axis_range(self) -> None:
        if self._minimum_angle is None or self._maximum_angle is None:
            return

        angle_span = self._maximum_angle - self._minimum_angle
        padding = max(2.0, angle_span * 0.1)
        lower_bound = max(0.0, self._minimum_angle - padding)
        upper_bound = min(180.0, self._maximum_angle + padding)
        minimum_visible_span = 20.0
        if upper_bound - lower_bound < minimum_visible_span:
            center = (self._minimum_angle + self._maximum_angle) / 2
            lower_bound = max(0.0, center - minimum_visible_span / 2)
            upper_bound = min(180.0, center + minimum_visible_span / 2)
            if lower_bound == 0.0:
                upper_bound = minimum_visible_span
            elif upper_bound == 180.0:
                lower_bound = 180.0 - minimum_visible_span
        self.angle_axis.setRange(lower_bound, upper_bound)

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_responsive_layout()
        self._show_current_pixmap()

    def _update_responsive_layout(self) -> None:
        if not hasattr(self, "content_layout"):
            return

        compact = self.width() < 760
        if compact:
            self.content_layout.setContentsMargins(12, 14, 12, 14)
            self.content_layout.setSpacing(10)
        else:
            self.content_layout.setContentsMargins(36, 32, 36, 32)
            self.content_layout.setSpacing(22)

        if compact == self._compact_layout:
            return

        self.actions_layout.removeWidget(self.open_results_button)
        self.actions_layout.removeWidget(self.process_button)
        if compact:
            self.actions_layout.setColumnStretch(1, 0)
            self.actions_layout.addWidget(self.process_button, 0, 0, 1, 3)
            self.actions_layout.addWidget(self.open_results_button, 1, 0, 1, 3)
        else:
            self.actions_layout.addWidget(self.open_results_button, 0, 0)
            self.actions_layout.setColumnStretch(1, 1)
            self.actions_layout.addWidget(self.process_button, 0, 2)
        self._compact_layout = compact

    @Slot(int, int)
    def _scroll_range_changed(self, minimum: int, maximum: int) -> None:
        self.scroll_indicator.setVisible(maximum > minimum)
        self._update_scroll_indicator()

    @Slot(int)
    def _scroll_value_changed(self, _value: int) -> None:
        self._update_scroll_indicator()

    def _update_scroll_indicator(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        at_bottom = scrollbar.value() >= scrollbar.maximum()
        if at_bottom:
            text = "Ver contenido anterior"
            icon = QStyle.StandardPixmap.SP_ArrowUp
        else:
            text = "Ver mas contenido"
            icon = QStyle.StandardPixmap.SP_ArrowDown
        self.scroll_indicator.setText(text)
        self.scroll_indicator.setIcon(self.style().standardIcon(icon))

    @Slot()
    def _scroll_to_hidden_content(self) -> None:
        scrollbar = self.scroll_area.verticalScrollBar()
        if scrollbar.value() >= scrollbar.maximum():
            scrollbar.setValue(scrollbar.minimum())
        else:
            scrollbar.setValue(scrollbar.maximum())

    @Slot()
    def _open_results(self) -> None:
        output_dir = Path(self.output_edit.text().strip()).expanduser()
        output_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(output_dir.resolve())

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._thread is not None and self._thread.isRunning():
            QMessageBox.information(
                self,
                "Procesamiento en curso",
                "Espera a que termine el procesamiento antes de cerrar la aplicacion.",
            )
            event.ignore()
            return
        event.accept()

    def _apply_style(self) -> None:
        self.setStyleSheet(
            """
            QMainWindow { background: #f4f6f3; }
            QScrollArea#contentScroll { border: 0; background: #f4f6f3; }
            QScrollBar:vertical {
                background: #dce2de;
                width: 14px;
                margin: 2px;
            }
            QScrollBar::handle:vertical {
                background: #26734d;
                border-radius: 5px;
                min-height: 36px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0;
            }
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: transparent;
            }
            QWidget#content { background: #f4f6f3; }
            QWidget { color: #202722; font-family: "Aptos"; font-size: 14px; }
            QLabel#title { font-size: 28px; font-weight: 700; color: #173b2c; }
            QLabel#subtitle { color: #58655d; font-size: 15px; }
            QLabel#status { color: #425149; }
            QLabel#preview {
                background: #141915;
                border: 1px solid #354239;
                border-radius: 6px;
                color: #aeb9b1;
            }
            QChartView#angleChart {
                background: #ffffff;
                border: 1px solid #b9c3bc;
                border-radius: 6px;
            }
            QLineEdit {
                background: #ffffff;
                border: 1px solid #b9c3bc;
                border-radius: 6px;
                padding: 8px 10px;
                selection-background-color: #26734d;
            }
            QComboBox {
                background: #ffffff;
                border: 1px solid #b9c3bc;
                border-radius: 6px;
                padding: 8px 10px;
            }
            QComboBox:focus { border: 2px solid #26734d; padding: 7px 9px; }
            QComboBox:disabled { color: #87928a; background: #e3e7e4; }
            QLineEdit:focus { border: 2px solid #26734d; padding: 7px 9px; }
            QToolButton, QPushButton {
                background: #ffffff;
                border: 1px solid #aeb9b1;
                border-radius: 6px;
                padding: 8px 14px;
            }
            QToolButton:hover, QPushButton:hover { background: #e7ece8; }
            QPushButton#primaryButton {
                background: #26734d;
                border-color: #26734d;
                color: #ffffff;
                font-weight: 600;
                padding: 9px 18px;
            }
            QPushButton#primaryButton:hover { background: #1f6040; }
            QPushButton#scrollIndicator {
                background: #e7ece8;
                border: 0;
                border-top: 1px solid #aeb9b1;
                border-radius: 0;
                color: #173b2c;
                font-weight: 600;
                padding: 7px 12px;
            }
            QPushButton#scrollIndicator:hover { background: #dce5df; }
            QPushButton:disabled { color: #87928a; background: #e3e7e4; }
            QProgressBar {
                background: #dce2de;
                border: 0;
                border-radius: 4px;
                min-height: 8px;
                max-height: 8px;
            }
            QProgressBar::chunk { background: #d9882b; border-radius: 4px; }
            """
        )


def main() -> None:
    application = QApplication(sys.argv)
    application.setApplicationName("Analisis de pose humana")
    window = MainWindow()
    window.show()
    raise SystemExit(application.exec())


if __name__ == "__main__":
    main()