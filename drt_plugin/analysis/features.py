# -*- coding: utf-8 -*-
"""
Módulo para la extracción de descriptores territoriales (Features) a nivel de polígono.
"""

import numpy as np
import pandas as pd
from scipy import stats
from scipy.optimize import curve_fit
from scipy.spatial.distance import cdist
from sklearn.decomposition import PCA
from shapely.geometry import Polygon

class FeatureExtractor:
    """Extrae descriptores espectrales, texturales, variográficos, geométricos y topológicos."""

    def __init__(self, raster_ds, vector_gdf):
        """Inicializa el extractor con los conjuntos de datos correspondientes.

        Args:
            raster_ds (gdal.Dataset): Dataset de GDAL del ráster.
            vector_gdf (gpd.GeoDataFrame): Capa vectorial de polígonos (ya reproyectada).
        """
        self.ds = raster_ds
        self.gdf = vector_gdf.copy()
        
        # Obtener información básica de bandas
        self.gt = self.ds.GetGeoTransform()
        self.inv_gt = gdal_inv_gt = self.ds.GetGeoTransform() # Se usará gdal.InvGeoTransform más adelante
        self.num_bands = self.ds.RasterCount
        self.bands = [self.ds.GetRasterBand(i) for i in range(1, self.num_bands + 1)]
        self.nodatas = [b.GetNoDataValue() for b in self.bands]

    def extract_features(self, class_field, log_callback=None):
        """Extrae la matriz completa de descriptores para todos los objetos territoriales.

        Args:
            class_field (str): Nombre del campo que define la clase territorial.
            log_callback (function): Callback opcional para registrar el avance.

        Returns:
            pd.DataFrame: Tabla con descriptores calculados por polígono.
        """
        def log(msg):
            if log_callback:
                log_callback(msg)

        log("Iniciando extracción de descriptores del Objeto Territorial...")
        
        # 1. Calcular Descriptores Topológicos Globales (para evitar recalcular por fila)
        log("  Calculando relaciones topológicas globales...")
        topological_feats = self._extract_topological_features()

        features_records = []
        n_features = len(self.gdf)

        # Importar GDAL de forma segura
        from osgeo import gdal
        inv_gt = gdal.InvGeoTransform(self.gt)

        # Preparar shapely
        from shapely.prepared import prep
        from shapely.geometry import Point

        for idx, geom in enumerate(self.gdf.geometry):
            if geom is None or geom.is_empty:
                continue

            objeto_id = idx + 1
            clase_val = self.gdf.iloc[idx][class_field] if class_field in self.gdf.columns else 'Desconocida'
            
            if log_callback and (idx + 1) % 20 == 0:
                log(f"    Procesando objeto {idx + 1} de {n_features}...")

            # --- A. Extracción de Píxeles Crudos del Polígono ---
            xmin, ymin, xmax, ymax = geom.bounds
            col1, row1 = gdal.ApplyGeoTransform(inv_gt, xmin, ymax)
            col2, row2 = gdal.ApplyGeoTransform(inv_gt, xmax, ymin)
            
            col_min = max(0, int(np.floor(col1)))
            row_min = max(0, int(np.floor(row1)))
            col_max = min(self.ds.RasterXSize - 1, int(np.ceil(col2)))
            row_max = min(self.ds.RasterYSize - 1, int(np.ceil(row2)))
            
            cols = col_max - col_min + 1
            rows = row_max - row_min + 1
            
            # Inicializar registro de descriptores
            record = {
                'objeto_id': objeto_id,
                'clase': clase_val
            }

            # Si el área es nula o no hay píxeles en el recuadro, saltar o usar centroid
            if cols <= 0 or rows <= 0:
                self._fill_dummy_values(record)
                features_records.append(record)
                continue

            band_arrs = []
            for b in self.bands:
                arr = b.ReadAsArray(col_min, row_min, cols, rows)
                if arr is not None:
                    band_arrs.append(arr.astype(np.float64))

            if len(band_arrs) < self.num_bands:
                self._fill_dummy_values(record)
                features_records.append(record)
                continue

            # Mapeo de coordenadas
            cols_arr = np.arange(col_min, col_max + 1) + 0.5
            rows_arr = np.arange(row_min, row_max + 1) + 0.5
            px_x, px_y = np.meshgrid(cols_arr, rows_arr)
            
            xs = self.gt[0] + px_x * self.gt[1]
            ys = self.gt[3] + px_y * self.gt[5]
            
            points_flat = [Point(x, y) for x, y in zip(xs.ravel(), ys.ravel())]
            prepared_geom = prep(geom)
            inside_mask = np.array([prepared_geom.contains(p) for p in points_flat])

            # Filtrar por NoData
            xs_inside = xs.ravel()[inside_mask]
            ys_inside = ys.ravel()[inside_mask]
            
            # Extraer valores de bandas
            band_vals = []
            for b_idx in range(self.num_bands):
                vals = band_arrs[b_idx].ravel()[inside_mask]
                nd = self.nodatas[b_idx]
                if nd is not None:
                    # Reemplazar NoData por NaN
                    vals[vals == nd] = np.nan
                band_vals.append(vals)

            # Si no hay píxeles válidos dentro del polígono, usar centroid fallback
            if len(xs_inside) == 0 or np.all(np.isnan(band_vals[0])):
                # Centroid fallback
                cx, cy = geom.centroid.x, geom.centroid.y
                c_col, c_row = gdal.ApplyGeoTransform(inv_gt, cx, cy)
                c_col = max(0, min(self.ds.RasterXSize - 1, int(c_col)))
                c_row = max(0, min(self.ds.RasterYSize - 1, int(c_row)))
                
                band_vals = []
                for b_idx in range(self.num_bands):
                    val = self.bands[b_idx].ReadAsArray(c_col, c_row, 1, 1)[0, 0]
                    nd = self.nodatas[b_idx]
                    band_vals.append(np.array([float(val) if (nd is None or val != nd) else np.nan]))
                xs_inside = np.array([cx])
                ys_inside = np.array([cy])

            # Limpiar filas con NaN en cualquier banda
            valid_mask = ~np.any(np.isnan(band_vals), axis=0)
            xs_clean = xs_inside[valid_mask]
            ys_clean = ys_inside[valid_mask]
            band_vals_clean = [b[valid_mask] for b in band_vals]

            if len(xs_clean) == 0:
                self._fill_dummy_values(record)
                features_records.append(record)
                continue

            # X_data es una matriz (N, 7) de píxeles
            X_data = np.column_stack(band_vals_clean)
            N_pixels = X_data.shape[0]

            # --- 1. Descriptores Espectrales ---
            for b_idx in range(self.num_bands):
                vals = X_data[:, b_idx]
                prefix = f"b{b_idx+1}_"
                record[prefix + "mean"] = float(np.mean(vals))
                record[prefix + "median"] = float(np.median(vals))
                record[prefix + "std"] = float(np.std(vals)) if len(vals) > 1 else 0.0
                record[prefix + "min"] = float(np.min(vals))
                record[prefix + "max"] = float(np.max(vals))
                record[prefix + "p25"] = float(np.percentile(vals, 25))
                record[prefix + "p75"] = float(np.percentile(vals, 75))
                
                # Asimetría, Curtosis y MAD
                if len(vals) > 2 and np.std(vals) > 0:
                    record[prefix + "skew"] = float(stats.skew(vals))
                    record[prefix + "kurt"] = float(stats.kurtosis(vals))
                else:
                    record[prefix + "skew"] = 0.0
                    record[prefix + "kurt"] = 0.0
                
                record[prefix + "mad"] = float(np.median(np.abs(vals - np.median(vals))))
                
                # Entropía de Shannon del píxel
                record[prefix + "entropy"] = self._calculate_shannon_entropy(vals)

            # --- 2. Descriptores Texturales (GLCM en NumPy sobre PC1 local) ---
            # Calcular PC1 local
            if N_pixels >= 2 and X_data.shape[1] > 1:
                try:
                    pca_local = PCA(n_components=1)
                    pc1_local = pca_local.fit_transform(X_data).ravel()
                except Exception:
                    pc1_local = X_data[:, 0]  # Fallback a Banda 1 si falla PCA
            else:
                pc1_local = X_data[:, 0]

            # Obtener texturas de GLCM
            contrast, homogeneity, asm, entropy_glcm = self._calculate_glcm_textures(
                pc1_local, xs_clean, ys_clean, xmin, ymax
            )
            record["glcm_contrast"] = contrast
            record["glcm_homogeneity"] = homogeneity
            record["glcm_asm"] = asm
            record["glcm_entropy"] = entropy_glcm

            # --- 3. Descriptores Variográficos Locales ---
            nugget, sill, range_val = self._calculate_local_variography(pc1_local, xs_clean, ys_clean)
            record["var_nugget"] = nugget
            record["var_sill"] = sill
            record["var_range"] = range_val

            # --- 4. Descriptores Geométricos ---
            area = geom.area
            perimeter = geom.length
            record["geom_area"] = float(area)
            record["geom_perimeter"] = float(perimeter)
            record["geom_circularity"] = float(4 * np.pi * area / (perimeter**2)) if perimeter > 0 else 0.0
            
            convex_area = geom.convex_hull.area
            record["geom_convexity"] = float(area / convex_area) if convex_area > 0 else 1.0
            
            # Elongación desde el mínimo rectángulo orientado
            try:
                rect = geom.minimum_rotated_rectangle
                if isinstance(rect, Polygon):
                    coords = list(rect.exterior.coords)
                    side1 = np.sqrt((coords[0][0] - coords[1][0])**2 + (coords[0][1] - coords[1][1])**2)
                    side2 = np.sqrt((coords[1][0] - coords[2][0])**2 + (coords[1][1] - coords[2][1])**2)
                    min_side = min(side1, side2)
                    max_side = max(side1, side2)
                    record["geom_elongation"] = float(min_side / max_side) if max_side > 0 else 1.0
                else:
                    record["geom_elongation"] = 1.0
            except Exception:
                record["geom_elongation"] = 1.0

            record["geom_shape_index"] = float(perimeter / (4 * np.sqrt(area))) if area > 0 else 0.0

            # --- 5. Descriptores Topológicos ---
            record["top_neighbors"] = float(topological_feats['neighbors_count'][idx])
            record["top_proximity"] = float(topological_feats['proximity_3'][idx])

            features_records.append(record)

        df_out = pd.DataFrame(features_records)
        return df_out

    def _fill_dummy_values(self, record):
        """Llena el registro con valores nulos o por defecto si la extracción falla."""
        for b_idx in range(self.num_bands):
            prefix = f"b{b_idx+1}_"
            for stat in ["mean", "median", "std", "min", "max", "p25", "p75", "skew", "kurt", "mad", "entropy"]:
                record[prefix + stat] = np.nan
        record["glcm_contrast"] = np.nan
        record["glcm_homogeneity"] = np.nan
        record["glcm_asm"] = np.nan
        record["glcm_entropy"] = np.nan
        record["var_nugget"] = np.nan
        record["var_sill"] = np.nan
        record["var_range"] = np.nan
        record["geom_area"] = 0.0
        record["geom_perimeter"] = 0.0
        record["geom_circularity"] = 0.0
        record["geom_convexity"] = 1.0
        record["geom_elongation"] = 1.0
        record["geom_shape_index"] = 0.0
        record["top_neighbors"] = 0.0
        record["top_proximity"] = np.nan

    def _calculate_shannon_entropy(self, vals):
        """Calcula la entropía de Shannon de un array de datos cuantizándolo a 16 bins."""
        if len(vals) <= 1 or np.all(vals == vals[0]):
            return 0.0
        counts, _ = np.histogram(vals, bins=16)
        probs = counts / float(len(vals))
        probs = probs[probs > 0]
        return float(-np.sum(probs * np.log2(probs)))

    def _calculate_glcm_textures(self, pc1, xs, ys, xmin, ymax):
        """Calcula las texturas de co-ocurrencia espacial (GLCM) mediante NumPy.

        Cuantiza a 8 niveles de gris y calcula la matriz de co-ocurrencia para d=1 (horizontal/vertical).
        """
        N = len(pc1)
        if N < 4:
            return 0.0, 1.0, 1.0, 0.0  # Valores por defecto para texturas planas/muy pequeñas

        # Cuantizar linealmente a 8 niveles de gris (0 a 7)
        min_v, max_v = pc1.min(), pc1.max()
        if max_v > min_v:
            quantized = np.clip(((pc1 - min_v) / (max_v - min_v) * 7.999).astype(int), 0, 7)
        else:
            quantized = np.zeros_like(pc1, dtype=int)

        # Mapear coordenadas a índices de fila y columna locales
        # Tamaño de píxel nominal de 30m
        px_w, px_h = abs(self.gt[1]), abs(self.gt[5])
        cols = np.round((xs - xmin) / px_w).astype(int)
        rows = np.round((ymax - ys) / px_h).astype(int)

        c_min, r_min = cols.min(), rows.min()
        cols_local = cols - c_min
        rows_local = rows - r_min

        H = rows_local.max() + 1
        W = cols_local.max() + 1

        # Crear cuadrícula local, -1 indica fuera del polígono
        grid = np.full((H, W), -1, dtype=int)
        grid[rows_local, cols_local] = quantized

        # Acumulador de co-ocurrencia
        glcm = np.zeros((8, 8), dtype=float)

        # Direcciones: Horizontal (0, 1) y Vertical (1, 0)
        offsets = [(0, 1), (1, 0)]

        for dr, dc in offsets:
            for r in range(H):
                for c in range(W):
                    v1 = grid[r, c]
                    if v1 == -1:
                        continue
                    tr, tc = r + dr, c + dc
                    if 0 <= tr < H and 0 <= tc < W:
                        v2 = grid[tr, tc]
                        if v2 != -1:
                            glcm[v1, v2] += 1.0

        # Hacer simétrica
        glcm = glcm + glcm.T
        glcm_sum = glcm.sum()

        if glcm_sum == 0:
            return 0.0, 1.0, 1.0, 0.0

        # Normalizar
        P = glcm / glcm_sum

        # Índices i y j para operaciones vectorizadas
        i, j = np.meshgrid(np.arange(8), np.arange(8), indexing='ij')

        # Contraste
        contrast = float(np.sum(((i - j) ** 2) * P))
        # Homogeneidad
        homogeneity = float(np.sum(P / (1.0 + (i - j) ** 2)))
        # ASM / Energy
        asm = float(np.sum(P ** 2))
        # Entropía
        entropy = float(-np.sum(P * np.log2(P + 1e-10)))

        return contrast, homogeneity, asm, entropy

    def _calculate_local_variography(self, pc1, xs, ys):
        """Calcula el variograma local empírico y estima nugget, sill y rango."""
        N = len(pc1)
        if N < 5:
            # Fallback por defecto si hay muy pocos píxeles
            return 0.0, float(np.var(pc1)) if N > 1 else 0.0, 30.0

        # Muestrear si el polígono tiene demasiados píxeles para evitar alto costo computacional
        if N > 400:
            idx_sample = np.random.choice(N, size=400, replace=False)
            x_s = xs[idx_sample]
            y_s = ys[idx_sample]
            z_s = pc1[idx_sample]
        else:
            x_s = xs
            y_s = ys
            z_s = pc1

        # Matriz de distancias
        dx = x_s[:, np.newaxis] - x_s[np.newaxis, :]
        dy = y_s[:, np.newaxis] - y_s[np.newaxis, :]
        dists = np.sqrt(dx**2 + dy**2)

        # Semivarianza (0.5 * squared differences)
        sq_diff = 0.5 * ((z_s[:, np.newaxis] - z_s[np.newaxis, :])**2)

        # Triángulo superior
        triu = np.triu_indices(len(x_s), k=1)
        flat_dists = dists[triu]
        flat_sq_diff = sq_diff[triu]

        max_d = flat_dists.max()
        if max_d <= 0:
            return 0.0, float(np.var(z_s)), 30.0

        # Generar 5 lags
        lags = np.linspace(0, max_d, 6)
        lag_centers = []
        semivars = []

        for i in range(5):
            mask = (flat_dists >= lags[i]) & (flat_dists < lags[i+1])
            if np.any(mask):
                lag_centers.append((lags[i] + lags[i+1]) / 2.0)
                semivars.append(np.mean(flat_sq_diff[mask]))

        # Ajuste del modelo esférico
        var_z = np.var(z_s)
        # Fallback por estimación robusta
        nugget_fb = 0.05 * var_z
        sill_fb = var_z
        range_fb = max_d * 0.5 if max_d > 0 else 30.0

        if len(lag_centers) < 3:
            return nugget_fb, sill_fb, range_fb

        # Definición del modelo esférico
        def spherical_model(h, nugget, sill, r):
            c = sill - nugget
            y = np.where(h <= r, nugget + c * (1.5 * h / r - 0.5 * (h / r)**3), sill)
            return y

        try:
            popt, _ = curve_fit(
                spherical_model,
                lag_centers,
                semivars,
                p0=[nugget_fb, sill_fb, range_fb],
                bounds=([0.0, 0.0, 10.0], [var_z * 2.0, var_z * 3.0, max_d * 1.5]),
                maxfev=1000
            )
            return float(popt[0]), float(popt[1]), float(popt[2])
        except Exception:
            return nugget_fb, sill_fb, range_fb

    def _extract_topological_features(self):
        """Calcula la cantidad de vecinos adyacentes y la distancia promedio a los 3 vecinos más cercanos."""
        n = len(self.gdf)
        neighbors_count = np.zeros(n, dtype=int)
        
        # Calcular contactos
        for idx in range(n):
            geom = self.gdf.geometry.iloc[idx]
            if geom is not None:
                # Filtrar y excluir el mismo polígono
                touches = self.gdf.geometry.touches(geom)
                neighbors_count[idx] = sum(touches)

        # Distancia de centroides
        centroids = self.gdf.geometry.centroid
        coords = np.array([[c.x, c.y] for c in centroids])
        dist_matrix = cdist(coords, coords)
        
        # Ignorar diagonal (distancia a uno mismo)
        np.fill_diagonal(dist_matrix, np.inf)

        # Distancia promedio a los 3 centroides más cercanos
        sorted_dists = np.sort(dist_matrix, axis=1)
        proximity_3 = np.mean(sorted_dists[:, :3], axis=1)

        return {
            'neighbors_count': neighbors_count,
            'proximity_3': proximity_3
        }
