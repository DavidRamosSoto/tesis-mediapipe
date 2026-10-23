"""Procesa un video local con MediaPipe Pose y exporta sus resultados."""

from __future__ import annotations

import argparse
import csv
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import cast

import cv2
import mediapipe.python.solutions.drawing_utils as drawing_utils
import mediapipe.python.solutions.pose as pose_module
import numpy as np
from numpy.typing import NDArray
from openpyxl import Workbook


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_VIDEO = PROJECT_ROOT / "mov.mp4"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"
DEFAULT_EXERCISE = "Flexion HOMBRO Derecho"
LANDMARK_NAMES = [landmark.name.lower() for landmark in pose_module.PoseLandmark]


@dataclass
class Point:
    x: float
    y: float


@dataclass
class Body:
    frame: int
    points: list[Point] = field(default_factory=list)

    def get_angle(self, point1: int, vertex: int, point3: int) -> float:
        if min(point1, vertex, point3) < 0 or max(point1, vertex, point3) >= len(self.points):
            raise ValueError("Indice de landmark fuera de rango")

        first = self.points[point1]
        center = self.points[vertex]
        third = self.points[point3]
        vector1 = (first.x - center.x, first.y - center.y)
        vector2 = (third.x - center.x, third.y - center.y)
        magnitude1 = math.hypot(*vector1)
        magnitude2 = math.hypot(*vector2)

        if magnitude1 == 0 or magnitude2 == 0:
            raise ValueError("No se puede calcular un angulo con un vector de longitud cero")

        cosine = (vector1[0] * vector2[0] + vector1[1] * vector2[1]) / (
            magnitude1 * magnitude2
        )
        return math.degrees(math.acos(max(-1.0, min(1.0, cosine))))


@dataclass(frozen=True)
class ExerciseConfig:
    name: str
    rom: float | None
    vertex: int | None = None
    previous: int | None = None
    following: int | None = None

    @property
    def angle_landmarks(self) -> tuple[int, int, int] | None:
        if self.previous is None or self.vertex is None or self.following is None:
            return None
        return self.previous, self.vertex, self.following


