# -*- coding: utf-8 -*-
"""
Módulo para el cálculo del Índice de Observabilidad Territorial (TOI).
"""

import numpy as np

class IndexCalculation:
    """Calcula indicadores sintéticos de observabilidad basados en las métricas previas."""

    @staticmethod
    def calculate_toi(coverage_ratio, median_ratio_pixel_poly, mean_entropy, mean_abs_correlation, moran_i):
        """Calcula el Territorial Observability Index (TOI) a partir de pesos específicos.

        Args:
            coverage_ratio (float): Porcentaje de cobertura espacial (0 a 100).
            median_ratio_pixel_poly (float): Mediana de la relación de área píxel/polígono.
            mean_entropy (float): Promedio de la entropía de Shannon de las bandas (bits).
            mean_abs_correlation (float): Correlación absoluta promedio entre bandas (0 a 1).
            moran_i (float): Índice de Moran Global (-1 a 1).

        Returns:
            dict: Desglose del TOI y sub-puntajes de cada componente.
        """
        # 1. Puntaje de Cobertura Espacial (directo de 0 a 100)
        score_coverage = float(np.clip(coverage_ratio, 0.0, 100.0))

        # 2. Puntaje de Resolución Observacional
        # A menor relación (más píxeles caben en el polígono), mejor es la resolución.
        # Si la mediana de la relación >= 1.0 (un píxel por polígono o menos), el puntaje es 0.
        score_resolution = float(np.clip((1.0 - median_ratio_pixel_poly) * 100.0, 0.0, 100.0))

        # 3. Puntaje de Complejidad Espectral (basado en entropía respecto a 8 bits)
        score_complexity = float(np.clip((mean_entropy / 8.0) * 100.0, 0.0, 100.0))

        # 4. Puntaje de Redundancia (baja correlación entre bandas da mayor puntaje)
        score_redundancy = float(np.clip((1.0 - mean_abs_correlation) * 100.0, 0.0, 100.0))

        # 5. Puntaje de Estructura Espacial (alta autocorrelación espacial positiva da mayor puntaje)
        score_structure = float(np.clip(max(0.0, moran_i) * 100.0, 0.0, 100.0))

        # Pesos definidos en los requerimientos
        w_coverage = 0.20
        w_resolution = 0.25
        w_complexity = 0.25
        w_redundancy = 0.15
        w_structure = 0.15

        toi = (
            w_coverage * score_coverage +
            w_resolution * score_resolution +
            w_complexity * score_complexity +
            w_redundancy * score_redundancy +
            w_structure * score_structure
        )

        # Determinar nivel de aptitud observacional
        if toi >= 80.0:
            classification = "Excelente"
        elif toi >= 60.0:
            classification = "Buena"
        elif toi >= 40.0:
            classification = "Aceptable"
        else:
            classification = "Crítica"

        return {
            'toi': float(toi),
            'clasificacion': classification,
            'sub_scores': {
                'cobertura': score_coverage,
                'resolucion': score_resolution,
                'complejidad': score_complexity,
                'redundancia': score_redundancy,
                'estructura': score_structure
            }
        }
