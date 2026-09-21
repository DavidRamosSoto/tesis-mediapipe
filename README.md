# Analisis de pose humana con MediaPipe

Proyecto de tesis para procesar videos localmente con MediaPipe Pose. Detecta landmarks corporales, genera un video anotado y exporta coordenadas y angulos del hombro derecho.

## Requisitos

- Windows
- Python 3.11 de 64 bits
- Git

Python 3.14 no es compatible con la version de MediaPipe usada por este proyecto.

## Instalacion

Clona el repositorio y entra en su carpeta:

```powershell
git clone <URL_DEL_REPOSITORIO>
cd Tesis
```

Crea y activa un entorno virtual:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## Uso

Coloca un video llamado `mov.mp4` en la raiz del proyecto y ejecuta:

```powershell
python Tesis.py
```

Para ver el video durante el procesamiento:

```powershell
python Tesis.py --display
```

Tambien puedes indicar otro video y directorio de salida:

```powershell
python Tesis.py --input ruta\video.mp4 --output-dir results
```

Presiona `q` para detener la visualizacion. El procesamiento genera en `results/`:

- Un CSV con coordenadas normalizadas de los landmarks.
- Un MP4 con el esqueleto dibujado.
- Un Excel con el angulo del hombro derecho por frame detectado.

Los tres nombres incluyen la fecha y hora de la ejecucion.

## Estructura

- `Tesis.py`: aplicacion local principal.
- `Human_Pose_MediaPipe.ipynb`: notebook original de experimentacion.
- `human_pose_mediapipe.py`: exportacion original de Colab, conservada como referencia.
- `results/`: salidas generadas; no se versionan.

Los archivos de video tampoco se versionan. Cada usuario debe proporcionar su propia entrada.