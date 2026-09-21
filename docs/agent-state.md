# Estado del Proyecto

## Entorno
- Sistema operativo: Windows
- Versión de Python: 3.11
- Entorno virtual: `.venv`
- Instalación: `.venv\\Scripts\\python.exe -m pip install -r requirements.txt`
- Ejecución: `.venv\\Scripts\\python.exe Tesis.py`

## Estructura
- Video principal: `mov.mp4`
- Imagen de prueba:
- Modelo EfficientSAM XML:
- Modelo EfficientSAM BIN:
- Directorio de resultados: `results/`

## Último Cambio
- Se preparo el proyecto para GitHub: `README.md`, `.gitignore`, dependencias minimas en `requirements.txt` y repositorio Git local sobre la rama `main`. Se incluye `mov.mp4` como video de ejemplo; `.venv`, `results/` y los videos generados quedan excluidos.

## Problemas Conocidos
- `human_pose_mediapipe.py` conserva comandos de Colab y rutas `/content/drive`.
- Python 3.14 no es compatible con `mediapipe==0.10.21`; usar Python 3.11.
- GitHub CLI (`gh`) no esta instalado, por lo que la publicacion remota aun no se realizo.

## Próximo Paso
- Inicializar Git, crear el primer commit y publicar el repositorio en GitHub despues de definir nombre y visibilidad.