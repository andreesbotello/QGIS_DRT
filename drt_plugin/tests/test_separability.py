# -*- coding: utf-8 -*-
"""
Pruebas unitarias e integración para validar el módulo de construcción del Objeto Territorial y la Memoria 2.
"""

import os
import pytest
import pandas as pd
import numpy as np
from osgeo import gdal
import geopandas as gpd

from drt_plugin.analysis.compatibility import SpatialCompatibility
from drt_plugin.analysis.features import FeatureExtractor
from drt_plugin.analysis.separability import SeparabilityDiagnostics
from drt_plugin.analysis.runner import run_memoria2_diagnostics

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RASTER_PATH = os.path.join(BASE_DIR, "Data", "L8Toa.tif")
VECTOR_PATH = os.path.join(BASE_DIR, "Data", "valle1.shp")

def test_feature_extraction():
    """Valida la extracción de descriptores espectrales, texturales (GLCM), variográficos y geométricos."""
    if not os.path.exists(RASTER_PATH) or not os.path.exists(VECTOR_PATH):
        pytest.skip("Test datasets not found.")

    ds = gdal.Open(RASTER_PATH)
    gdf = gpd.read_file(VECTOR_PATH)

    # Alinear CRS primero
    compat = SpatialCompatibility(RASTER_PATH, VECTOR_PATH)
    compat.check_crs()

    # Instanciar extractor
    extractor = FeatureExtractor(ds, compat.vector_gdf)
    df_feats = extractor.extract_features(class_field="layer")

    # Validar DataFrame de salida
    assert isinstance(df_feats, pd.DataFrame)
    assert not df_feats.empty
    assert len(df_feats) == len(gdf)
    
    # Comprobar columnas clave
    assert 'objeto_id' in df_feats.columns
    assert 'clase' in df_feats.columns
    
    # Validar descriptores espectrales
    assert 'b1_mean' in df_feats.columns
    assert 'b7_entropy' in df_feats.columns
    
    # Validar descriptores texturales
    assert 'glcm_contrast' in df_feats.columns
    assert 'glcm_entropy' in df_feats.columns
    
    # Validar descriptores variográficos
    assert 'var_range' in df_feats.columns
    assert 'var_sill' in df_feats.columns
    
    # Validar descriptores geométricos
    assert 'geom_area' in df_feats.columns
    assert 'geom_circularity' in df_feats.columns
    assert 'geom_elongation' in df_feats.columns
    
    # Validar descriptores topológicos
    assert 'top_neighbors' in df_feats.columns
    assert 'top_proximity' in df_feats.columns

    # Verificar que no hay todos NaNs en columnas críticas
    assert not df_feats['b1_mean'].isna().all()
    assert not df_feats['glcm_contrast'].isna().all()
    assert not df_feats['var_range'].isna().all()

def test_separability_diagnostics():
    """Valida el análisis de colinealidad, PCA, clustering, t-SNE y cálculo de distancias multivariantes."""
    # Crear datos simulados para no depender del tiempo de extracción de features en pruebas rápidas
    np.random.seed(42)
    n_samples = 30
    n_features = 15
    
    data = np.random.randn(n_samples, n_features)
    # Introducir colinealidad
    data[:, 2] = data[:, 0] * 0.95 + np.random.randn(n_samples) * 0.05
    data[:, 5] = data[:, 4] * 0.99
    
    # Asignar a clases
    clases = ['fincas'] * 10 + ['lotes'] * 10 + ['urbanos'] * 10
    
    df_dummy = pd.DataFrame(data, columns=[f"feat_{i}" for i in range(n_features)])
    df_dummy['objeto_id'] = range(1, n_samples + 1)
    df_dummy['clase'] = clases
    
    # Instanciar diagnósticos de separabilidad
    diag = SeparabilityDiagnostics(df_dummy)
    
    # 1. Colinealidad
    collin = diag.analyze_collinearity()
    assert len(collin['redundant_pairs']) >= 1
    found_redundant = False
    for pair in collin['redundant_pairs']:
        if 'feat_2' in [pair['var1'], pair['var2']] or 'feat_5' in [pair['var1'], pair['var2']]:
            found_redundant = True
            break
    assert found_redundant
    
    # 2. PCA
    pca_res = diag.analyze_pca()
    assert pca_res['dimensionalidad_intrinseca'] < n_features
    assert len(pca_res['varianza_explicada']) == len(diag.feature_cols)
    
    # 3. Mutual Information
    mi = diag.analyze_mutual_information()
    assert len(mi) == len(diag.feature_cols)
    assert 'variable' in mi[0]
    
    # 4. Clustering
    clustering = diag.analyze_clustering()
    assert clustering['optimal_k'] >= 2
    assert len(clustering['labels']) == n_samples
    
    # 5. t-SNE
    tsne_coords = diag.run_tsne()
    assert len(tsne_coords) == n_samples
    assert len(tsne_coords[0]) == 2
    
    # 6. Correspondencia
    corr = diag.analyze_correspondence(clustering['labels'])
    assert corr['global_purity'] > 0.0
    assert 'fincas' in corr['entropies']
    
    # 7. Distancias
    dist = diag.calculate_interclass_distances(intrinsic_dim=3)
    assert len(dist['classes']) == 3
    assert len(dist['mahalanobis']) == 3
    assert dist['mahalanobis'][0][0] == 0.0
    assert dist['mahalanobis'][0][1] > 0.0
    assert dist['bhattacharyya'][0][1] >= 0.0

def test_full_m2_pipeline():
    """Valida la ejecución del pipeline completo de la Memoria 2."""
    if not os.path.exists(RASTER_PATH) or not os.path.exists(VECTOR_PATH):
        pytest.skip("Test datasets not found.")

    results, df_feats = run_memoria2_diagnostics(RASTER_PATH, VECTOR_PATH, "layer")
    
    # Validar resultados globales
    assert 'tli' in results
    assert results['tli']['tli'] >= 0.0
    assert 'meta' in results
    assert 'clustering' in results
    assert len(results['tsne']) == len(df_feats)
    
    # Comprobar export_df
    assert isinstance(df_feats, pd.DataFrame)
    assert 'b1_mean' in df_feats.columns
