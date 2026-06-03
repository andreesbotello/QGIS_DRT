# -*- coding: utf-8 -*-
"""
Módulo para el diagnóstico espectral inicial, correlación y análisis de componentes principales (PCA).
"""

import numpy as np
import pandas as pd
from scipy.stats import skew, kurtosis
from sklearn.decomposition import PCA
from osgeo import gdal

class SpectralDiagnostics:
    """Calcula métricas estadísticas descriptivas, redundancia y dimensionalidad en datos ráster."""

    def __init__(self, raster_path):
        """Inicializa el diagnóstico espectral a partir de la ruta del ráster.

        Args:
            raster_path (str): Ruta al archivo ráster (.tif).
        """
        self.raster_path = raster_path
        self.ds = gdal.Open(self.raster_path)
        if not self.ds:
            raise IOError(f"No se pudo abrir el archivo ráster: {self.raster_path}")
        self.num_bands = self.ds.RasterCount

    def get_band_data(self, band_idx):
        """Lee una banda del ráster y retorna únicamente sus píxeles válidos.

        Args:
            band_idx (int): Índice de la banda (1-indexed).

        Returns:
            np.ndarray: Array unidimensional con los píxeles válidos.
        """
        band = self.ds.GetRasterBand(band_idx)
        arr = band.ReadAsArray().astype(np.float64)
        nodata = band.GetNoDataValue()

        # Filtrar valores NoData e infinitos/NaN
        mask = np.isfinite(arr)
        if nodata is not None:
            mask = mask & (arr != nodata)

        return arr[mask]

    def calculate_band_statistics(self):
        """Calcula estadísticas descriptivas para cada una de las bandas.

        Returns:
            list: Lista de diccionarios con las estadísticas de cada banda.
        """
        stats_list = []
        for i in range(1, self.num_bands + 1):
            pixels = self.get_band_data(i)
            if len(pixels) == 0:
                continue

            # Cálculo de la entropía de Shannon mediante histograma
            counts, _ = np.histogram(pixels, bins=256)
            probs = counts / np.sum(counts)
            probs = probs[probs > 0]
            entropy_val = -np.sum(probs * np.log2(probs))

            stats_list.append({
                'banda': i,
                'media': float(np.mean(pixels)),
                'varianza': float(np.var(pixels)),
                'std': float(np.std(pixels)),
                'asimetria': float(skew(pixels)),
                'curtosis': float(kurtosis(pixels)),
                'entropia': float(entropy_val),
                'total_pixeles': int(len(pixels))
            })

        return stats_list

    def calculate_redundancy(self, sample_size=100000):
        """Calcula las matrices de correlación de Pearson y Spearman entre bandas.

        Args:
            sample_size (int): Tamaño de muestra aleatoria de píxeles para acelerar el cálculo.

        Returns:
            dict: Matrices de correlación en formato tabular.
        """
        # Recopilar datos de todas las bandas
        band_data_dict = {}
        min_pixels = None

        for i in range(1, self.num_bands + 1):
            pixels = self.get_band_data(i)
            if len(pixels) == 0:
                raise ValueError(f"La banda {i} no contiene píxeles válidos.")
            band_data_dict[f"Banda_{i}"] = pixels
            if min_pixels is None or len(pixels) < min_pixels:
                min_pixels = len(pixels)

        # Alinear los arrays de píxeles (recortar al tamaño mínimo común si difieren)
        aligned_data = {}
        for name, arr in band_data_dict.items():
            aligned_data[name] = arr[:min_pixels]

        df = pd.DataFrame(aligned_data)

        # Muestreo aleatorio si supera el tamaño de muestra
        if len(df) > sample_size:
            df = df.sample(n=sample_size, random_state=42)

        pearson_matrix = df.corr(method='pearson').values.tolist()
        spearman_matrix = df.corr(method='spearman').values.tolist()
        band_names = list(df.columns)

        return {
            'nombres_bandas': band_names,
            'pearson': pearson_matrix,
            'spearman': spearman_matrix
        }

    def calculate_pca(self, sample_size=50000):
        """Aplica un análisis de componentes principales (PCA) global sobre el ráster.

        Args:
            sample_size (int): Número de píxeles para entrenar el PCA.

        Returns:
            dict: Resultados del PCA (scree plot, varianza acumulada, etc.).
        """
        # Recopilar arrays de píxeles alineados
        band_data_list = []
        min_pixels = None

        for i in range(1, self.num_bands + 1):
            pixels = self.get_band_data(i)
            band_data_list.append(pixels)
            if min_pixels is None or len(pixels) < min_pixels:
                min_pixels = len(pixels)

        if min_pixels == 0:
            raise ValueError("No hay datos de píxeles válidos comunes para ejecutar el PCA.")

        X = np.column_stack([arr[:min_pixels] for arr in band_data_list])

        # Escalar/Estandarizar variables
        mean = np.mean(X, axis=0)
        std = np.std(X, axis=0)
        # Evitar división por cero
        std[std == 0] = 1.0
        X_scaled = (X - mean) / std

        # Muestrear píxeles para el PCA
        if len(X_scaled) > sample_size:
            indices = np.random.choice(len(X_scaled), sample_size, replace=False)
            X_sample = X_scaled[indices]
        else:
            X_sample = X_scaled

        pca = PCA()
        pca.fit(X_sample)

        variance_ratio = pca.explained_variance_ratio_.tolist()
        cumulative_variance = np.cumsum(pca.explained_variance_ratio_).tolist()

        # Calcular dimensionalidad efectiva (número de componentes para llegar al 95% de varianza)
        effective_dim = int(np.argmax(np.array(cumulative_variance) >= 0.95) + 1)

        return {
            'varianza_explicada': variance_ratio,
            'varianza_acumulada': cumulative_variance,
            'dimensionalidad_efectiva': effective_dim
        }
