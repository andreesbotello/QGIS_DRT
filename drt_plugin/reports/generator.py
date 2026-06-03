# -*- coding: utf-8 -*-
"""
Módulo para la compilación y exportación de reportes de diagnóstico en formato HTML.
"""

import os
import base64
import io
import numpy as np
import matplotlib.pyplot as plt
from jinja2 import Template

class ReportGenerator:
    """Genera reportes de diagnóstico profesionales en formato HTML con gráficos embebidos."""

    @staticmethod
    def _fig_to_base64(fig):
        """Convierte una figura de Matplotlib en una cadena Base64 embebible en HTML.

        Args:
            fig (matplotlib.figure.Figure): Figura a convertir.

        Returns:
            str: Cadena formateada para la etiqueta src de HTML.
        """
        buf = io.BytesIO()
        fig.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        img_str = base64.b64encode(buf.read()).decode('utf-8')
        plt.close(fig)
        return f"data:image/png;base64,{img_str}"

    @classmethod
    def generate_m1_report(cls, results, output_path):
        """Genera el reporte HTML de la Memoria 1 (Observabilidad Territorial).

        Args:
            results (dict): Diccionario con los resultados de todos los análisis de M1.
            output_path (str): Ruta absoluta del archivo HTML a guardar.
        """
        # 1. Gráfico de Resolución Observacional (Histograma de Ratios)
        ratios = np.array(results['resolution']['ratios'])
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist(ratios, bins=20, color='#2980b9', edgecolor='black', alpha=0.7)
        ax.set_title("Relación de Escala (Píxel / Polígono)")
        ax.set_xlabel("Relación de Área")
        ax.set_ylabel("Frecuencia")
        ax.grid(True, linestyle='--', alpha=0.5)
        img_resolution = cls._fig_to_base64(fig)

        # 2. Heatmap de Correlación Espectral
        corr_matrix = np.array(results['redundancy']['pearson'])
        band_names = results['redundancy']['nombres_bandas']
        fig, ax = plt.subplots(figsize=(6, 5))
        cax = ax.imshow(corr_matrix, cmap='coolwarm', vmin=-1.0, vmax=1.0)
        fig.colorbar(cax, ax=ax)
        ax.set_xticks(np.arange(len(band_names)))
        ax.set_yticks(np.arange(len(band_names)))
        ax.set_xticklabels(band_names, rotation=45, ha='right')
        ax.set_yticklabels(band_names)
        # Anotaciones numéricas en la matriz
        for i in range(len(band_names)):
            for j in range(len(band_names)):
                text_color = 'white' if abs(corr_matrix[i, j]) > 0.6 else 'black'
                ax.text(j, i, f"{corr_matrix[i, j]:.2f}", ha='center', va='center', color=text_color, fontsize=8)
        ax.set_title("Matriz de Correlación Espectral (Pearson)")
        img_correlation = cls._fig_to_base64(fig)

        # 3. Scree Plot de PCA Global
        variance_ratio = results['pca']['varianza_explicada']
        cumulative_variance = results['pca']['varianza_acumulada']
        fig, ax = plt.subplots(figsize=(6, 4))
        components = np.arange(1, len(variance_ratio) + 1)
        ax.bar(components, variance_ratio, alpha=0.6, align='center', label='Varianza Individual', color='#2ecc71')
        ax.step(components, cumulative_variance, where='mid', label='Varianza Acumulada', color='#e74c3c')
        ax.set_xlabel('Componentes Principales')
        ax.set_ylabel('Proporción de Varianza Explicada')
        ax.set_title('Scree Plot - PCA Global')
        ax.set_xticks(components)
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='best')
        img_pca = cls._fig_to_base64(fig)

        # 4. Gráfico del Semivariograma Empírico y Ajuste Esférico
        lags = results['spatial_structure']['semivariograma']['lags']
        emp_semivar = results['spatial_structure']['semivariograma']['semivarianza_empirica']
        nugget = results['spatial_structure']['semivariograma']['nugget']
        sill = results['spatial_structure']['semivariograma']['sill']
        rango = results['spatial_structure']['semivariograma']['rango']

        fig, ax = plt.subplots(figsize=(6, 4))
        ax.scatter(lags, emp_semivar, color='#e67e22', label='Semivarianza Empírica', zorder=3)
        
        # Graficar modelo esférico ajustado
        h_grid = np.linspace(0, max(lags), 100)
        p_sill = sill - nugget
        fitted_y = np.where(
            h_grid <= rango,
            nugget + p_sill * (1.5 * (h_grid / rango) - 0.5 * (h_grid / rango) ** 3),
            nugget + p_sill
        )
        ax.plot(h_grid, fitted_y, color='#2c3e50', label='Modelo Esférico', linewidth=2)
        ax.axhline(y=sill, color='red', linestyle='--', label=f'Sill ({sill:.2f})')
        ax.axvline(x=rango, color='green', linestyle='--', label=f'Rango ({rango:.2f})')
        
        ax.set_xlabel('Distancia (Lags)')
        ax.set_ylabel('Semivarianza')
        ax.set_title('Semivariograma y Ajuste Esférico')
        ax.grid(True, linestyle='--', alpha=0.5)
        ax.legend(loc='best')
        img_variogram = cls._fig_to_base64(fig)

        # 5. Renderizado de la plantilla HTML mediante Jinja2
        html_template = Template(cls.HTML_TEMPLATE_STRING)
        rendered_html = html_template.render(
            results=results,
            img_resolution=img_resolution,
            img_correlation=img_correlation,
            img_pca=img_pca,
            img_variogram=img_variogram
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_html)

    @classmethod
    def generate_m2_report(cls, results, output_path):
        """Genera el reporte HTML de la Memoria 2 (Separabilidad y Aprendibilidad).

        Args:
            results (dict): Diccionario con los resultados de todos los análisis de M2.
            output_path (str): Ruta absoluta del archivo HTML a guardar.
        """
        import matplotlib.pyplot as plt
        import numpy as np

        # 1. Gráfico de t-SNE (Clases Reales vs Clusters Asignados)
        tsne_coords = np.array(results['tsne'])
        y_real = np.array(results['y_real'])
        cluster_labels = np.array(results['cluster_labels'])

        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(11, 4.5))

        # Subplot 1: Clases Reales
        unique_classes = sorted(list(set(y_real)))
        colors = plt.cm.get_cmap('tab10', len(unique_classes))
        for i, c_label in enumerate(unique_classes):
            mask = (y_real == c_label)
            ax1.scatter(tsne_coords[mask, 0], tsne_coords[mask, 1], label=c_label, color=colors(i), alpha=0.8, edgecolor='k', s=35)
        ax1.set_title("Espacio Latente (t-SNE) por Clase Real")
        ax1.set_xlabel("t-SNE 1")
        ax1.set_ylabel("t-SNE 2")
        ax1.grid(True, linestyle='--', alpha=0.5)
        ax1.legend(loc='best', fontsize=8)

        # Subplot 2: Clusters K-Means
        unique_clusters = sorted(list(set(cluster_labels)))
        colors_c = plt.cm.get_cmap('Accent', len(unique_clusters))
        for i, cluster in enumerate(unique_clusters):
            mask = (cluster_labels == cluster)
            ax2.scatter(tsne_coords[mask, 0], tsne_coords[mask, 1], label=f"Cluster {cluster}", color=colors_c(i), alpha=0.8, edgecolor='k', s=35)
        ax2.set_title("Espacio Latente (t-SNE) por Cluster K-Means")
        ax2.set_xlabel("t-SNE 1")
        ax2.set_ylabel("t-SNE 2")
        ax2.grid(True, linestyle='--', alpha=0.5)
        ax2.legend(loc='best', fontsize=8)

        fig.tight_layout()
        img_tsne = cls._fig_to_base64(fig)

        # 2. Gráfico de Optimización K-Means (Silueta y Davies-Bouldin)
        scores = results['clustering']['scores']
        ks = [s['k'] for s in scores]
        silhouettes = [s['silhouette'] for s in scores]
        db_scores = [s['davies_bouldin'] for s in scores]

        fig, ax1 = plt.subplots(figsize=(6, 3.5))

        color = '#2980b9'
        ax1.set_xlabel('Número de Clusters (K)')
        ax1.set_ylabel('Silhouette Score', color=color)
        line1 = ax1.plot(ks, silhouettes, color=color, marker='o', label='Silhouette', linewidth=2)
        ax1.tick_params(axis='y', labelcolor=color)

        ax2 = ax1.twinx()  
        color = '#e74c3c'
        ax2.set_ylabel('Davies-Bouldin Index', color=color)
        line2 = ax2.plot(ks, db_scores, color=color, marker='s', linestyle='--', label='Davies-Bouldin', linewidth=2)
        ax2.tick_params(axis='y', labelcolor=color)

        lines = line1 + line2
        labels = [l.get_label() for l in lines]
        ax1.legend(lines, labels, loc='best', fontsize=8)
        ax1.set_title('Optimización de Agrupamiento K-Means')
        ax1.grid(True, linestyle='--', alpha=0.5)
        fig.tight_layout()
        img_clustering = cls._fig_to_base64(fig)

        # 3. Heatmap de Correlación de Descriptores Relevantes (Top 12)
        mi_scores = results['mutual_info']
        top_features = [m['variable'] for m in mi_scores[:12]]
        
        columns = results['collinearity']['columns']
        corr_all = np.array(results['collinearity']['pearson'])
        
        indices = [columns.index(f) for f in top_features if f in columns]
        sub_corr = corr_all[np.ix_(indices, indices)]
        
        fig, ax = plt.subplots(figsize=(6.5, 5.5))
        cax = ax.imshow(sub_corr, cmap='coolwarm', vmin=-1.0, vmax=1.0)
        fig.colorbar(cax, ax=ax)
        
        ax.set_xticks(np.arange(len(indices)))
        ax.set_yticks(np.arange(len(indices)))
        top_labels = [columns[i] for i in indices]
        clean_labels = [l[:18] + '...' if len(l) > 20 else l for l in top_labels]
        ax.set_xticklabels(clean_labels, rotation=45, ha='right', fontsize=8)
        ax.set_yticklabels(clean_labels, fontsize=8)
        
        for i in range(len(indices)):
            for j in range(len(indices)):
                ax.text(j, i, f"{sub_corr[i, j]:.2f}", ha='center', va='center', 
                        color='white' if abs(sub_corr[i, j]) > 0.6 else 'black', fontsize=7)
                        
        ax.set_title("Correlación de los Descriptores más Relevantes (Top 12)")
        fig.tight_layout()
        img_correlation = cls._fig_to_base64(fig)

        # 4. Gráfico de Importancia (Mutual Information Top 12)
        variables = [m['variable'] for m in mi_scores[:12]]
        scores_mi = [m['mutual_info'] for m in mi_scores[:12]]
        
        fig, ax = plt.subplots(figsize=(5.5, 3.5))
        y_pos = np.arange(len(variables))
        ax.barh(y_pos, scores_mi, align='center', color='#2ecc71', edgecolor='black', alpha=0.7)
        ax.set_yticks(y_pos)
        clean_vars = [v[:18] + '...' if len(v) > 20 else v for v in variables]
        ax.set_yticklabels(clean_vars, fontsize=8)
        ax.invert_yaxis()
        ax.set_xlabel('Mutual Information Score')
        ax.set_title('Relevancia del Descriptor (Mutual Information)')
        ax.grid(True, linestyle='--', alpha=0.5)
        fig.tight_layout()
        img_mutual_info = cls._fig_to_base64(fig)

        # 5. Renderizado de la plantilla HTML mediante Jinja2
        html_template = Template(cls.HTML_TEMPLATE_STRING_M2)
        rendered_html = html_template.render(
            results=results,
            img_tsne=img_tsne,
            img_clustering=img_clustering,
            img_correlation=img_correlation,
            img_mutual_info=img_mutual_info
        )

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(rendered_html)

    # Plantilla HTML estática autocontenida para la Memoria 1
    HTML_TEMPLATE_STRING = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Reporte de Observabilidad Territorial - Memoria 1</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #2c3e50;
            background-color: #f8f9fa;
            margin: 0;
            padding: 30px;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            padding: 40px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border-radius: 8px;
        }
        h1, h2, h3 {
            color: #1e3a8a;
        }
        h1 {
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 15px;
            margin-top: 0;
        }
        h2 {
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 10px;
            margin-top: 30px;
        }
        .meta-box {
            background-color: #f1f5f9;
            border-left: 4px solid #3b82f6;
            padding: 15px 20px;
            margin-bottom: 30px;
            border-radius: 0 4px 4px 0;
        }
        .meta-box p {
            margin: 5px 0;
            font-size: 14px;
        }
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        .card {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 20px;
        }
        .toi-badge {
            display: inline-block;
            padding: 8px 16px;
            font-weight: bold;
            border-radius: 20px;
            font-size: 16px;
        }
        .toi-Excelente { background-color: #d1fae5; color: #065f46; }
        .toi-Buena { background-color: #dbeafe; color: #1e40af; }
        .toi-Aceptable { background-color: #fef3c7; color: #92400e; }
        .toi-Critica { background-color: #fee2e2; color: #991b1b; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 25px;
        }
        th, td {
            border: 1px solid #e2e8f0;
            padding: 12px;
            text-align: left;
            font-size: 14px;
        }
        th {
            background-color: #f8f9fa;
            color: #1e3a8a;
        }
        tr:nth-child(even) {
            background-color: #f8fafc;
        }
        .chart-img {
            max-width: 100%;
            height: auto;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            display: block;
            margin: 10px auto;
        }
        .footer {
            margin-top: 50px;
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
            text-align: center;
            font-size: 12px;
            color: #64748b;
        }
        @media print {
            body { background-color: #fff; padding: 0; }
            .container { box-shadow: none; padding: 0; max-width: 100%; }
            .chart-img { page-break-inside: avoid; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Diagnóstico de Observabilidad Territorial (DRT)</h1>
        <p style="font-size: 18px; color: #475569;">Reporte Técnico de Memoria 1 — Calidad Representacional de Datos</p>

        <div class="meta-box">
            <p><strong>Capa Ráster:</strong> {{ results.meta.raster_name }}</p>
            <p><strong>Capa Vectorial:</strong> {{ results.meta.vector_name }}</p>
            <p><strong>Campo de Clase Analizado:</strong> {{ results.meta.class_field }}</p>
            <p><strong>Fecha de Generación:</strong> {{ results.meta.timestamp }}</p>
        </div>

        <h2>1. Índice de Observabilidad Territorial (TOI)</h2>
        <div class="grid-2">
            <div class="card" style="text-align: center;">
                <p style="font-size: 14px; color: #64748b; text-transform: uppercase; margin-bottom: 5px;">Puntaje TOI Global</p>
                <p style="font-size: 48px; font-weight: bold; margin: 10px 0; color: #1e3a8a;">{{ "%.2f"|format(results.toi.toi) }} / 100</p>
                <span class="toi-badge toi-{{ results.toi.clasificacion }}">{{ results.toi.clasificacion }}</span>
            </div>
            <div class="card">
                <h3 style="margin-top: 0;">Desglose de Componentes</h3>
                <p><strong>Cobertura Territorial (20%):</strong> {{ "%.2f"|format(results.toi.sub_scores.cobertura) }}%</p>
                <p><strong>Resolución Observacional (25%):</strong> {{ "%.2f"|format(results.toi.sub_scores.resolucion) }}%</p>
                <p><strong>Complejidad Espectral (25%):</strong> {{ "%.2f"|format(results.toi.sub_scores.complejidad) }}%</p>
                <p><strong>Redundancia (15%):</strong> {{ "%.2f"|format(results.toi.sub_scores.redundancia) }}%</p>
                <p><strong>Estructura Espacial (15%):</strong> {{ "%.2f"|format(results.toi.sub_scores.estructura) }}%</p>
            </div>
        </div>

        <h2>2. Compatibilidad y Cobertura Espacial</h2>
        <div class="grid-2">
            <div class="card">
                <h3>Alineación de Sistemas</h3>
                <p><strong>CRS Ráster:</strong> {{ results.crs.raster_crs }}</p>
                <p><strong>CRS Vector:</strong> {{ results.crs.vector_crs }}</p>
                <p><strong>CRS Coinciden:</strong> {{ "Sí" if results.crs.match else "No" }}</p>
                <p><strong>Reproyección al Vuelo:</strong> {{ "Sí, vector proyectado al CRS del ráster" if results.crs.reprojected else "No requerida" }}</p>
            </div>
            <div class="card">
                <h3>Cobertura Geométrica</h3>
                <p><strong>Polígonos Totales:</strong> {{ results.coverage.total_polygons }}</p>
                <p><strong>Polígonos Cubiertos:</strong> {{ results.coverage.polygons_inside }}</p>
                <p><strong>Polígonos Fuera del Ráster:</strong> {{ results.coverage.polygons_outside }}</p>
                <p><strong>Porcentaje Cobertura Efectiva:</strong> {{ "%.2f"|format(results.coverage.coverage_ratio) }}%</p>
            </div>
        </div>

        <h2>3. Resolución Observacional</h2>
        <div class="grid-2">
            <div class="card">
                <h3>Relación de Escalas</h3>
                <p><strong>Área del Píxel Ráster:</strong> {{ "%.2f"|format(results.resolution.pixel_area_m2) }} m²</p>
                <p><strong>Área Promedio de Polígonos:</strong> {{ "%.2f"|format(results.resolution.polygon_area_mean) }} m²</p>
                <p><strong>Relación Promedio Píxel/Polígono:</strong> {{ "%.4f"|format(results.resolution.ratio_pixel_poly_mean) }}</p>
                <p><strong>Relación Mediana Píxel/Polígono:</strong> {{ "%.4f"|format(results.resolution.ratio_pixel_poly_median) }}</p>
            </div>
            <div class="card">
                <img class="chart-img" src="{{ img_resolution }}" alt="Gráfico de Resolución">
            </div>
        </div>

        <h2>4. Estadísticas Espectrales por Banda</h2>
        <table>
            <thead>
                <tr>
                    <th>Banda</th>
                    <th>Media</th>
                    <th>Std Dev</th>
                    <th>Varianza</th>
                    <th>Asimetría (Skewness)</th>
                    <th>Curtosis</th>
                    <th>Entropía (bits)</th>
                </tr>
            </thead>
            <tbody>
                {% for b in results.spectral_stats %}
                <tr>
                    <td>Banda {{ b.banda }}</td>
                    <td>{{ "%.2f"|format(b.media) }}</td>
                    <td>{{ "%.2f"|format(b.std) }}</td>
                    <td>{{ "%.2f"|format(b.varianza) }}</td>
                    <td>{{ "%.4f"|format(b.asimetria) }}</td>
                    <td>{{ "%.4f"|format(b.curtosis) }}</td>
                    <td>{{ "%.4f"|format(b.entropia) }}</td>
                </tr>
                {% endfor %}
            </tbody>
        </table>

        <h2>5. Redundancia Espectral y Dimensionalidad</h2>
        <div class="grid-2">
            <div class="card">
                <img class="chart-img" src="{{ img_correlation }}" alt="Heatmap de Correlación">
            </div>
            <div class="card">
                <img class="chart-img" src="{{ img_pca }}" alt="Scree Plot PCA">
                <p style="margin-top: 15px;"><strong>Dimensionalidad Efectiva:</strong> Se requieren <strong>{{ results.pca.effective_dimensionality }}</strong> componentes principales para explicar el 95% de la varianza total de la escena ráster.</p>
            </div>
        </div>

        <h2>6. Estructura y Autocorrelación Espacial</h2>
        <div class="grid-2">
            <div class="card">
                <h3>Métricas de Estructura</h3>
                <p><strong>Moran's I (Autocorrelación):</strong> {{ "%.4f"|format(results.spatial_structure.moran.moran_i) }}</p>
                <p><strong>Esperanza Matemática E(I):</strong> {{ "%.4f"|format(results.spatial_structure.moran.esperanza) }}</p>
                <p><strong>Nugget (Efecto Pepita):</strong> {{ "%.4f"|format(results.spatial_structure.semivariograma.nugget) }}</p>
                <p><strong>Sill (Meseta):</strong> {{ "%.4f"|format(results.spatial_structure.semivariograma.sill) }}</p>
                <p><strong>Rango (Range):</strong> {{ "%.2f"|format(results.spatial_structure.semivariograma.rango) }} metros</p>
            </div>
            <div class="card">
                <img class="chart-img" src="{{ img_variogram }}" alt="Variograma Ajustado">
            </div>
        </div>

        <div class="footer">
            <p>Diagnóstico de Representación Territorial (DRT) — Plugin para QGIS</p>
            <p>Desarrollado para la validación científica de observabilidad y representatividad territorial.</p>
        </div>
    </div>
</body>
</html>
"""

    HTML_TEMPLATE_STRING_M2 = """<!DOCTYPE html>
<html lang="es">
<head>
    <meta charset="UTF-8">
    <title>Reporte de Separabilidad y Aprendibilidad - Memoria 2</title>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #2c3e50;
            background-color: #f8f9fa;
            margin: 0;
            padding: 30px;
        }
        .container {
            max-width: 1100px;
            margin: 0 auto;
            background: #ffffff;
            padding: 40px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.05);
            border-radius: 8px;
        }
        h1, h2, h3 {
            color: #1e3a8a;
        }
        h1 {
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 15px;
            margin-top: 0;
        }
        h2 {
            border-bottom: 1px solid #e2e8f0;
            padding-bottom: 10px;
            margin-top: 30px;
        }
        .meta-box {
            background-color: #f1f5f9;
            border-left: 4px solid #3b82f6;
            padding: 15px 20px;
            margin-bottom: 30px;
            border-radius: 0 4px 4px 0;
        }
        .meta-box p {
            margin: 5px 0;
            font-size: 14px;
        }
        .grid-2 {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 30px;
            margin-bottom: 30px;
        }
        .card {
            background: #fff;
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 20px;
        }
        .tli-badge {
            display: inline-block;
            padding: 8px 16px;
            font-weight: bold;
            border-radius: 20px;
            font-size: 16px;
        }
        .tli-Excelente { background-color: #d1fae5; color: #065f46; }
        .tli-Buena { background-color: #dbeafe; color: #1e40af; }
        .tli-Moderada { background-color: #fef3c7; color: #92400e; }
        .tli-Baja { background-color: #fee2e2; color: #991b1b; }
        
        table {
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 25px;
        }
        th, td {
            border: 1px solid #e2e8f0;
            padding: 10px 12px;
            text-align: left;
            font-size: 13px;
        }
        th {
            background-color: #f8f9fa;
            color: #1e3a8a;
        }
        tr:nth-child(even) {
            background-color: #f8fafc;
        }
        .chart-img {
            max-width: 100%;
            height: auto;
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            display: block;
            margin: 10px auto;
        }
        .footer {
            margin-top: 50px;
            border-top: 1px solid #e2e8f0;
            padding-top: 20px;
            text-align: center;
            font-size: 12px;
            color: #64748b;
        }
        @media print {
            body { background-color: #fff; padding: 0; }
            .container { box-shadow: none; padding: 0; max-width: 100%; }
            .chart-img { page-break-inside: avoid; }
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Diagnóstico de Representación Territorial (DRT)</h1>
        <p style="font-size: 18px; color: #475569;">Reporte Técnico de Memoria 2 — Separabilidad y Aprendibilidad Territorial</p>
 
        <div class="meta-box">
            <p><strong>Capa Ráster:</strong> {{ results.meta.raster_name }}</p>
            <p><strong>Capa Vectorial:</strong> {{ results.meta.vector_name }}</p>
            <p><strong>Campo de Clase Analizado:</strong> {{ results.meta.class_field }}</p>
            <p><strong>Fecha de Generación:</strong> {{ results.meta.timestamp }}</p>
        </div>
 
        <h2>1. Territorial Learnability Index (TLI)</h2>
        <div class="grid-2">
            <div class="card" style="text-align: center;">
                <p style="font-size: 14px; color: #64748b; text-transform: uppercase; margin-bottom: 5px;">Puntaje TLI Global</p>
                <p style="font-size: 48px; font-weight: bold; margin: 10px 0; color: #1e3a8a;">{{ "%.2f"|format(results.tli.tli) }} / 100</p>
                {% set class_prefix = results.tli.clasificacion.split(' ')[0] %}
                <span class="tli-badge tli-{{ class_prefix }}">{{ results.tli.clasificacion }}</span>
            </div>
            <div class="card">
                <h3 style="margin-top: 0;">Componentes del Índice</h3>
                <p><strong>Separabilidad Multivariante (40%):</strong> {{ "%.2f"|format(results.tli.mahalanobis_score) }}%</p>
                <p><strong>Pureza Temática (35%):</strong> {{ "%.2f"|format(results.tli.purity_score) }}%</p>
                <p><strong>Coherencia de Clústeres (25%):</strong> {{ "%.2f"|format(results.tli.silhouette_score_norm) }}%</p>
                <p><strong>Penalización por Redundancia:</strong> {{ "%.2f"|format(results.tli.redundancy_penalty) }} puntos</p>
            </div>
        </div>
 
        <h2>2. Diagnóstico del Feature Space (Variables y PCA)</h2>
        <div class="grid-2">
            <div class="card">
                <img class="chart-img" src="{{ img_mutual_info }}" alt="Importancia de Descriptores">
            </div>
            <div class="card">
                <h3>Importancia de Variables (Mutual Information)</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Descriptor</th>
                            <th>Mutual Information Score</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for m in results.mutual_info[:6] %}
                        <tr>
                            <td>{{ m.variable }}</td>
                            <td>{{ "%.4f"|format(m.mutual_info) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                <p><strong>Dimensionalidad Intrínseca (PCA 95%):</strong> Se requieren <strong>{{ results.pca.dimensionalidad_intrinseca }}</strong> componentes principales ortogonales para capturar el 95% de la varianza del espacio de variables.</p>
            </div>
        </div>
 
        <h2>3. Colinealidad y Redundancia de Descriptores</h2>
        <div class="grid-2">
            <div class="card">
                <img class="chart-img" src="{{ img_correlation }}" alt="Heatmap de Correlación">
            </div>
            <div class="card">
                <h3>Análisis de Colinealidad</h3>
                <p><strong>Total de Descriptores Numéricos:</strong> {{ results.collinearity.columns|length }}</p>
                <p><strong>Pares de Variables Redundantes (r > 0.85):</strong> {{ results.collinearity.redundant_pairs|length }}</p>
                
                {% if results.collinearity.redundant_pairs|length > 0 %}
                <div style="max-height: 200px; overflow-y: auto;">
                    <table>
                        <thead>
                            <tr>
                                <th>Variable 1</th>
                                <th>Variable 2</th>
                                <th>Corr (r)</th>
                            </tr>
                        </thead>
                        <tbody>
                            {% for pair in results.collinearity.redundant_pairs[:8] %}
                            <tr>
                                <td>{{ pair.var1[:20] }}</td>
                                <td>{{ pair.var2[:20] }}</td>
                                <td>{{ "%.3f"|format(pair.correlation) }}</td>
                            </tr>
                            {% endfor %}
                        </tbody>
                    </table>
                    {% if results.collinearity.redundant_pairs|length > 8 %}
                        <p style="font-size: 11px; color: #64748b;">* Mostrando las primeras 8 correlaciones más altas.</p>
                    {% endif %}
                </div>
                {% else %}
                    <p style="color: #065f46; font-weight: bold;">Excelente: No se detectan altos niveles de redundancia directa entre variables.</p>
                {% endif %}
            </div>
        </div>
 
        <h2>4. Clustering Exploratorio (K-Means)</h2>
        <div class="grid-2">
            <div class="card">
                <img class="chart-img" src="{{ img_clustering }}" alt="Gráfico de Optimización K-Means">
            </div>
            <div class="card">
                <h3>Métricas de Agrupación</h3>
                <p><strong>K Óptimo Seleccionado:</strong> {{ results.clustering.optimal_k }}</p>
                <p><strong>Silhouette Score del K Óptimo:</strong> {{ "%.4f"|format(results.clustering.optimal_silhouette) }}</p>
                
                <table>
                    <thead>
                        <tr>
                            <th>K</th>
                            <th>Silhouette Score</th>
                            <th>Davies-Bouldin Index</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for score in results.clustering.scores %}
                        <tr {% if score.k == results.clustering.optimal_k %}style="background-color: #f1f5f9; font-weight: bold;"{% endif %}>
                            <td>{{ score.k }}</td>
                            <td>{{ "%.4f"|format(score.silhouette) }}</td>
                            <td>{{ "%.4f"|format(score.davies_bouldin) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
 
        <h2>5. Visualización del Espacio Latente (t-SNE)</h2>
        <div class="card">
            <img class="chart-img" src="{{ img_tsne }}" alt="Proyección t-SNE">
            <p style="font-size: 12px; color: #64748b; text-align: center; margin-top: 10px;">La proyección t-SNE revela el agrupamiento del territorio basado en todas las variables extraídas. Un alto traslape entre colores de clases reales indica interferencia y mezcla espectral/textural.</p>
        </div>
 
        <h2>6. Correspondencia Clase-Cluster</h2>
        <div class="grid-2">
            <div class="card">
                <h3>Matriz de Confusión Clase vs. Cluster</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Clase \ Cluster</th>
                            {% for c in results.correspondence.clusters %}
                                <th>C{{ c }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for i in range(results.correspondence.classes|length) %}
                        <tr>
                            <td><strong>{{ results.correspondence.classes[i] }}</strong></td>
                            {% for j in range(results.correspondence.clusters|length) %}
                                <td>{{ results.correspondence.matrix[i][j] }}</td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
            <div class="card">
                <h3>Métricas de Pureza y Mezcla</h3>
                <p><strong>Pureza Global de Agrupamiento:</strong> {{ "%.2f"|format(results.correspondence.global_purity * 100) }}%</p>
                <table>
                    <thead>
                        <tr>
                            <th>Clase Real</th>
                            <th>Pureza del Cluster</th>
                            <th>Entropía de Mezcla</th>
                        </tr>
                    </thead>
                    <tbody>
                        {% for cls in results.correspondence.classes %}
                        <tr>
                            <td>{{ cls }}</td>
                            <td>{{ "%.2f"|format(results.correspondence.purities[cls] * 100) }}%</td>
                            <td>{{ "%.4f"|format(results.correspondence.entropies[cls]) }}</td>
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
 
        <h2>7. Solapamiento Interclase (Distancias Estadísticas)</h2>
        <div class="grid-2">
            <div class="card">
                <h3>Distancia de Mahalanobis</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Clase</th>
                            {% for cls in results.distances.classes %}
                                <th>{{ cls[:8] }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for i in range(results.distances.classes|length) %}
                        <tr>
                            <td><strong>{{ results.distances.classes[i][:12] }}</strong></td>
                            {% for j in range(results.distances.classes|length) %}
                                <td>
                                    {% if i == j %}
                                        0.00
                                    {% else %}
                                        {{ "%.2f"|format(results.distances.mahalanobis[i][j]) }}
                                    {% endif %}
                                </td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
                <p style="font-size: 11px; color: #64748b;">* Calculado sobre el espacio ortogonal proyectado de PCA para evitar indeterminación numérica.</p>
            </div>
            <div class="card">
                <h3>Distancia de Bhattacharyya</h3>
                <table>
                    <thead>
                        <tr>
                            <th>Clase</th>
                            {% for cls in results.distances.classes %}
                                <th>{{ cls[:8] }}</th>
                            {% endfor %}
                        </tr>
                    </thead>
                    <tbody>
                        {% for i in range(results.distances.classes|length) %}
                        <tr>
                            <td><strong>{{ results.distances.classes[i][:12] }}</strong></td>
                            {% for j in range(results.distances.classes|length) %}
                                <td>
                                    {% if i == j %}
                                        0.00
                                    {% else %}
                                        {{ "%.3f"|format(results.distances.bhattacharyya[i][j]) }}
                                    {% endif %}
                                </td>
                            {% endfor %}
                        </tr>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>
 
        <div class="footer">
            <p>Diagnóstico de Representación Territorial (DRT) — Plugin para QGIS</p>
            <p>Desarrollado para la validación científica de separabilidad y aprendibilidad territorial.</p>
        </div>
    </div>
</body>
</html>
"""

