# -*- coding: utf-8 -*-
"""
Inicializador del plugin Diagnóstico de Representación Territorial (DRT).
"""

def classFactory(iface):
    """Carga y retorna la clase principal del plugin.

    Args:
        iface (QgsInterface): Interfaz de usuario de QGIS.
    """
    from .plugin import DRTPlugin
    return DRTPlugin(iface)
