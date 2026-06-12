# -*- coding: utf-8 -*-
"""
Controlador del diálogo de progreso de instalación de dependencias de Python para el plugin DRT.
"""

import os
from qgis.PyQt import uic
from qgis.PyQt.QtCore import Qt, QThread, pyqtSignal
from qgis.PyQt.QtWidgets import QDialog, QMessageBox

# Carga dinámica del archivo .ui compilado en tiempo de ejecución
UI_FILE = os.path.join(os.path.dirname(__file__), 'dependency_dialog.ui')
FORM_CLASS, BASE_CLASS = uic.loadUiType(UI_FILE)

class InstallationWorker(QThread):
    """Hilo de trabajo secundario para ejecutar pip install sin bloquear la UI principal de QGIS."""
    sig_stdout = pyqtSignal(str)
    sig_stderr = pyqtSignal(str)
    sig_finished = pyqtSignal(bool, str)

    def __init__(self, packages):
        """Inicializa el hilo con la lista de paquetes a instalar.

        Args:
            packages (list): Nombres de los paquetes en PyPI.
        """
        super(InstallationWorker, self).__init__()
        self.packages = packages

    def run(self):
        """Ejecuta el proceso de instalación."""
        from ..core.dependency_manager import DependencyManager
        success, log = DependencyManager.install_packages_subprocess(
            self.packages,
            stdout_callback=self.sig_stdout.emit,
            stderr_callback=self.sig_stderr.emit
        )
        self.sig_finished.emit(success, log)

class DependencyDialog(BASE_CLASS, FORM_CLASS):
    """Diálogo interactivo para mostrar el progreso de preparación de dependencias de Python."""

    def __init__(self, missing_packages, parent=None):
        """Inicializa los componentes de la interfaz.

        Args:
            missing_packages (list): Lista de tuplas (modulo, paquete_pypi) de las librerías faltantes.
            parent: Widget contenedor padre.
        """
        super(DependencyDialog, self).__init__(parent)
        self.setupUi(self)
        self.missing_packages = missing_packages
        self.worker = None

        # Configurar comportamiento de botones
        self.btnDetails.clicked.connect(self._toggle_details)
        self.btnCancel.clicked.connect(self.reject)

        # Configurar la barra de progreso como indeterminada (marquesina) al inicio
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(0)

        # Iniciar instalación al mostrarse el diálogo
        self.finished.connect(self._on_finished_event)

    def showEvent(self, event):
        """Sobrescribe el evento de visualización para arrancar la descarga."""
        super(DependencyDialog, self).showEvent(event)
        self.start_installation()

    def start_installation(self):
        """Crea el hilo de trabajo y lanza el comando pip."""
        pypi_names = [pkg[1] for pkg in self.missing_packages]
        
        self.txtDetails.append(f"Iniciando instalación de componentes: {', '.join(pypi_names)}\n")
        self.lblStatus.setText("Preparando instalación...")
        
        # Deshabilitar cierre hasta finalizar
        self.setWindowFlags(self.windowFlags() | Qt.CustomizeWindowHint)
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowCloseButtonHint)
        self.show()

        self.worker = InstallationWorker(pypi_names)
        self.worker.sig_stdout.connect(self._on_stdout)
        self.worker.sig_stderr.connect(self._on_stderr)
        self.worker.sig_finished.connect(self._on_worker_finished)
        self.worker.start()

    def _on_stdout(self, text):
        """Maneja la salida estándar de pip y actualiza las etiquetas."""
        self.txtDetails.append(text)
        self.txtDetails.ensureCursorVisible()

        # Extraer nombres amigables de descarga para el usuario
        if "Downloading" in text:
            parts = text.split(" ")
            if len(parts) > 1:
                pkg_name = parts[1].split("-")[0]
                self.lblStatus.setText(f"Descargando {pkg_name}...")
        elif "Installing collected packages" in text:
            self.lblStatus.setText("Instalando componentes en el perfil de usuario...")
        elif "Successfully installed" in text:
            self.lblStatus.setText("Componentes instalados con éxito.")

    def _on_stderr(self, text):
        """Maneja los errores reportados por pip."""
        self.txtDetails.append(f"[Error] {text}")
        self.txtDetails.ensureCursorVisible()

    def _on_worker_finished(self, success, log):
        """Finaliza el diálogo al completarse la instalación."""
        self.progressBar.setMinimum(0)
        self.progressBar.setMaximum(100)
        self.progressBar.setValue(100 if success else 0)

        # Rehabilitar botón de cerrar ventana
        self.setWindowFlags(self.windowFlags() | Qt.WindowCloseButtonHint)
        self.show()

        if success:
            self.lblStatus.setText("¡Todo listo! Entorno configurado correctamente.")
            self.lblMessage.setText("¡Preparación completa!")
            QMessageBox.information(
                self,
                "Instalación Exitosa",
                "Las librerías científicas se han instalado correctamente en su entorno de usuario.\n"
                "El plugin ahora está listo para ser utilizado."
            )
            self.accept()
        else:
            self.lblStatus.setText("Ocurrió un error al preparar el entorno.")
            self.lblMessage.setText("Error en la configuración")
            
            # Forzar la visualización de los detalles del log de errores
            self.btnDetails.setChecked(True)
            self._toggle_details(True)
            
            QMessageBox.critical(
                self,
                "Error en Preparación",
                "Hubo un inconveniente en la descarga de componentes.\n"
                "Revise la bitácora de detalles para mayor información."
            )
            self.reject()

    def _toggle_details(self, checked):
        """Alterna el tamaño de la ventana y visualización de la terminal."""
        self.txtDetails.setVisible(checked)
        if checked:
            self.btnDetails.setText("Ocultar detalles")
            self.resize(self.width(), 380)
        else:
            self.btnDetails.setText("Mostrar detalles")
            self.resize(self.width(), 180)

    def _on_finished_event(self, result):
        """Asegura la terminación segura del hilo de instalación."""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            self.worker.wait()
