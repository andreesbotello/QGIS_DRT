# Arquitectura de Pruebas (.ai/architecture/testing.md)

Este documento detalla las metodologías y consideraciones para la ejecución de pruebas unitarias y de integración en el plugin DRT.

---

## 1. Marco de Trabajo
*   **Herramienta:** `pytest`.
*   **Ubicación:** Las pruebas están alojadas en la carpeta [drt_plugin/tests/](drt_plugin/tests/).
*   **Enfoque:** Validar el comportamiento matemático y la lógica espacial de los componentes del backend (Memoria 1 y Memoria 2) fuera de QGIS.

---

## 2. Consideración Crítica en Windows (Carga de DLLs de GDAL)
Dado que el backend utiliza la librería `osgeo` (GDAL), ejecutar los tests en Windows directamente con el intérprete Python de QGIS (`python3.exe`) desde una terminal Powershell estándar suele fallar arrojando un error:
`ImportError: DLL load failed while importing _gdal: No se encontró el proceso especificado.`

*   **Razón:** Para que los bindings de Python de GDAL puedan cargar sus DLLs de C++, requieren de variables de entorno del sistema que QGIS configura de manera interna al arrancar.
*   **Cómo proceder para testear:**
    *   **Método 1 (Consola OSGeo4W):** Ejecutar las pruebas desde la terminal **OSGeo4W Shell** provista por la instalación de QGIS. Esta consola configura automáticamente las variables de entorno (`PATH`, `GDAL_DATA`, `PROJ_LIB`) antes de invocar a `pytest`.
    *   **Método 2 (Scripts de entorno):** Ejecutar un script de inicialización por lotes (`.bat`) que configure los paths de QGIS antes de levantar `pytest`.

---

## 3. Reglas para Escribir Tests
*   **Aislamiento:** Los tests no deben interactuar con la interfaz gráfica (`PyQt5` o `QgsInterface`).
*   **Datos de prueba:** Utilizar los ficheros ráster y vectoriales pequeños provistos en la carpeta `Data/` del proyecto.
*   **Verificación no invasiva:** Asegurarse de que los tests limpien cualquier archivo temporal residual creado durante las pruebas.
