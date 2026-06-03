# -*- coding: utf-8 -*-
"""
Clase principal para la integración del plugin DRT con la interfaz de QGIS.
"""

import os
from qgis.PyQt.QtCore import QCoreApplication, Qt
from qgis.PyQt.QtWidgets import QAction
from qgis.PyQt.QtGui import QIcon

class DRTPlugin:
    """Controlador del ciclo de vida del plugin en QGIS."""

    def __init__(self, iface):
        """Inicializa el plugin guardando la interfaz de QGIS.

        Args:
            iface (QgsInterface): Interfaz de usuario de QGIS.
        """
        self.iface = iface
        self.dock_widget = None
        self.action = None
        self.plugin_dir = os.path.dirname(__file__)

    def initGui(self):
        """Inicializa la interfaz gráfica, agregando menús y botones."""
        # Se define la acción de ejecución del plugin con su icono
        icon_path = os.path.join(self.plugin_dir, 'icono.png')
        icon = QIcon(icon_path)
        self.action = QAction(
            icon,
            "Diagnóstico de Representación Territorial (DRT)",
            self.iface.mainWindow()
        )
        self.action.triggered.connect(self.run)

        # Agregar al menú de Plugins y a la barra de herramientas
        self.iface.addPluginToMenu("&DRT", self.action)
        self.iface.addToolBarIcon(self.action)

    def unload(self):
        """Descarga el plugin removiendo sus menús e interfaces."""
        if self.action:
            self.iface.removePluginMenu("&DRT", self.action)
            self.iface.removeToolBarIcon(self.action)
        if self.dock_widget:
            self.iface.removeDockWidget(self.dock_widget)

    def run(self):
        """Ejecuta e inicializa el panel de control del plugin."""
        from .ui.main_dockwidget import DRTDockWidget
        
        if self.dock_widget is None:
            self.dock_widget = DRTDockWidget(self.iface)

        # Añade el panel al área lateral derecha de QGIS
        self.iface.addDockWidget(Qt.RightDockWidgetArea, self.dock_widget)
        self.dock_widget.show()
