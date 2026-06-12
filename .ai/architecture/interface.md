# Arquitectura de Interfaz de Usuario (.ai/architecture/interface.md)

Este documento describe las directrices para operar y modificar la interfaz de usuario del plugin DRT.

---

## 1. Stack Tecnológico de UI
*   **Framework:** PyQt5 integrado en QGIS.
*   **Diseño:** Archivos XML `.ui` creados en QtDesigner.
*   **Estilo:** QGIS nativo (aprovecha la hoja de estilos de QGIS para mantener consistencia visual).

---

## 2. Carga Dinámica de UI
Para evitar la necesidad de compilar manualmente los archivos `.ui` a código Python (`pyuic5`), el plugin utiliza la carga al vuelo de PyQt:
```python
import os
from qgis.PyQt import uic

UI_FILE = os.path.join(os.path.dirname(__file__), 'nombre_del_componente.ui')
FORM_CLASS, BASE_CLASS = uic.loadUiType(UI_FILE)
```
Esto facilita enormemente la edición del diseño en QtDesigner y la recarga al vuelo con el plugin *Plugin Reloader* en QGIS.

---

## 3. Reglas de Programación en la UI
*   **No bloquear el hilo principal:** Cualquier geoproceso, instalación o cálculo matemático pesado debe ejecutarse en un hilo secundario (`QThread`) o mediante tareas asíncronas (`QgsTask`).
*   **Carga Perezosa de Dependencias (Lazy Loading):** Los módulos analíticos del backend (ej. `pandas`, `sklearn`, `geopandas`) **nunca** deben importarse a nivel de cabecera en los archivos de la interfaz (`ui/`). Deben ser importados de forma local únicamente cuando se verifiquen dependencias o cuando se ejecute la acción correspondiente.
*   **Manejo de Errores Amigable:** Toda llamada al backend debe estar envuelta en bloques `try-except` capturando excepciones específicas e informando al usuario mediante `QMessageBox` o registros en la consola interna.
