# -*- coding: utf-8 -*-
"""
Servicio centralizado de gestión e instalación de dependencias de Python para el plugin DRT.
"""

import sys
import os
import subprocess
import importlib
import site

class DependencyManager:
    """Administra la validación e instalación de librerías científicas externas en QGIS."""

    # Diccionario de dependencias requeridas
    # Llave: Nombre del módulo a importar
    # Valor: Nombre del paquete en PyPI
    REQUIRED_LIBRARIES = {
        "numpy": "numpy",
        "pandas": "pandas",
        "geopandas": "geopandas",
        "shapely": "shapely",
        "scipy": "scipy",
        "sklearn": "scikit-learn",
        "skimage": "scikit-image",
        "plotly": "plotly",
        "jinja2": "jinja2"
    }

    @classmethod
    def check_missing_dependencies(cls):
        """Identifica cuáles dependencias requeridas no están instaladas en el entorno.

        Returns:
            list: Lista de tuplas (modulo, paquete_pypi) de las librerías faltantes.
        """
        # Asegurarse de que el directorio site-packages del usuario esté en sys.path
        cls.ensure_user_site_packages()

        missing = []
        for module_name, pypi_name in cls.REQUIRED_LIBRARIES.items():
            try:
                importlib.import_module(module_name)
            except ImportError:
                missing.append((module_name, pypi_name))
        return missing

    @classmethod
    def ensure_user_site_packages(cls):
        """Agrega programáticamente la ruta site-packages del usuario al sys.path."""
        try:
            user_site = site.getusersitepackages()
            if user_site and os.path.exists(user_site) and user_site not in sys.path:
                sys.path.append(user_site)
        except Exception:
            pass

    @classmethod
    def get_python_executable(cls):
        """Obtiene la ruta absoluta del intérprete de Python de QGIS.

        Returns:
            str: Ruta al ejecutable de Python.
        """
        python_exe = sys.executable
        
        # En Windows/OSGeo4W, sys.executable suele ser qgis-bin.exe,
        # por lo que debemos ubicar python3.exe en el mismo directorio o en sys.exec_prefix
        if os.name == 'nt':
            bin_dir = os.path.dirname(python_exe)
            potential_py = os.path.join(bin_dir, "python3.exe")
            if os.path.exists(potential_py):
                return potential_py
            
            potential_py = os.path.join(bin_dir, "python.exe")
            if os.path.exists(potential_py):
                return potential_py

            # Alternativa usando sys.exec_prefix
            potential_py = os.path.join(sys.exec_prefix, "python.exe")
            if os.path.exists(potential_py):
                return potential_py
                
        return python_exe

    @classmethod
    def install_packages_subprocess(cls, packages, stdout_callback=None, stderr_callback=None):
        """Instala los paquetes especificados ejecutando pip en un subproceso de forma asíncrona.

        Args:
            packages (list): Lista de nombres de paquetes PyPI a instalar.
            stdout_callback (function): Callback para redirigir stdout.
            stderr_callback (function): Callback para redirigir stderr.

        Returns:
            tuple: (bool éxito, str logs_completos)
        """
        python_exe = cls.get_python_executable()
        cmd = [python_exe, "-m", "pip", "install", "--user"] + packages

        # Opciones de inicio para evitar levantar una consola CMD en Windows
        startupinfo = None
        if os.name == 'nt':
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = 0  # SW_HIDE

        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                universal_newlines=True,
                bufsize=1
            )

            # Leer la salida en tiempo real
            full_log = []
            while True:
                output = process.stdout.readline()
                if output == '' and process.poll() is not None:
                    break
                if output:
                    clean_line = output.strip()
                    full_log.append(clean_line)
                    if stdout_callback:
                        stdout_callback(clean_line)

            # Capturar posibles errores del stderr
            stderr_output = process.stderr.read()
            if stderr_output:
                full_log.append(stderr_output)
                if stderr_callback:
                    stderr_callback(stderr_output)

            rc = process.poll()
            success = (rc == 0)

            # Asegurar que se recargue la ruta site-packages en sys.path al finalizar la instalación
            cls.ensure_user_site_packages()

            return success, "\n".join(full_log)

        except Exception as e:
            error_msg = f"Excepción durante la instalación: {str(e)}"
            if stderr_callback:
                stderr_callback(error_msg)
            return False, error_msg