EXERCISE_CONFIGS: tuple[ExerciseConfig, ...] = (
    ExerciseConfig("Flexion  CUELLO", 40),
    ExerciseConfig("Extension  CUELLO", 40),
    ExerciseConfig("Lateralizacion Derecha CUELLO", 40),
    ExerciseConfig("Lateralizacion Izquierda CUELLO", 40),
    ExerciseConfig("Rotacion Derecha  CUELLO", 90),
    ExerciseConfig("Rotacion Izquierda CUELLO", 90),
    ExerciseConfig("Flexion HOMBRO Derecho", 175, vertex=12, previous=11, following=14),
    ExerciseConfig("Extension  HOMBRO Derecho", 50),
    ExerciseConfig("Rot. Int. HOMBRO Derecho", 80, vertex=14, previous=12, following=16),
    ExerciseConfig("Rot. Ext. HOMBRO Derecho", 55, vertex=14, previous=12, following=16),
    ExerciseConfig("Flexion HOMBRO Izquierdo", 175, vertex=11, previous=12, following=13),
    ExerciseConfig("Extension  HOMBRO Izquierdo", 50),
    ExerciseConfig("Rot. Int.  HOMBRO Izquierdo", 80, vertex=13, previous=11, following=15),
    ExerciseConfig("Rot. Ext. HOMBRO Izquierdo", 55, vertex=13, previous=11, following=15),
    ExerciseConfig("Flexion   TRONCO Derecho", 80, vertex=24, previous=26, following=12),
    ExerciseConfig("Flexion   TRONCO izquerdo", 80, vertex=23, previous=25, following=11),
    ExerciseConfig("Extension  TRONCO", 30),
    ExerciseConfig("Lateralizacion Derecha TRONCO", 35),
    ExerciseConfig("Rotacion Derecha  TRONCO", 35),
    ExerciseConfig("LateralizacionIzquierda TRONCO", 35),
    ExerciseConfig("Rotacion Izquierda  TRONCO", 35),
    ExerciseConfig("ABD CADERA Derecha", 50),
    ExerciseConfig("ADD CADERA Derecha", 25),
    ExerciseConfig("Flexion CADERA Derecha", 130),
    ExerciseConfig("Extension  CADERA Derecha", 30),
    ExerciseConfig("Rot. Int.CADERA Derecha", 50),
    ExerciseConfig("Rot. Ext. Cadera Derecha", 45),
    ExerciseConfig("ABD Cadera Izquierda", 50),
    ExerciseConfig("ADD Cadera Izquierda", 25),
    ExerciseConfig("Flexion Cadera Izquierda", 130),
    ExerciseConfig("Extension  Cadera Izquierda", 30),
    ExerciseConfig("Rot. Int. Cadera Izquierda", 50),
    ExerciseConfig("Rot. Ext. Cadera Izquierda", 45),
    ExerciseConfig("Flexion Rodilla Derecha", 145),
    ExerciseConfig("Extension  Rodilla Derecha", 10),
    ExerciseConfig("Tencion QUAD  Derecha", 80),
    ExerciseConfig("PSOAS Derecha", 5),
    ExerciseConfig("Flexion Rodilla Izquierda", 145),
    ExerciseConfig("Extension  Rodilla Izquierda", 10),
    ExerciseConfig("Tencion QUAD  Izquierda", 80),
    ExerciseConfig("PSOAS Izquierda", 5),
    ExerciseConfig("Dorsiflexion TOBILLO Derecha", 50, vertex=26, previous=28, following=24),
    ExerciseConfig("Extension  Tobillo Derecha", 30),
    ExerciseConfig("Dorsiflexion TOBILLO Izquierda", 50, vertex=25, previous=27, following=23),
    ExerciseConfig("Extension  Tobillo Izquierda", 30),
    ExerciseConfig("Flexion  Hallux Derecha", 45),
    ExerciseConfig("Extension  Hallux Derecha", 70),
    ExerciseConfig("FlexionHallux Izquierda", 45),
    ExerciseConfig("Extension  Hallux Izquierda", 70),
    ExerciseConfig("Test biering score H", 195),
    ExerciseConfig("Plancha lat Der H", 97),
    ExerciseConfig("Plancha lat Izq H", 97),
    ExerciseConfig("Flexion de tronco H", 149),
    ExerciseConfig("Test biering score M", 189),
    ExerciseConfig("Plancha lat Der M", 77),
    ExerciseConfig("Plancha lat Izq M", 77),
    ExerciseConfig("Flexion de tronco M", 144),
)

EXERCISE_OPTION_COLORS: tuple[str, ...] = (
    ("#E6B8AF",) * 6
    + ("#F4CCCC",) * 8
    + ("#FCE5CD",) * 7
    + ("#FFF2CC",) * 12
    + ("#D9EAD3",) * 8
    + ("#D0E0E3",) * 4
    + ("#C9DAF8",) * 4
    + ("#9FC5E8",) * 4
    + ("#EAD1DC",) * 4
)


def get_exercise_config(exercise_name: str) -> ExerciseConfig:
    normalized_name = exercise_name.strip()
    for configuration in EXERCISE_CONFIGS:
        if configuration.name == normalized_name:
            return configuration
    raise ValueError(f"No se encontro el ejercicio: {exercise_name}")


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detecta pose humana en un video local con MediaPipe."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument("--exercise", default=DEFAULT_EXERCISE)
    parser.add_argument(
        "--display",
        action="store_true",
        help="Muestra el video durante el procesamiento; presiona q para detenerlo.",
    )
    return parser.parse_args()


def export_exercise_angles(
    bodies: list[Body], output_path: Path, configuration: ExerciseConfig
) -> None:
    landmarks = configuration.angle_landmarks
    if landmarks is None:
        raise ValueError(
            f"El ejercicio '{configuration.name}' no tiene K, k_prev y k_post "
            "numericos completos en el archivo de analisis"
        )

    previous, vertex, following = landmarks
    workbook = Workbook()
    worksheet = workbook.active
    if worksheet is None:
        raise RuntimeError("No se pudo crear la hoja de Excel")
    worksheet.title = "Movement Angles"
    worksheet.append(["Frame", "Exercise", "Measured Angle", "ROM Target"])

    for body in bodies:
        try:
            angle = body.get_angle(previous, vertex, following)
        except ValueError:
            continue
        worksheet.append([body.frame, configuration.name, angle, configuration.rom])

    workbook.save(output_path)


