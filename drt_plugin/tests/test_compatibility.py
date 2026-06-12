# -*- coding: utf-8 -*-
"""
Pruebas de integración para validar el correcto funcionamiento del backend de la Memoria 1.
"""

import os
from drt_plugin.analysis.compatibility import SpatialCompatibility
from drt_plugin.analysis.spectral import SpectralDiagnostics
from drt_plugin.analysis.spatial import SpatialDiagnostics
from drt_plugin.analysis.runner import run_memoria1_diagnostics

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
RASTER_PATH = os.path.join(BASE_DIR, "Data", "L8Toa.tif")
VECTOR_PATH = os.path.join(BASE_DIR, "Data", "valle1.shp")

def test_spatial_compatibility():
    """Valida los análisis del módulo de compatibilidad espacial."""
    if not os.path.exists(RASTER_PATH) or not os.path.exists(VECTOR_PATH):
        return

    compat = SpatialCompatibility(RASTER_PATH, VECTOR_PATH)
    
    # Comprobar CRS
    crs_res = compat.check_crs()
    assert 'match' in crs_res
    assert 'raster_crs' in crs_res
    
    # Comprobar extensiones y solapamiento
    extents = compat.get_extents()
    assert extents['intersection_extent'] is not None
    assert extents['overlap_percentage'] > 0.0

    # Comprobar cobertura
    coverage = compat.calculate_coverage()
    assert coverage['coverage_ratio'] > 0.0
    assert coverage['total_polygons'] == 100

    # Comprobar resolución observacional
    res = compat.calculate_observational_resolution()
    assert 'pixel_area_m2' in res
    assert len(res['ratios']) == 100

def test_spectral_diagnostics():
    """Valida las métricas espectrales y el PCA."""
    if not os.path.exists(RASTER_PATH):
        return

    spectral = SpectralDiagnostics(RASTER_PATH)
    
    # Estadísticas descriptivas de bandas
    stats = spectral.calculate_band_statistics()
    assert len(stats) == 7  # Landsat 8 de prueba tiene 7 bandas
    assert stats[0]['banda'] == 1
    assert 'entropia' in stats[0]

    # Redundancia espectral
    redundancy = spectral.calculate_redundancy(sample_size=1000)
    assert len(redundancy['pearson']) == 7
    assert len(redundancy['spearman']) == 7

    # PCA
    pca = spectral.calculate_pca(sample_size=1000)
    assert len(pca['varianza_explicada']) == 7
    assert pca['dimensionalidad_efectiva'] > 0

def test_full_runner_pipeline():
    """Valida la ejecución completa y acoplada del backend."""
    if not os.path.exists(RASTER_PATH) or not os.path.exists(VECTOR_PATH):
        return

    results, export_df = run_memoria1_diagnostics(RASTER_PATH, VECTOR_PATH, "layer")
    
    # Validar estructura de resultados
    assert results['toi']['toi'] > 0.0
    assert 'clasificacion' in results['toi']
    assert results['spatial_structure']['moran']['moran_i'] is not None
    assert results['spatial_structure']['semivariograma']['rango'] > 0.0

    # Validar DataFrame de exportación de píxeles crudos para Fase 3
    assert len(export_df) > 30000
    assert 'pixel_x' in export_df.columns
    assert 'pixel_y' in export_df.columns
    assert 'b1' in export_df.columns
    assert 'b7' in export_df.columns
    assert 'clase' in export_df.columns
    # El campo de clase de prueba es 'layer'
    assert export_df['clase'].iloc[0] is not None
