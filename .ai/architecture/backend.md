# Arquitectura del Backend Analítico (.ai/architecture/backend.md)

Este documento describe los principios de diseño y operación del motor científico del plugin DRT.

---

## 1. Desacoplamiento de QGIS
*   **Principio Fundamental:** El módulo `/analysis` debe permanecer **100% puro de Python**.
*   **Prohibición:** Está estrictamente prohibido importar `qgis.core` o `qgis.gui` en cualquiera de los archivos analíticos (` runner.py`, `compatibility.py`, `features.py`, `spatial.py`, `spectral.py`, `separability.py`, `indexes.py`).
*   **Manejo de Datos:** El intercambio de información entre la UI (QGIS) y el backend se realiza mediante rutas de archivos físicas (`raster_path`, `vector_path`) o estructuras tabulares genéricas (Pandas DataFrame, CSV).

---

## 2. Librerías Científicas Utilizadas
*   **GDAL (osgeo.gdal):** Lectura directa de bandas ráster y transformación de coordenadas de píxeles a mapa.
*   **GeoPandas:** Lectura, gestión de tablas y reproyección rápida del vector.
*   **Shapely:** Operaciones geométricas avanzadas (intersecciones, áreas, perímetros, centroides y point-in-polygon con `shapely.prepared.prep`).
*   **SciPy / NumPy:** Operaciones de álgebra lineal, distancias multivariadas (`cdist`), estadísticas básicas y ajuste de curvas empíricas (`curve_fit`).
*   **scikit-learn:** Algoritmos de Machine Learning (PCA, K-Means, siluetas, Davies-Bouldin, Mutual Information, t-SNE).
*   **scikit-image:** Extracción de texturas mediante matrices de co-ocurrencia de niveles de gris (GLCM).

---

## 3. Directrices de Programación del Backend
*   **Evitar I/O Redundante:** Utilizar operaciones vectorizadas en NumPy siempre que sea posible en lugar de loops iterativos pesados en Python.
*   **No Destructividad:** El backend no debe modificar los archivos vectoriales ni ráster originales en disco. Los resultados analíticos deben compilarse en estructuras de datos de Pandas (`pd.DataFrame`) y exportarse a HTML o ficheros CSV planos de salida.
*   **Seguridad de Matrices Singulares:** En cálculos como distancias de Mahalanobis, se debe aplicar regularización Ridge (`+ 1e-4 * np.eye(...)`) para evitar matrices singulares y errores de división por cero en proyecciones vectoriales.