def process_video(
    input_path: Path,
    output_dir: Path,
    display: bool = False,
    frame_callback: Callable[[NDArray[np.uint8]], None] | None = None,
    exercise_name: str = DEFAULT_EXERCISE,
    measurement_callback: Callable[[int, float], None] | None = None,
) -> None:
    input_path = input_path.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"No se encontro el video de entrada: {input_path}")

    exercise_configuration = get_exercise_config(exercise_name)
    if exercise_configuration.angle_landmarks is None:
        raise ValueError(
            f"El ejercicio '{exercise_configuration.name}' todavia no tiene una "
            "configuracion angular completa (K, k_prev, k_post)"
        )
    angle_landmarks = exercise_configuration.angle_landmarks

    output_dir.mkdir(parents=True, exist_ok=True)
    creation_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = output_dir / f"{input_path.stem}_landmarks_{creation_date}.csv"
    annotated_video_path = output_dir / f"{input_path.stem}_annotated_{creation_date}.mp4"
    angles_path = output_dir / f"{input_path.stem}_movement_angles_{creation_date}.xlsx"

    capture = cv2.VideoCapture(str(input_path))
    if not capture.isOpened():
        raise RuntimeError(f"No se pudo abrir el video: {input_path}")

    width = int(capture.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(capture.get(cv2.CAP_PROP_FRAME_HEIGHT))
    frames_per_second = capture.get(cv2.CAP_PROP_FPS) or 30.0
    fourcc = cv2.VideoWriter.fourcc(*"mp4v")

    writer = cv2.VideoWriter(
        str(annotated_video_path),
        fourcc,
        frames_per_second,
        (width, height),
    )
    if not writer.isOpened():
        capture.release()
        raise RuntimeError(f"No se pudo crear el video de salida: {annotated_video_path}")

    point_style = drawing_utils.DrawingSpec(
        color=(220, 100, 0), thickness=2, circle_radius=4
    )
    line_style = drawing_utils.DrawingSpec(color=(0, 255, 0), thickness=2)
    bodies: list[Body] = []
    frame_number = 0

    try:
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            csv_writer = csv.writer(csv_file)
            csv_writer.writerow(["frame", "coordinate", *LANDMARK_NAMES])

            with pose_module.Pose(static_image_mode=False) as pose:
                while True:
                    success, frame = capture.read()
                    if not success:
                        break

                    frame_number += 1
                    results = pose.process(cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
                    annotated_frame = frame.copy()

                    if results.pose_landmarks:
                        landmarks = results.pose_landmarks.landmark
                        body = Body(
                            frame_number,
                            [Point(landmark.x, landmark.y) for landmark in landmarks],
                        )
                        bodies.append(body)
                        if measurement_callback is not None:
                            try:
                                angle = body.get_angle(*angle_landmarks)
                            except ValueError:
                                pass
                            else:
                                measurement_callback(frame_number, angle)
                        csv_writer.writerow(
                            [frame_number, "x", *(landmark.x for landmark in landmarks)]
                        )
                        csv_writer.writerow(
                            [frame_number, "y", *(landmark.y for landmark in landmarks)]
                        )
                        drawing_utils.draw_landmarks(
                            annotated_frame,
                            results.pose_landmarks,
                            pose_module.POSE_CONNECTIONS,
                            point_style,
                            line_style,
                        )

                    writer.write(annotated_frame)
                    if frame_callback is not None:
                        frame_callback(cast(NDArray[np.uint8], annotated_frame))
                    if display:
                        cv2.imshow("MediaPipe Pose", annotated_frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
    finally:
        capture.release()
        writer.release()
        if display:
            cv2.destroyAllWindows()

    export_exercise_angles(bodies, angles_path, exercise_configuration)
    print(f"Frames procesados: {frame_number}")
    print(f"Poses detectadas: {len(bodies)}")
    print(f"Ejercicio: {exercise_configuration.name}")
    print(f"Landmarks: {csv_path}")
    print(f"Video anotado: {annotated_video_path}")
    print(f"Angulos del movimiento: {angles_path}")


def main() -> None:
    arguments = parse_arguments()
    process_video(
        arguments.input,
        arguments.output_dir,
        arguments.display,
        exercise_name=arguments.exercise,
    )


if __name__ == "__main__":
    main()