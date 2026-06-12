# -*- coding: utf-8 -*-
"""
Módulo para el diagnóstico de estructura espacial (Zonal Stats, Moran's I y Variografía).
"""

import numpy as np
import geopandas as gpd
from osgeo import gdal
from scipy.spatial.distance import cdist
from scipy.optimize import curve_fit
from shapely.prepared import prep
from shapely.geometry import Point

class SpatialDiagnostics:
    """Calcula la autocorrelación espacial global (Moran's I) y variografía de objetos territoriales."""

    def __init__(self, raster_path, vector_path):
        """Inicializa el diagnóstico espacial.

        Args:
            raster_path (str): Ruta al archivo ráster (.tif).
            vector_path (str): Ruta al archivo vectorial (.shp).
        """
        self.raster_path = raster_path
        self.vector_path = vector_path
        self.raster_ds = gdal.Open(self.raster_path)
        if not self.raster_ds:
            raise IOError(f"No se pudo abrir el archivo ráster: {self.raster_path}")

        # Analizar ruta del vector por si incluye modificadores de proveedor de QGIS (ej. GPKG)
        clean_vector_path = vector_path
        vector_layer_name = None
        if vector_path and "|" in vector_path:
            parts = vector_path.split("|")
            clean_vector_path = parts[0]
            for part in parts[1:]:
                if part.startswith("layername="):
                    vector_layer_name = part.split("=", 1)[1]

        # Cargar vector con GeoPandas (especificando la capa si es un GPKG u otro formato multi-capa)
        if vector_layer_name:
            self.vector_gdf = gpd.read_file(clean_vector_path, layer=vector_layer_name)
        else:
            self.vector_gdf = gpd.read_file(clean_vector_path)

    def calculate_zonal_means(self, band_idx=1):
        """Calcula el valor medio de píxeles del ráster para cada polígono del vector (Zonal Stats).

        Args:
            band_idx (int): Banda del ráster de la cual se extraen los valores (1-indexed).

        Returns:
            np.ndarray: Array con el valor medio espectral de cada polígono.
        """
        gt = self.raster_ds.GetGeoTransform()
        inv_gt = gdal.InvGeoTransform(gt)
        band = self.raster_ds.GetRasterBand(band_idx)
        nodata = band.GetNoDataValue()

        means = []

        for geom in self.vector_gdf.geometry:
            if geom is None or geom.is_empty:
                means.append(0.0)
                continue

            # Obtener el Bounding Box de la geometría
            xmin, ymin, xmax, ymax = geom.bounds

            # Transformar coordenadas espaciales a índices de píxel
            col1, row1 = gdal.ApplyGeoTransform(inv_gt, xmin, ymax)
            col2, row2 = gdal.ApplyGeoTransform(inv_gt, xmax, ymin)

            col_min = max(0, int(np.floor(col1)))
            row_min = max(0, int(np.floor(row1)))
            col_max = min(self.raster_ds.RasterXSize - 1, int(np.ceil(col2)))
            row_max = min(self.raster_ds.RasterYSize - 1, int(np.ceil(row2)))

            cols = col_max - col_min + 1
            rows = row_max - row_min + 1

            if cols <= 0 or rows <= 0:
                means.append(0.0)
                continue

            # Leer sub-array de la banda correspondiente
            arr = band.ReadAsArray(col_min, row_min, cols, rows)
            if arr is None:
                means.append(0.0)
                continue

            arr = arr.astype(np.float64)

            # Generar grilla de centros de píxeles en coordenadas del mapa
            cols_arr = np.arange(col_min, col_max + 1) + 0.5
            rows_arr = np.arange(row_min, row_max + 1) + 0.5
            px_x, px_y = np.meshgrid(cols_arr, rows_arr)

            xs = gt[0] + px_x * gt[1]
            ys = gt[3] + px_y * gt[5]

            # Crear puntos Shapely para verificar intersección geométrica
            points_flat = [Point(x, y) for x, y in zip(xs.ravel(), ys.ravel())]

            # Optimizar consultas espaciales usando Prepared Geometries
            prepared_geom = prep(geom)
            inside_mask = np.array([prepared_geom.contains(p) for p in points_flat])

            # Extraer valores y filtrar NoData
            vals = arr.ravel()[inside_mask]
            if nodata is not None:
                vals = vals[vals != nodata]
            vals = vals[np.isfinite(vals)]

            # Guardar el promedio o fallback al centroide si el polígono es más pequeño que un píxel
            if len(vals) == 0:
                cx, cy = geom.centroid.x, geom.centroid.y
                c_col, c_row = gdal.ApplyGeoTransform(inv_gt, cx, cy)
                c_col = max(0, min(self.raster_ds.RasterXSize - 1, int(c_col)))
                c_row = max(0, min(self.raster_ds.RasterYSize - 1, int(c_row)))
                val = band.ReadAsArray(c_col, c_row, 1, 1)[0, 0]
                if nodata is not None and val == nodata:
                    means.append(0.0)
                else:
                    means.append(float(val) if np.isfinite(val) else 0.0)
            else:
                means.append(float(np.mean(vals)))

        return np.array(means)

    def calculate_moran(self, values):
        """Calcula el Índice de Moran Global para autocorrelación espacial.

        Args:
            values (np.ndarray): Valores de atributo por polígono.

        Returns:
            dict: Índice de Moran e información estadística básica.
        """
        # Extraer centroides del GeoDataFrame
        centroids = self.vector_gdf.geometry.centroid
        coords = np.column_stack((centroids.x, centroids.y))
        n = len(coords)

        if n < 2:
            return {'moran_i': 0.0, 'z_score': 0.0}

        # Calcular distancias euclidianas entre todos los pares de polígonos
        dists = cdist(coords, coords, metric='euclidean')

        # Inversa de la distancia como peso espacial
        with np.errstate(divide='ignore'):
            W = 1.0 / dists
        np.fill_diagonal(W, 0.0)

        # Normalización por filas de la matriz de pesos
        row_sums = W.sum(axis=1)
        row_sums[row_sums == 0] = 1.0
        W = W / row_sums[:, np.newaxis]

        # Calcular desvíos con respecto a la media
        z_mean = np.mean(values)
        z_diff = values - z_mean

        denominator = np.sum(z_diff ** 2)
        if denominator == 0:
            return {'moran_i': 0.0, 'z_score': 0.0}

        # Fórmula de Moran's I (al estar normalizada por filas, W_sum = n)
        numerator = np.sum(W * np.outer(z_diff, z_diff))
        moran_i = numerator / denominator

        # Calcular la esperanza matemática E(I) = -1 / (n - 1)
        expected_moran = -1.0 / (n - 1)

        return {
            'moran_i': float(moran_i),
            'esperanza': float(expected_moran)
        }

    def calculate_semivariogram(self, values, num_lags=15):
        """Calcula el semivariograma empírico y estima los parámetros (sill, nugget y range).

        Args:
            values (np.ndarray): Valores de atributo por polígono.
            num_lags (int): Número de intervalos de distancia (bins).

        Returns:
            dict: Parámetros del variograma y datos empíricos para visualización.
        """
        centroids = self.vector_gdf.geometry.centroid
        coords = np.column_stack((centroids.x, centroids.y))
        n = len(coords)

        # Calcular distancias y diferencias cuadráticas
        dists = cdist(coords, coords, metric='euclidean')
        
        # Obtener los índices del triángulo superior
        idx_i, idx_j = np.triu_indices(n, k=1)
        pair_dists = dists[idx_i, idx_j]
        
        # Semivarianza: 0.5 * (z_i - z_j)^2
        pair_semivariance = 0.5 * ((values[idx_i] - values[idx_j]) ** 2)

        # Definir la distancia de corte (half of max distance to avoid boundary noise)
        max_dist = np.max(pair_dists)
        cutoff_dist = max_dist * 0.5

        # Crear los intervalos de distancia (lags)
        bins = np.linspace(0, cutoff_dist, num_lags + 1)
        bin_centers = (bins[:-1] + bins[1:]) / 2.0

        empirical_semivariance = []
        counts = []

        for i in range(num_lags):
            mask = (pair_dists >= bins[i]) & (pair_dists < bins[i+1])
            vals = pair_semivariance[mask]
            if len(vals) > 0:
                empirical_semivariance.append(np.mean(vals))
                counts.append(len(vals))
            else:
                empirical_semivariance.append(0.0)
                counts.append(0)

        # Ajuste de un modelo esférico básico
        def spherical_model(h, nugget, partial_sill, range_a):
            nugget = abs(nugget)
            partial_sill = abs(partial_sill)
            range_a = abs(range_a) if abs(range_a) > 0 else 1.0

            result = np.where(
                h <= range_a,
                nugget + partial_sill * (1.5 * (h / range_a) - 0.5 * (h / range_a) ** 3),
                nugget + partial_sill
            )
            return result

        # Ajuste de un modelo de efecto hoyo
        def hole_effect_model(h, nugget, partial_sill, range_a):
            nugget = abs(nugget)
            partial_sill = abs(partial_sill)
            range_a = abs(range_a) if abs(range_a) > 0 else 1.0

            h_safe = np.where(h == 0.0, 1e-20, h)
            val = np.sin(np.pi * h_safe / range_a) / (np.pi * h_safe / range_a)
            return nugget + partial_sill * (1.0 - val)

        # Estimaciones iniciales
        est_nugget = empirical_semivariance[0] if len(empirical_semivariance) > 0 else 0.0
        est_sill = np.var(values)
        est_range = cutoff_dist * 0.5

        p0 = [est_nugget, est_sill - est_nugget, est_range]
        bounds = ([0.0, 0.0, 0.0], [est_sill * 2, est_sill * 5, cutoff_dist * 1.5])

        # Ajustar ambos modelos y elegir el de menor error cuadrático medio (MSE)
        fit_sph_nugget, fit_sph_sill, fit_sph_range = est_nugget, est_sill, est_range
        sph_mse = float('inf')
        sph_success = False
        
        try:
            popt_sph, _ = curve_fit(spherical_model, bin_centers, empirical_semivariance, p0=p0, bounds=bounds, maxfev=5000)
            fit_sph_nugget = float(popt_sph[0])
            fit_sph_sill = float(popt_sph[0] + popt_sph[1])
            fit_sph_range = float(popt_sph[2])
            
            y_pred_sph = spherical_model(bin_centers, *popt_sph)
            sph_mse = float(np.mean((np.array(empirical_semivariance) - y_pred_sph) ** 2))
            sph_success = True
        except Exception:
            pass

        fit_hole_nugget, fit_hole_sill, fit_hole_range = est_nugget, est_sill, est_range
        hole_mse = float('inf')
        hole_success = False
        
        try:
            popt_hole, _ = curve_fit(hole_effect_model, bin_centers, empirical_semivariance, p0=p0, bounds=bounds, maxfev=5000)
            fit_hole_nugget = float(popt_hole[0])
            fit_hole_sill = float(popt_hole[0] + popt_hole[1])
            fit_hole_range = float(popt_hole[2])
            
            y_pred_hole = hole_effect_model(bin_centers, *popt_hole)
            hole_mse = float(np.mean((np.array(empirical_semivariance) - y_pred_hole) ** 2))
            hole_success = True
        except Exception:
            pass

        # Seleccionar el mejor modelo
        if hole_success and (not sph_success or hole_mse < sph_mse):
            fit_nugget = fit_hole_nugget
            fit_sill = fit_hole_sill
            fit_range = fit_hole_range
            model_name = "efecto_hoyo"
        else:
            fit_nugget = fit_sph_nugget
            fit_sill = fit_sph_sill
            fit_range = fit_sph_range
            model_name = "esferico"

        return {
            'lags': bin_centers.tolist(),
            'semivarianza_empirica': [float(x) for x in empirical_semivariance],
            'nugget': fit_nugget,
            'sill': fit_sill,
            'rango': fit_range,
            'modelo': model_name
        }
