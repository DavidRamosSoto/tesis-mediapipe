"""Procesa un video local con MediaPipe Pose y exporta sus resultados."""

from __future__ import annotations

import argparse
import csv
import math
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

import cv2
import mediapipe.python.solutions.drawing_utils as drawing_utils
import mediapipe.python.solutions.pose as pose_module
from openpyxl import Workbook


PROJECT_ROOT = Path(__file__).resolve().parent
DEFAULT_VIDEO = PROJECT_ROOT / "mov.mp4"
DEFAULT_RESULTS_DIR = PROJECT_ROOT / "results"
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


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Detecta pose humana en un video local con MediaPipe."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_VIDEO)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_RESULTS_DIR)
    parser.add_argument(
        "--display",
        action="store_true",
        help="Muestra el video durante el procesamiento; presiona q para detenerlo.",
    )
    return parser.parse_args()


def export_shoulder_angles(bodies: list[Body], output_path: Path) -> None:
    workbook = Workbook()
    worksheet = workbook.active
    if worksheet is None:
        raise RuntimeError("No se pudo crear la hoja de Excel")
    worksheet.title = "Shoulder Angles"
    worksheet.append(["Frame", "Right Shoulder Angle"])

    for body in bodies:
        try:
            angle = body.get_angle(14, 12, 24)
        except ValueError:
            continue
        worksheet.append([body.frame, angle])

    workbook.save(output_path)


def process_video(input_path: Path, output_dir: Path, display: bool = False) -> None:
    input_path = input_path.resolve()
    if not input_path.is_file():
        raise FileNotFoundError(f"No se encontro el video de entrada: {input_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    creation_date = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    csv_path = output_dir / f"{input_path.stem}_landmarks_{creation_date}.csv"
    annotated_video_path = output_dir / f"{input_path.stem}_annotated_{creation_date}.mp4"
    angles_path = output_dir / f"{input_path.stem}_shoulder_angles_{creation_date}.xlsx"

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
                        bodies.append(
                            Body(
                                frame_number,
                                [Point(landmark.x, landmark.y) for landmark in landmarks],
                            )
                        )
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
                    if display:
                        cv2.imshow("MediaPipe Pose", annotated_frame)
                        if cv2.waitKey(1) & 0xFF == ord("q"):
                            break
    finally:
        capture.release()
        writer.release()
        if display:
            cv2.destroyAllWindows()

    export_shoulder_angles(bodies, angles_path)
    print(f"Frames procesados: {frame_number}")
    print(f"Poses detectadas: {len(bodies)}")
    print(f"Landmarks: {csv_path}")
    print(f"Video anotado: {annotated_video_path}")
    print(f"Angulos de hombro: {angles_path}")


def main() -> None:
    arguments = parse_arguments()
    process_video(arguments.input, arguments.output_dir, arguments.display)


if __name__ == "__main__":
    main()