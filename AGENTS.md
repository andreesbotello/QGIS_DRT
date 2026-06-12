# Directrices de Desarrollo para Agentes de Inteligencia Artificial (AGENTS.md)

Este archivo centraliza las reglas, metodologías y principios que cualquier agente de inteligencia artificial debe seguir al interactuar con el código, la documentación o los desarrolladores de este repositorio.

---

## 1. Tono y Estilo de Comunicación
*   **Lenguaje Técnico y Pragmático:** Toda la documentación, comentarios en el código, mensajes de confirmación de git y respuestas del agente deben redactarse en un tono estrictamente profesional, objetivo y libre de valoraciones subjetivas o lenguaje coloquial.
*   **Prohibición de Emojis y Decoraciones:** Está estrictamente prohibida la incorporación de emojis, signos de exclamación redundantes o decoraciones estilísticas informales en cualquier interacción o archivo del repositorio.

---

## 2. Reglas de Operación y Desarrollo
*   **Uso del Terminal:** Se debe limitar el uso de comandos de consola a lo estrictamente necesario (ej. ejecución de tests, compilación). Nunca se deben proponer o ejecutar comandos innecesarios o redundantes.
*   **Creación de Archivos Temporales:** Queda estrictamente prohibida la creación de scripts de prueba, archivos temporales o código suelto fuera del entorno del proyecto. En caso de ser necesarios para análisis rápidos, deben colocarse exclusivamente dentro de la carpeta `temp/` en la raíz del proyecto, la cual se encuentra convenientemente excluida del control de versiones mediante `.gitignore`.
*   **Integridad de Documentación:** Mantener y respetar los comentarios y docstrings del código preexistente a menos que su edición sea explícitamente solicitada por el usuario.
*   **Prohibición de Rutas Absolutas:** Queda estrictamente prohibido el uso de rutas absolutas en el código fuente, scripts o cualquier archivo de documentación del repositorio. Toda referencia a rutas debe expresarse de manera relativa a la raíz del proyecto para salvaguardar la confidencialidad, portabilidad del código y seguridad del entorno del desarrollador.

---

## 3. Estructura de Contexto y Gestión del Proyecto (.ai/)
Para facilitar la asimilación del proyecto y mantener un contexto óptimo para la IA, se ha estructurado una carpeta de metadatos en la raíz llamada `.ai/` con la siguiente estructura:

*   **`.ai/skills/`**: Carpeta destinada a albergar archivos con mejores prácticas de codificación (ej. buenas prácticas en Python, QGIS, optimizaciones numéricas).
*   **`.ai/architecture/`**: Carpeta destinada a albergar guías de arquitectura cortas y modulares bajo demanda:
    *   [interface.md](.ai/architecture/interface.md): Lineamientos para el desarrollo de la interfaz de usuario con PyQt5/QtDesigner en QGIS.
    *   [backend.md](.ai/architecture/backend.md): Lineamientos de operación del motor analítico desacoplado (GeoPandas, SciPy, NumPy).
    *   [testing.md](.ai/architecture/testing.md): Reglas de testeo con pytest y consideraciones sobre el cargador de DLLs de GDAL.
