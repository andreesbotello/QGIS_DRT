# -*- coding: utf-8 -*-
"""
Módulo para el diagnóstico de compatibilidad espacial (CRS, extensión y resolución).
"""

import os
import numpy as np
import geopandas as gpd
from osgeo import gdal, osr
from shapely.geometry import box

class SpatialCompatibility:
    """Valida la consistencia espacial y de escala entre datos ráster y vectoriales."""

    def __init__(self, raster_path, vector_path):
        """Inicializa los datos espaciales a partir de las rutas de archivo.

        Args:
            raster_path (str): Ruta al archivo ráster (.tif).
            vector_path (str): Ruta al archivo vectorial (.shp).
        """
        self.raster_path = raster_path
        self.vector_path = vector_path
        self.raster_ds = None
        self.vector_gdf = None
        self._load_data()

    def _load_data(self):
        """Carga el ráster usando GDAL y el vector usando GeoPandas."""
        if not os.path.exists(self.raster_path):
            raise FileNotFoundError(f"Archivo ráster no encontrado: {self.raster_path}")
        if not os.path.exists(self.vector_path):
            raise FileNotFoundError(f"Archivo vectorial no encontrado: {self.vector_path}")

        # Cargar ráster con GDAL
        self.raster_ds = gdal.Open(self.raster_path)
        if not self.raster_ds:
            raise IOError(f"No se pudo abrir el archivo ráster: {self.raster_path}")

        # Cargar vector con GeoPandas
        self.vector_gdf = gpd.read_file(self.vector_path)
        if self.vector_gdf.empty:
            raise ValueError(f"El archivo vectorial cargado está vacío: {self.vector_path}")

    def check_crs(self):
        """Compara los CRS de ambas fuentes y reproyecta el vector si es necesario.

        Returns:
            dict: Estado detallado de la comparación de proyecciones.
        """
        raster_crs_wkt = self.raster_ds.GetProjection()
        vector_crs = self.vector_gdf.crs

        # Extraer códigos EPSG usando OSR
        srs = osr.SpatialReference(wkt=raster_crs_wkt)
        raster_epsg = srs.GetAttrValue("AUTHORITY", 1)

        vector_epsg = None
        if vector_crs:
            vector_epsg = str(vector_crs.to_epsg())

        match = False
        reprojected = False

        if raster_epsg and vector_epsg:
            match = (raster_epsg == vector_epsg)
        else:
            match = self.vector_gdf.crs.to_wkt().strip().lower() == raster_crs_wkt.strip().lower()

        if not match:
            # Proyectar el vector al CRS del ráster para asegurar compatibilidad geométrica
            target_crs = f"EPSG:{raster_epsg}" if raster_epsg else raster_crs_wkt
            try:
                self.vector_gdf = self.vector_gdf.to_crs(target_crs)
                reprojected = True
            except Exception as e:
                raise RuntimeError(f"Fallo al reproyectar la capa vectorial al CRS del ráster: {str(e)}")

        return {
            'match': match,
            'raster_crs': f"EPSG:{raster_epsg}" if raster_epsg else "WKT Personalizado",
            'vector_crs': f"EPSG:{vector_epsg}" if vector_epsg else "WKT Personalizado",
            'reprojected': reprojected
        }

    def get_extents(self):
        """Calcula el Bounding Box del ráster, vector e intersección común.

        Returns:
            dict: Extensiones espaciales y ratio de solapamiento.
        """
        # Extensión del ráster mediante la GeoTransformación de GDAL
        gt = self.raster_ds.GetGeoTransform()
        r_xmin = gt[0]
        r_ymax = gt[3]
        r_xmax = r_xmin + gt[1] * self.raster_ds.RasterXSize
        r_ymin = r_ymax + gt[5] * self.raster_ds.RasterYSize

        raster_ext = {'xmin': r_xmin, 'ymin': r_ymin, 'xmax': r_xmax, 'ymax': r_ymax}

        # Extensión del vector
        bounds = self.vector_gdf.total_bounds
        vector_ext = {'xmin': bounds[0], 'ymin': bounds[1], 'xmax': bounds[2], 'ymax': bounds[3]}

        # Intersección
        i_xmin = max(r_xmin, bounds[0])
        i_ymin = max(r_ymin, bounds[1])
        i_xmax = min(r_xmax, bounds[2])
        i_ymax = min(r_ymax, bounds[3])

        intersection_ext = None
        overlap_percentage = 0.0

        if i_xmin < i_xmax and i_ymin < i_ymax:
            intersection_ext = {'xmin': i_xmin, 'ymin': i_ymin, 'xmax': i_xmax, 'ymax': i_ymax}
            # Calcular el porcentaje de solapamiento sobre la extensión del vector
            vector_area = (bounds[2] - bounds[0]) * (bounds[3] - bounds[1])
            inter_area = (i_xmax - i_xmin) * (i_ymax - i_ymin)
            if vector_area > 0:
                overlap_percentage = min(100.0, (inter_area / vector_area) * 100.0)

        return {
            'raster_extent': raster_ext,
            'vector_extent': vector_ext,
            'intersection_extent': intersection_ext,
            'overlap_percentage': overlap_percentage
        }

    def calculate_coverage(self):
        """Calcula la cobertura efectiva del ráster sobre las geometrías del vector.

        Returns:
            dict: Número de polígonos que intersecan espacialmente y tasa de cobertura.
        """
        extents = self.get_extents()
        inter_ext = extents['intersection_extent']

        if not inter_ext:
            return {
                'total_polygons': len(self.vector_gdf),
                'polygons_inside': 0,
                'polygons_outside': len(self.vector_gdf),
                'coverage_ratio': 0.0
            }

        # Crear caja contenedora de ráster con Shapely
        gt = self.raster_ds.GetGeoTransform()
        r_xmin = gt[0]
        r_ymax = gt[3]
        r_xmax = r_xmin + gt[1] * self.raster_ds.RasterXSize
        r_ymin = r_ymax + gt[5] * self.raster_ds.RasterYSize
        raster_box = box(r_xmin, r_ymin, r_xmax, r_ymax)

        inside_count = 0
        outside_count = 0

        for geom in self.vector_gdf.geometry:
            if geom is None:
                outside_count += 1
                continue
            # Se considera cubierto si tiene alguna intersección física con el ráster
            if raster_box.intersects(geom):
                inside_count += 1
            else:
                outside_count += 1

        coverage_ratio = (inside_count / len(self.vector_gdf)) * 100.0

        return {
            'total_polygons': len(self.vector_gdf),
            'polygons_inside': inside_count,
            'polygons_outside': outside_count,
            'coverage_ratio': coverage_ratio
        }

    def calculate_observational_resolution(self):
        """Analiza la relación de escala (tamaño píxel vs área de polígonos).

        Returns:
            dict: Métricas y array de razones de escala.
        """
        gt = self.raster_ds.GetGeoTransform()
        pixel_area = abs(gt[1] * gt[5])

        # Áreas en unidades del CRS (generalmente metros cuadrados para UTM)
        poly_areas = self.vector_gdf.geometry.area.values
        poly_areas = poly_areas[poly_areas > 0]

        if len(poly_areas) == 0:
            return {}

        # Razón: Área del píxel / Área del polígono
        ratios = pixel_area / poly_areas

        return {
            'pixel_area_m2': float(pixel_area),
            'polygon_area_min': float(np.min(poly_areas)),
            'polygon_area_max': float(np.max(poly_areas)),
            'polygon_area_mean': float(np.mean(poly_areas)),
            'polygon_area_std': float(np.std(poly_areas)),
            'ratio_pixel_poly_mean': float(np.mean(ratios)),
            'ratio_pixel_poly_median': float(np.median(ratios)),
            'ratios': ratios.tolist()
        }
