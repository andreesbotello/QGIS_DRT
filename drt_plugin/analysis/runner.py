# -*- coding: utf-8 -*-
"""
Coordinador principal de la secuencia de análisis del módulo de Memoria 1.
"""

import os
import datetime
import numpy as np
import pandas as pd
from osgeo import gdal
from .compatibility import SpatialCompatibility
from .spectral import SpectralDiagnostics
from .spatial import SpatialDiagnostics
from .indexes import IndexCalculation

def run_memoria1_diagnostics(raster_path, vector_path, class_field, log_callback=None):
    """Ejecuta de manera secuencial todos los diagnósticos analíticos de la Memoria 1.

    Args:
        raster_path (str): Ruta al archivo ráster (.tif).
        vector_path (str): Ruta al archivo vectorial (.shp).
        class_field (str): Campo del vector que clasifica los objetos territoriales.
        log_callback (function): Función callback opcional para registrar el progreso en tiempo real.

    Returns:
        tuple: (dict con resultados completos del diagnóstico, pd.DataFrame con datos estructurados para exportación).
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Iniciando secuencia de diagnósticos de Memoria 1...")

    # 1. Análisis de Compatibilidad Espacial
    log("Fase 1/5: Evaluando compatibilidad espacial y cobertura...")
    compat = SpatialCompatibility(raster_path, vector_path)
    
    log("  Comprobando Sistema de Referencia de Coordenadas (CRS)...")
    crs_res = compat.check_crs()
    if crs_res['reprojected']:
        log(f"  [Advertencia] CRS difieren. Vector reproyectado automáticamente de {crs_res['vector_crs']} a {crs_res['raster_crs']}.")
    else:
        log(f"  CRS coinciden: {crs_res['raster_crs']}")

    log("  Calculando extensión geográfica y área de intersección...")
    extents = compat.get_extents()
    log(f"  Solapamiento espacial de Bounding Boxes: {extents['overlap_percentage']:.2f}%")

    log("  Calculando cobertura efectiva de polígonos...")
    coverage = compat.calculate_coverage()
    log(f"  Polígonos cubiertos por el ráster: {coverage['polygons_inside']} de {coverage['total_polygons']} ({coverage['coverage_ratio']:.2f}%)")

    log("  Analizando resolución observacional...")
    resolution = compat.calculate_observational_resolution()
    log(f"  Mediana del ratio píxel/polígono: {resolution['ratio_pixel_poly_median']:.6f}")

    # 2. Análisis Espectral y Componentes Principales
    log("Fase 2/5: Ejecutando diagnóstico espectral inicial y PCA global...")
    spectral = SpectralDiagnostics(raster_path)
    
    log("  Calculando estadísticas básicas de bandas (media, varianza, asimetría, entropía)...")
    spectral_stats = spectral.calculate_band_statistics()
    
    log("  Evaluando matrices de correlación (redundancia espectral)...")
    redundancy = spectral.calculate_redundancy()

    log("  Calculando análisis de componentes principales (PCA)...")
    pca = spectral.calculate_pca()
    log(f"  Dimensionalidad efectiva (95% varianza): {pca['dimensionalidad_efectiva']} componentes")

    # 3. Análisis de Estructura Espacial (sobre el vector proyectado al CRS del ráster)
    log("Fase 3/5: Evaluando estructura espacial y autocorrelación...")
    spatial = SpatialDiagnostics(raster_path, vector_path)
    # Se sobrescribe el GeoDataFrame con el ya validado/reproyectado en el paso 1
    spatial.vector_gdf = compat.vector_gdf

    log("  Calculando estadísticas de zona (Zonal Means) sobre Banda 1...")
    zonal_means = spatial.calculate_zonal_means(band_idx=1)

    log("  Calculando Moran's I global...")
    moran = spatial.calculate_moran(zonal_means)
    log(f"  Índice de Moran: {moran['moran_i']:.4f} (Esperanza: {moran['esperanza']:.4f})")

    log("  Calculando semivariograma empírico y ajuste de modelo esférico...")
    semivariogram = spatial.calculate_semivariogram(zonal_means)
    log(f"  Variograma - Nugget: {semivariogram['nugget']:.4f}, Sill: {semivariogram['sill']:.4f}, Rango: {semivariogram['rango']:.2f} m")

    # 4. Cálculo de Índices
    log("Fase 4/5: Evaluando el índice sintético de observabilidad...")
    # Obtener el coeficiente de correlación absoluto promedio
    pearson_mat = np.abs(np.array(redundancy['pearson']))
    np.fill_diagonal(pearson_mat, 0.0)
    # Excluyendo la diagonal, calcular promedio de correlación entre bandas distintas
    n_bands = pearson_mat.shape[0]
    mean_abs_corr = float(np.sum(pearson_mat) / (n_bands * (n_bands - 1))) if n_bands > 1 else 0.0

    # Promedio de la entropía de Shannon de todas las bandas
    mean_entropy = float(np.mean([b['entropia'] for b in spectral_stats]))

    # Cálculo sintético del TOI
    toi = IndexCalculation.calculate_toi(
        coverage_ratio=coverage['coverage_ratio'],
        median_ratio_pixel_poly=resolution['ratio_pixel_poly_median'],
        mean_entropy=mean_entropy,
        mean_abs_correlation=mean_abs_corr,
        moran_i=moran['moran_i']
    )
    log(f"  Índice TOI calculado: {toi['toi']:.2f} ({toi['clasificacion']})")

    # 5. Estructurar metadatos del diagnóstico
    log("Fase 5/5: Compilando resultados y preparando tabla de exportación...")
    clean_vector_path = vector_path.split('|')[0] if vector_path else ""
    meta = {
        'raster_name': os.path.basename(raster_path),
        'vector_name': os.path.basename(clean_vector_path),
        'class_field': class_field,
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    results = {
        'meta': meta,
        'crs': crs_res,
        'extents': extents,
        'coverage': coverage,
        'resolution': resolution,
        'spectral_stats': spectral_stats,
        'redundancy': redundancy,
        'pca': {
            'varianza_explicada': pca['varianza_explicada'],
            'varianza_acumulada': pca['varianza_acumulada'],
            'effective_dimensionality': pca['dimensionalidad_efectiva']
        },
        'spatial_structure': {
            'moran': moran,
            'semivariograma': semivariogram
        },
        'toi': toi
    }

    # Extraer los datos crudos a nivel de píxel para todas las bandas
    log("  Extrayendo píxeles crudos de cada objeto territorial para Fase 3...")
    export_df = extract_raw_pixels(spectral.ds, compat.vector_gdf, class_field)

    log("Secuencia de diagnóstico completada exitosamente.")
    return results, export_df

def extract_raw_pixels(ds, gdf, class_field):
    """Extrae las coordenadas y los valores crudos de todas las bandas para cada píxel dentro de los polígonos.

    Args:
        ds (gdal.Dataset): Dataset de GDAL del ráster.
        gdf (gpd.GeoDataFrame): Capa vectorial de polígonos.
        class_field (str): Campo que contiene la clase del polígono.

    Returns:
        pd.DataFrame: Tabla estructurada con píxeles crudos georreferenciados.
    """
    from shapely.prepared import prep
    from shapely.geometry import Point

    gt = ds.GetGeoTransform()
    inv_gt = gdal.InvGeoTransform(gt)
    num_bands = ds.RasterCount

    bands = [ds.GetRasterBand(i) for i in range(1, num_bands + 1)]
    nodatas = [b.GetNoDataValue() for b in bands]

    pixel_records = []

    for idx, geom in enumerate(gdf.geometry):
        if geom is None or geom.is_empty:
            continue
        
        clase_val = gdf.iloc[idx][class_field] if class_field in gdf.columns else 'Desconocida'
        objeto_id = idx + 1
        
        xmin, ymin, xmax, ymax = geom.bounds
        col1, row1 = gdal.ApplyGeoTransform(inv_gt, xmin, ymax)
        col2, row2 = gdal.ApplyGeoTransform(inv_gt, xmax, ymin)
        
        col_min = max(0, int(np.floor(col1)))
        row_min = max(0, int(np.floor(row1)))
        col_max = min(ds.RasterXSize - 1, int(np.ceil(col2)))
        row_max = min(ds.RasterYSize - 1, int(np.ceil(row2)))
        
        cols = col_max - col_min + 1
        rows = row_max - row_min + 1
        
        if cols <= 0 or rows <= 0:
            continue
            
        band_arrs = []
        for b in bands:
            arr = b.ReadAsArray(col_min, row_min, cols, rows)
            if arr is not None:
                band_arrs.append(arr.astype(np.float64))
        
        if len(band_arrs) < num_bands:
            continue
            
        cols_arr = np.arange(col_min, col_max + 1) + 0.5
        rows_arr = np.arange(row_min, row_max + 1) + 0.5
        px_x, px_y = np.meshgrid(cols_arr, rows_arr)
        
        xs = gt[0] + px_x * gt[1]
        ys = gt[3] + px_y * gt[5]
        
        points_flat = [Point(x, y) for x, y in zip(xs.ravel(), ys.ravel())]
        prepared_geom = prep(geom)
        inside_mask = np.array([prepared_geom.contains(p) for p in points_flat])
        
        if not np.any(inside_mask):
            cx, cy = geom.centroid.x, geom.centroid.y
            c_col, c_row = gdal.ApplyGeoTransform(inv_gt, cx, cy)
            c_col = max(0, min(ds.RasterXSize - 1, int(c_col)))
            c_row = max(0, min(ds.RasterYSize - 1, int(c_row)))
            
            row_record = {
                'objeto_id': objeto_id,
                'clase': clase_val,
                'pixel_x': cx,
                'pixel_y': cy
            }
            for b_idx in range(num_bands):
                val = bands[b_idx].ReadAsArray(c_col, c_row, 1, 1)[0, 0]
                nd = nodatas[b_idx]
                row_record[f"b{b_idx+1}"] = float(val) if (nd is None or val != nd) else np.nan
            pixel_records.append(row_record)
        else:
            xs_flat = xs.ravel()[inside_mask]
            ys_flat = ys.ravel()[inside_mask]
            flat_band_vals = [arr.ravel()[inside_mask] for arr in band_arrs]
            
            for k in range(len(xs_flat)):
                row_record = {
                    'objeto_id': objeto_id,
                    'clase': clase_val,
                    'pixel_x': float(xs_flat[k]),
                    'pixel_y': float(ys_flat[k])
                }
                has_nodata = False
                for b_idx in range(num_bands):
                    val = flat_band_vals[b_idx][k]
                    nd = nodatas[b_idx]
                    if nd is not None and val == nd:
                        has_nodata = True
                        break
                    row_record[f"b{b_idx+1}"] = float(val)
                
                if not has_nodata:
                    pixel_records.append(row_record)

    df_out = pd.DataFrame(pixel_records)
    if not df_out.empty:
        df_out = df_out.dropna()
    return df_out

def run_memoria2_diagnostics(raster_path, vector_path, class_field, 
                             input_csv=None, 
                             filter_collinearity=False, 
                             green_band=None, red_band=None, nir_band=None, 
                             log_callback=None):
    """Ejecuta la secuencia de construcción del Objeto Territorial (Fase 3) y la Memoria 2 (Fase 4).

    Args:
        raster_path (str): Ruta al archivo ráster (.tif).
        vector_path (str): Ruta al archivo vectorial (.shp).
        class_field (str): Campo de clase del vector.
        input_csv (str): Ruta al CSV de píxeles crudos (opcional).
        filter_collinearity (bool): Si es True, filtra descriptores altamente correlacionados.
        green_band (int): Índice de la banda verde.
        red_band (int): Índice de la banda roja.
        nir_band (int): Índice de la banda NIR.
        log_callback (function): Función para registrar mensajes.

    Returns:
        tuple: (dict con resultados detallados, pd.DataFrame con descriptores por polígono).
    """
    def log(msg):
        if log_callback:
            log_callback(msg)

    log("Iniciando secuencia de diagnósticos de la Memoria 2...")

    # 1. Alineación y Compatibilidad Espacial
    log("Fase 1/4: Comprobando CRS y alineamiento espacial...")
    compat = SpatialCompatibility(raster_path, vector_path)
    crs_res = compat.check_crs()
    if crs_res['reprojected']:
        log("  [Advertencia] Vector reproyectado automáticamente para coincidir con el ráster.")

    # 2. Construcción del Objeto Territorial (M2)
    log("Fase 2/4: Extrayendo descriptores del Objeto Territorial (M2)...")
    from .features import FeatureExtractor
    
    # Abrir dataset ráster
    ds = gdal.Open(raster_path)
    if not ds:
        raise IOError(f"No se pudo abrir el ráster para extracción de descriptores: {raster_path}")

    # Extraer variables espectrales, texturales (GLCM), locales (variografía), geométricas y topológicas
    extractor = FeatureExtractor(
        ds, compat.vector_gdf, 
        green_band=green_band, red_band=red_band, nir_band=nir_band, 
        input_csv=input_csv
    )
    df_features = extractor.extract_features(class_field, log_callback=log)
    log(f"  Extracción completada. Generados {len(df_features)} objetos con {df_features.shape[1] - 2} descriptores cada uno.")

    # 3. Diagnósticos de Separabilidad (M3)
    log("Fase 3/4: Evaluando colinealidad y clustering exploratorio (M3)...")
    from .separability import SeparabilityDiagnostics
    
    diag = SeparabilityDiagnostics(df_features, filter_collinearity=filter_collinearity)
    
    log("  Comprobando correlación y variables colineales...")
    collin = diag.analyze_collinearity()
    log(f"  Detectados {len(collin['redundant_pairs'])} pares de variables con alta colinealidad (>0.85).")

    log("  Ejecutando Análisis de Componentes Principales (PCA) del espacio de variables...")
    pca_res = diag.analyze_pca()
    log(f"  Dimensionalidad intrínseca (95% varianza): {pca_res['dimensionalidad_intrinseca']} componentes principales.")

    log("  Calculando importancia de variables (Mutual Information) respecto a las clases...")
    mi_res = diag.analyze_mutual_information()

    log("  Optimizando agrupamiento espacial mediante K-Means (Silueta/Davies-Bouldin)...")
    clustering = diag.analyze_clustering()
    log(f"  K óptimo seleccionado: {clustering['optimal_k']} (Silhouette Score: {clustering['optimal_silhouette']:.4f}).")

    log("  Proyectando descriptores a 2D mediante t-SNE para visualización latente...")
    tsne_coords = diag.run_tsne()

    log("  Calculando correspondencia y pureza Clase-Cluster...")
    correspondence = diag.analyze_correspondence(clustering['labels'])
    log(f"  Pureza de agrupamiento global: {correspondence['global_purity']*100:.2f}%.")

    log("  Calculando distancias estadísticas de Mahalanobis y Bhattacharyya interclase...")
    distances = diag.calculate_interclass_distances(pca_res['dimensionalidad_intrinseca'])

    # 4. Cálculo de Índices y Consolidación de Resultados
    log("Fase 4/4: Consolidando métricas e índice de aprendibilidad (TLI)...")
    # Promediar distancias de Mahalanobis (excluyendo la diagonal)
    mahalanobis_arr = np.array(distances['mahalanobis'])
    n_classes = mahalanobis_arr.shape[0]
    mean_mahalanobis = float(np.sum(mahalanobis_arr) / (n_classes * (n_classes - 1))) if n_classes > 1 else 0.0

    # Ratio de redundancia
    n_vars = len(collin['columns'])
    n_redundant = len(collin['redundant_pairs'])
    redundant_ratio = (n_redundant / n_vars) if n_vars > 0 else 0.0

    tli_res = diag.calculate_tli(
        mean_mahalanobis=mean_mahalanobis,
        global_purity=correspondence['global_purity'],
        optimal_silhouette=clustering['optimal_silhouette'],
        redundant_ratio=redundant_ratio
    )
    log(f"  Índice TLI calculado: {tli_res['tli']:.2f} ({tli_res['clasificacion']})")

    clean_vector_path = vector_path.split('|')[0] if vector_path else ""
    meta = {
        'raster_name': os.path.basename(raster_path),
        'vector_name': os.path.basename(clean_vector_path),
        'class_field': class_field,
        'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }

    results = {
        'meta': meta,
        'collinearity': collin,
        'pca': pca_res,
        'mutual_info': mi_res,
        'clustering': {
            'scores': clustering['scores'],
            'optimal_k': clustering['optimal_k'],
            'optimal_silhouette': clustering['optimal_silhouette']
        },
        'tsne': tsne_coords,
        'y_real': df_features['clase'].tolist(),
        'cluster_labels': clustering['labels'],
        'correspondence': correspondence,
        'distances': distances,
        'tli': tli_res
    }

    log("Secuencia de diagnóstico de Memoria 2 completada exitosamente.")
    
    # Cerrar dataset
    ds = None
    
    return results, df_features
