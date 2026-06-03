# -*- coding: utf-8 -*-
"""
Controlador para el panel de usuario DockWidget del plugin DRT.
"""

import os
from qgis.PyQt import uic
from qgis.PyQt.QtWidgets import QMessageBox, QFileDialog
from qgis.core import QgsProject, QgsMapLayerType, QgsRasterLayer, QgsVectorLayer

# Carga dinámica del archivo .ui compilado en tiempo de ejecución
UI_FILE = os.path.join(os.path.dirname(__file__), 'main_dockwidget.ui')
FORM_CLASS, BASE_CLASS = uic.loadUiType(UI_FILE)

class DRTDockWidget(BASE_CLASS, FORM_CLASS):
    """Panel lateral de control para configurar y ejecutar los diagnósticos DRT."""

    def __init__(self, iface, parent=None):
        """Inicializa los componentes de la interfaz y configura los eventos de enlace.

        Args:
            iface (QgsInterface): Interfaz de usuario de QGIS.
            parent: Widget contenedor padre.
        """
        super(DRTDockWidget, self).__init__(parent)
        self.iface = iface
        self.setupUi(self)

        # Enlace de eventos de control
        self.vectorComboBox.currentIndexChanged.connect(self._on_vector_changed)
        self.btnExecuteM1.clicked.connect(self._on_execute_m1)
        self.btnExecuteM2.clicked.connect(self._on_execute_m2)
        self.btnBrowseRaster.clicked.connect(self._on_browse_raster)
        self.btnBrowseVector.clicked.connect(self._on_browse_vector)
        self.btnBrowseOutputDir.clicked.connect(self._on_browse_output_dir)
        self.btnClearLog.clicked.connect(self._on_clear_log)

        # Enlace de actualización de capas al modificar el proyecto
        QgsProject.instance().layersAdded.connect(self.populate_layers)
        QgsProject.instance().layersRemoved.connect(self.populate_layers)

        self.populate_layers()

    def populate_layers(self, *args, **kwargs):
        """Carga y filtra las capas del proyecto activo en sus comboboxes respectivos."""
        prev_raster = self.rasterComboBox.currentText()
        prev_vector = self.vectorComboBox.currentText()

        self.rasterComboBox.clear()
        self.vectorComboBox.clear()

        # Obtener todas las capas del proyecto
        layers = QgsProject.instance().mapLayers().values()

        for layer in layers:
            if layer.type() == QgsMapLayerType.RasterLayer:
                self.rasterComboBox.addItem(layer.name(), layer.id())
            elif layer.type() == QgsMapLayerType.VectorLayer:
                self.vectorComboBox.addItem(layer.name(), layer.id())

        # Restaurar la selección anterior si aún existe
        idx_raster = self.rasterComboBox.findText(prev_raster)
        if idx_raster != -1:
            self.rasterComboBox.setCurrentIndex(idx_raster)

        idx_vector = self.vectorComboBox.findText(prev_vector)
        if idx_vector != -1:
            self.vectorComboBox.setCurrentIndex(idx_vector)

    def _on_vector_changed(self):
        """Actualiza el combobox de campos y el nombre base según la capa vectorial seleccionada."""
        self.classFieldComboBox.clear()

        layer_id = self.vectorComboBox.currentData()
        if not layer_id:
            return

        layer = QgsProject.instance().mapLayer(layer_id)
        if not layer or not layer.isValid():
            return

        # Establecer por defecto el nombre de la capa vectorial como nombre base
        self.txtBaseName.setText(layer.name())

        # Cargar los nombres de los atributos
        fields = layer.fields()
        for field in fields:
            self.classFieldComboBox.addItem(field.name())

    def _on_execute_m1(self):
        """Gestiona el evento de ejecución para el módulo Memoria 1."""
        raster_id = self.rasterComboBox.currentData()
        vector_id = self.vectorComboBox.currentData()
        class_field = self.classFieldComboBox.currentText()
        output_dir = self.txtOutputDir.text()
        base_name = self.txtBaseName.text().strip()

        if not raster_id or not vector_id or not class_field:
            QMessageBox.warning(
                self,
                "Error de Parámetros",
                "Debe seleccionar una capa ráster, una capa vectorial y el campo de clase correspondiente."
            )
            return

        if not output_dir:
            QMessageBox.warning(
                self,
                "Error de Parámetros",
                "Debe seleccionar una carpeta de salida para los resultados."
            )
            return

        if not base_name:
            QMessageBox.warning(
                self,
                "Error de Parámetros",
                "Debe especificar un nombre base para los archivos de salida."
            )
            return

        raster_layer = QgsProject.instance().mapLayer(raster_id)
        vector_layer = QgsProject.instance().mapLayer(vector_id)

        if not raster_layer or not vector_layer:
            QMessageBox.warning(
                self,
                "Error de Capas",
                "Las capas seleccionadas no son válidas o han sido removidas del proyecto."
            )
            return

        raster_path = raster_layer.source()
        vector_path = vector_layer.source()

        # Validaciones preliminares de consistencia espacial
        try:
            from ..analysis.compatibility import SpatialCompatibility
            compat = SpatialCompatibility(raster_path, vector_path)
            
            # 1. Comprobar CRS
            compat.check_crs()
            
            # 2. Comprobar solapamiento físico
            extents = compat.get_extents()
            if extents['intersection_extent'] is None:
                QMessageBox.critical(
                    self,
                    "Error de Solapamiento Espacial",
                    "No existe coincidencia física entre el ráster y el vector.\n"
                    "Sus extensiones geográficas son completamente disjuntas."
                )
                return
                
            # 3. Comprobar si el campo de clase existe
            if class_field not in compat.vector_gdf.columns:
                QMessageBox.critical(
                    self,
                    "Error de Atributo",
                    f"El campo de clase '{class_field}' no existe en la tabla de atributos del vector."
                )
                return

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error de Inicialización",
                f"Ocurrió un error al validar los datos espaciales:\n{str(e)}"
            )
            return

        # Ejecución del análisis y exportación de archivos
        try:
            # Limpiar consola de registro y cambiar a la pestaña de consola
            self.txtLog.clear()
            self.tabWidget.setCurrentIndex(1)

            from qgis.PyQt.QtCore import Qt, QCoreApplication
            from qgis.PyQt.QtGui import QCursor
            self.setCursor(QCursor(Qt.WaitCursor))

            from ..analysis.runner import run_memoria1_diagnostics
            from ..reports.generator import ReportGenerator

            # Ejecutar cálculos registrando eventos en la consola
            results, export_df = run_memoria1_diagnostics(raster_path, vector_path, class_field, log_callback=self.log)

            # Rutas de salida físicas
            html_path = os.path.join(output_dir, f"{base_name}.html")
            csv_path = os.path.join(output_dir, f"{base_name}.csv")

            self.log("Guardando archivos de salida...")
            # Guardar reporte HTML y tabla CSV
            ReportGenerator.generate_m1_report(results, html_path)
            export_df.to_csv(csv_path, index=False, encoding='utf-8')
            self.log(f"  Reporte HTML guardado en: {html_path}")
            self.log(f"  Fichero CSV guardado en: {csv_path}")

            self.setCursor(QCursor(Qt.ArrowCursor))

            self.log("\nProceso finalizado correctamente.")
            QMessageBox.information(
                self,
                "Diagnóstico Completado",
                f"El análisis de la Memoria 1 ha finalizado correctamente.\n\n"
                f"Archivos generados en:\n"
                f"- Reporte HTML: {html_path}\n"
                f"- Datos CSV: {csv_path}\n\n"
                f"Puntaje TOI: {results['toi']['toi']:.2f} ({results['toi']['clasificacion']})\n\n"
                f"Nota: Puede abrir el reporte HTML en su navegador e imprimirlo como PDF."
            )

        except Exception as e:
            self.setCursor(QCursor(Qt.ArrowCursor))
            import traceback
            error_tb = traceback.format_exc()
            self.log("\n[ERROR CRÍTICO DETECTADO]")
            self.log(error_tb)
            QMessageBox.critical(
                self,
                "Error de Procesamiento",
                f"Fallo durante la ejecución. Revise el registro en la pestaña 'Consola' para más detalles:\n{str(e)}"
            )
            return

    def _on_execute_m2(self):
        """Gestiona el evento de ejecución para el módulo Memoria 2 (Separabilidad)."""
        raster_id = self.rasterComboBox.currentData()
        vector_id = self.vectorComboBox.currentData()
        class_field = self.classFieldComboBox.currentText()
        output_dir = self.txtOutputDir.text()
        base_name = self.txtBaseName.text().strip()

        if not raster_id or not vector_id or not class_field:
            QMessageBox.warning(
                self,
                "Error de Parámetros",
                "Debe seleccionar una capa ráster, una capa vectorial y el campo de clase correspondiente."
            )
            return

        if not output_dir:
            QMessageBox.warning(
                self,
                "Error de Parámetros",
                "Debe seleccionar una carpeta de salida para los resultados."
            )
            return

        if not base_name:
            QMessageBox.warning(
                self,
                "Error de Parámetros",
                "Debe especificar un nombre base para los archivos de salida."
            )
            return

        raster_layer = QgsProject.instance().mapLayer(raster_id)
        vector_layer = QgsProject.instance().mapLayer(vector_id)

        if not raster_layer or not vector_layer:
            QMessageBox.warning(
                self,
                "Error de Capas",
                "Las capas seleccionadas no son válidas o han sido removidas del proyecto."
            )
            return

        raster_path = raster_layer.source()
        vector_path = vector_layer.source()

        # Validaciones preliminares de consistencia espacial
        try:
            from ..analysis.compatibility import SpatialCompatibility
            compat = SpatialCompatibility(raster_path, vector_path)
            
            # 1. Comprobar CRS
            compat.check_crs()
            
            # 2. Comprobar solapamiento físico
            extents = compat.get_extents()
            if extents['intersection_extent'] is None:
                QMessageBox.critical(
                    self,
                    "Error de Solapamiento Espacial",
                    "No existe coincidencia física entre el ráster y el vector.\n"
                    "Sus extensiones geográficas son completamente disjuntas."
                )
                return
                
            # 3. Comprobar si el campo de clase existe
            if class_field not in compat.vector_gdf.columns:
                QMessageBox.critical(
                    self,
                    "Error de Atributo",
                    f"El campo de clase '{class_field}' no existe en la tabla de atributos del vector."
                )
                return

        except Exception as e:
            QMessageBox.critical(
                self,
                "Error de Inicialización",
                f"Ocurrió un error al validar los datos espaciales:\n{str(e)}"
            )
            return

        # Ejecución del análisis y exportación de archivos
        try:
            # Limpiar consola de registro y cambiar a la pestaña de consola
            self.txtLog.clear()
            self.tabWidget.setCurrentIndex(1)

            from qgis.PyQt.QtCore import Qt
            from qgis.PyQt.QtGui import QCursor
            self.setCursor(QCursor(Qt.WaitCursor))

            from ..analysis.runner import run_memoria2_diagnostics
            from ..reports.generator import ReportGenerator

            # Ejecutar cálculos registrando eventos en la consola
            results, export_df = run_memoria2_diagnostics(raster_path, vector_path, class_field, log_callback=self.log)

            # Rutas de salida físicas
            html_path = os.path.join(output_dir, f"{base_name}_m2.html")
            csv_path = os.path.join(output_dir, f"{base_name}_m2.csv")

            self.log("Guardando archivos de salida...")
            # Guardar reporte HTML y tabla CSV
            ReportGenerator.generate_m2_report(results, html_path)
            export_df.to_csv(csv_path, index=False, encoding='utf-8')
            self.log(f"  Reporte HTML guardado en: {html_path}")
            self.log(f"  Fichero CSV guardado en: {csv_path}")

            self.setCursor(QCursor(Qt.ArrowCursor))

            self.log("\nProceso finalizado correctamente.")
            QMessageBox.information(
                self,
                "Diagnóstico Completado",
                f"El análisis de la Memoria 2 ha finalizado correctamente.\n\n"
                f"Archivos generados en:\n"
                f"- Reporte HTML: {html_path}\n"
                f"- Datos CSV: {csv_path}\n\n"
                f"Puntaje TLI: {results['tli']['tli']:.2f} ({results['tli']['clasificacion']})\n\n"
                f"Nota: Puede abrir el reporte HTML en su navegador e imprimirlo como PDF."
            )

        except Exception as e:
            self.setCursor(QCursor(Qt.ArrowCursor))
            import traceback
            error_tb = traceback.format_exc()
            self.log("\n[ERROR CRÍTICO DETECTADO]")
            self.log(error_tb)
            QMessageBox.critical(
                self,
                "Error de Procesamiento",
                f"Fallo durante la ejecución. Revise el registro en la pestaña 'Consola' para más detalles:\n{str(e)}"
            )
            return

    def _on_browse_raster(self):
        """Abre un diálogo de búsqueda de archivos para cargar un ráster externo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo ráster",
            "",
            "Ráster (*.tif *.tiff *.img *.asc);;Todos los archivos (*.*)"
        )
        if not file_path:
            return

        # Crear y registrar la capa ráster en QGIS
        name = os.path.splitext(os.path.basename(file_path))[0]
        layer = QgsRasterLayer(file_path, name)
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            # Seleccionar la nueva capa en el combobox
            idx = self.rasterComboBox.findText(layer.name())
            if idx != -1:
                self.rasterComboBox.setCurrentIndex(idx)
        else:
            QMessageBox.critical(
                self,
                "Error de Carga",
                f"El archivo ráster seleccionado no es válido:\n{file_path}"
            )

    def _on_browse_vector(self):
        """Abre un diálogo de búsqueda de archivos para cargar un vector externo."""
        file_path, _ = QFileDialog.getOpenFileName(
            self,
            "Seleccionar archivo vectorial",
            "",
            "Vectorial (*.shp *.gpkg *.geojson);;Todos los archivos (*.*)"
        )
        if not file_path:
            return

        # Crear y registrar la capa vectorial en QGIS
        name = os.path.splitext(os.path.basename(file_path))[0]
        layer = QgsVectorLayer(file_path, name, "ogr")
        if layer.isValid():
            QgsProject.instance().addMapLayer(layer)
            # Seleccionar la nueva capa en el combobox
            idx = self.vectorComboBox.findText(layer.name())
            if idx != -1:
                self.vectorComboBox.setCurrentIndex(idx)
        else:
            QMessageBox.critical(
                self,
                "Error de Carga",
                f"El archivo vectorial seleccionado no es válido o está corrupto:\n{file_path}"
            )

    def _on_browse_output_dir(self):
        """Abre un diálogo de selección de directorio para definir la ruta de salida."""
        dir_path = QFileDialog.getExistingDirectory(
            self,
            "Seleccionar carpeta de salida",
            ""
        )
        if dir_path:
            self.txtOutputDir.setText(dir_path)

    def log(self, message):
        """Agrega un mensaje a la consola de registro en tiempo real.

        Args:
            message (str): Texto a escribir.
        """
        self.txtLog.append(message)
        from qgis.PyQt.QtCore import QCoreApplication
        QCoreApplication.processEvents()

    def _on_clear_log(self):
        """Limpia el contenido del panel de la consola de registro."""
        self.txtLog.clear()
        self.txtLog.append("Esperando inicio del proceso de diagnóstico...")
