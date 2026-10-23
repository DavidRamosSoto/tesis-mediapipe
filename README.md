# Analisis de pose humana con MediaPipe

Proyecto de tesis para procesar videos localmente con MediaPipe Pose. Detecta
landmarks corporales, analiza el angulo configurado para el ejercicio seleccionado,
genera un video anotado y exporta coordenadas y mediciones.

## Requisitos

- Windows
- Python 3.11 de 64 bits
- Git

Python 3.11 es la version recomendada para instalaciones nuevas. El proyecto tambien
se probo correctamente con Python 3.14.6 en el entorno local existente.

Las dependencias de ejecucion estan fijadas en `requirements.txt`:

- MediaPipe para deteccion de pose.
- OpenCV y NumPy para video y procesamiento numerico.
- openpyxl para exportar las mediciones a Excel.
- PySide6, incluido QtCharts, para la interfaz y la grafica.

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

El repositorio incluye `mov.mp4` como video de ejemplo.

### Interfaz grafica

Inicia la aplicacion de escritorio:

```powershell
python Tesis_gui.py
```

Selecciona uno de los ejercicios, el video y la carpeta de resultados, luego
presiona **Procesar video**. Los 57 ejercicios estan embebidos en el programa y
siempre aparecen sin depender de un archivo Excel externo. El
angulo se calcula con `k_prev` como primer punto, `K` como vertice y `k_post` como
tercer punto. Si un ejercicio no tiene los tres landmarks definidos, la aplicacion
lo muestra pero bloquea el procesamiento para evitar un resultado incorrecto.
El Excel original se usa solo como referencia local para actualizar manualmente el
catalogo; no forma parte de la ejecucion ni se versiona en el repositorio.
El selector conserva los colores pastel del Excel para distinguir visualmente
los grupos de ejercicios; la paleta tambien esta embebida en el codigo y el color
de la prueba seleccionada permanece visible al cerrar el desplegable.
La interfaz permanece disponible mientras MediaPipe trabaja y permite abrir la
carpeta de resultados al finalizar. La opcion **Mostrar video durante el
procesamiento** presenta la vista anotada dentro del cuadro de video de la misma
aplicacion, sin abrir una ventana adicional de OpenCV.
Cuando MediaPipe obtiene la primera medicion, aparece debajo del video una grafica
de angulo contra frame. La curva se actualiza durante el procesamiento y permanece
visible al finalizar para revisar la evolucion del movimiento. El eje angular se
ajusta a los valores medidos para mostrar mejor variaciones pequenas, y la curva
usa marcadores dentro de un visor ampliado.

### Linea de comandos

Para procesar el video sin interfaz grafica, ejecuta:

```powershell
python Tesis.py
```

Para ver el video durante el procesamiento:

```powershell
python Tesis.py --display
```

Tambien puedes indicar otro video y directorio de salida:

```powershell
python Tesis.py --input ruta\video.mp4 --output-dir results --exercise "Flexion HOMBRO Derecho"
```

Presiona `q` para detener la visualizacion. El procesamiento genera en `results/`:

- Un CSV con coordenadas normalizadas de los landmarks.
- Un MP4 con el esqueleto dibujado.
- Un Excel con el ejercicio, angulo medido y ROM objetivo por frame detectado.

Los tres nombres incluyen la fecha y hora de la ejecucion.

## Estructura

- `Tesis.py`: aplicacion local principal.
- `Tesis_gui.py`: interfaz grafica de escritorio creada con PySide6.
- `requirements.txt`: dependencias Python necesarias para ejecutar el proyecto.
- `mov.mp4`: video de entrada de ejemplo.
- `results/`: salidas generadas; no se versionan.

No se versionan `Dataset Raw/`, `results/`, entornos virtuales, caches, archivos
del agente ni el Excel usado como referencia. Puedes reemplazar `mov.mp4` o indicar
otro archivo mediante `--input`.