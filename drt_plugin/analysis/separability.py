# -*- coding: utf-8 -*-
"""
Módulo para el diagnóstico de separabilidad y aprendibilidad del espacio de descriptores (Memoria 2).
"""

import numpy as np
import pandas as pd
from scipy import stats
from sklearn.preprocessing import StandardScaler
from sklearn.decomposition import PCA
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, davies_bouldin_score
from sklearn.manifold import TSNE
from sklearn.feature_selection import mutual_info_classif

class SeparabilityDiagnostics:
    """Realiza análisis multidimensionales de colinealidad, clustering, proyección 2D y separabilidad."""

    def __init__(self, df_features):
        """Inicializa con el DataFrame de descriptores del Objeto Territorial.

        Args:
            df_features (pd.DataFrame): Tabla de descriptores generada en la Fase 3.
        """
        self.df = df_features.copy()
        
        # Separar identificadores y clases de las variables numéricas
        self.meta_cols = ['objeto_id', 'clase']
        self.feature_cols = [col for col in self.df.columns if col not in self.meta_cols]
        
        # Eliminar columnas con desviación estándar igual a cero (sin variación)
        stds = self.df[self.feature_cols].std()
        self.feature_cols = [col for col in self.feature_cols if stds[col] > 0]
        
        self.X_raw = self.df[self.feature_cols].values
        self.y_label = self.df['clase'].values
        
        # Estandarizar descriptores
        self.scaler = StandardScaler()
        self.X_scaled = self.scaler.fit_transform(self.X_raw)

    def analyze_collinearity(self):
        """Identifica colinealidad y variables redundantes en el espacio de descriptores.

        Returns:
            dict: Matriz de correlación y lista de variables con alta colinealidad.
        """
        # Calcular matriz de correlación
        corr_matrix = pd.DataFrame(self.X_raw, columns=self.feature_cols).corr(method='pearson')
        
        # Encontrar pares de alta correlación (> 0.85)
        redundant_pairs = []
        visited = set()
        for col_a in corr_matrix.columns:
            for col_b in corr_matrix.columns:
                if col_a != col_b and (col_b, col_a) not in visited:
                    r = corr_matrix.loc[col_a, col_b]
                    if abs(r) > 0.85:
                        redundant_pairs.append({
                            'var1': col_a,
                            'var2': col_b,
                            'correlation': float(r)
                        })
                        visited.add((col_a, col_b))

        return {
            'pearson': corr_matrix.values.tolist(),
            'columns': self.feature_cols,
            'redundant_pairs': redundant_pairs
        }

    def analyze_pca(self):
        """Realiza un PCA sobre los descriptores para evaluar varianza explicada y dimensionalidad.

        Returns:
            dict: Resultados del análisis de componentes principales.
        """
        pca = PCA()
        pca.fit(self.X_scaled)
        
        explained_var = pca.explained_variance_ratio_.tolist()
        cum_var = np.cumsum(pca.explained_variance_ratio_).tolist()
        
        # Intrinsic dimensionality (95% varianza explicada)
        intrinsic_dim = int(np.where(np.array(cum_var) >= 0.95)[0][0]) + 1
        
        # Cargas de los primeros 3 componentes principales
        loadings = pca.components_[:3].T
        loadings_dict = {}
        for idx, col in enumerate(self.feature_cols):
            loadings_dict[col] = loadings[idx].tolist() if idx < len(loadings) else [0.0, 0.0, 0.0]

        return {
            'varianza_explicada': explained_var,
            'varianza_acumulada': cum_var,
            'dimensionalidad_intrinseca': intrinsic_dim,
            'loadings': loadings_dict
        }

    def analyze_mutual_information(self):
        """Calcula la importancia (Mutual Information) de cada descriptor respecto a la clase real.

        Returns:
            list: Lista de diccionarios con el nombre de la variable y su puntuación de MI.
        """
        # Calcular Mutual Information
        mi_scores = mutual_info_classif(self.X_scaled, self.y_label, random_state=42)
        
        mi_list = []
        for idx, col in enumerate(self.feature_cols):
            mi_list.append({
                'variable': col,
                'mutual_info': float(mi_scores[idx])
            })
            
        # Ordenar de mayor a menor importancia
        mi_list = sorted(mi_list, key=lambda x: x['mutual_info'], reverse=True)
        return mi_list

    def analyze_clustering(self):
        """Aplica K-Means variando K entre 2 y 8, y selecciona la solución óptima.

        Returns:
            dict: Estadísticas de agrupamiento y etiquetas óptimas asignadas.
        """
        k_values = list(range(2, min(9, len(self.df))))
        clustering_results = []
        
        best_k = 2
        best_silhouette = -1.0
        best_labels = None
        
        for k in k_values:
            kmeans = KMeans(n_clusters=k, random_state=42, n_init=10)
            labels = kmeans.fit_predict(self.X_scaled)
            
            sil = float(silhouette_score(self.X_scaled, labels))
            db = float(davies_bouldin_score(self.X_scaled, labels))
            inertia = float(kmeans.inertia_)
            
            clustering_results.append({
                'k': k,
                'silhouette': sil,
                'davies_bouldin': db,
                'inertia': inertia
            })
            
            # Maximizar Silhouette Score para el K óptimo
            if sil > best_silhouette:
                best_silhouette = sil
                best_k = k
                best_labels = labels

        return {
            'scores': clustering_results,
            'optimal_k': best_k,
            'optimal_silhouette': best_silhouette,
            'labels': best_labels.tolist() if best_labels is not None else []
        }

    def run_tsne(self):
        """Proyecta el espacio de descriptores a 2D usando t-SNE.

        Returns:
            list: Coordenadas 2D proyectadas.
        """
        # Usar perplejidad adaptativa al tamaño del dataset
        perplexity = min(30.0, max(2.0, len(self.df) / 3.0))
        tsne = TSNE(n_components=2, perplexity=perplexity, random_state=42, max_iter=1000)
        X_2d = tsne.fit_transform(self.X_scaled)
        return X_2d.tolist()

    def analyze_correspondence(self, cluster_labels):
        """Genera matriz de confusión entre clases reales y clusters, y calcula entropías de mezcla.

        Returns:
            dict: Matrices y puntuaciones de correspondencia/pureza.
        """
        unique_classes = sorted(list(set(self.y_label)))
        n_clusters = len(set(cluster_labels))
        
        # Crear tabla cruzada (Clase vs Cluster)
        cross_tab = pd.crosstab(self.df['clase'], pd.Series(cluster_labels, name='cluster'))
        
        # Calcular pureza por clase y entropía
        entropies = {}
        purities = {}
        
        for cls in unique_classes:
            if cls in cross_tab.index:
                row_counts = cross_tab.loc[cls].values
                total_cls = row_counts.sum()
                if total_cls > 0:
                    probs = row_counts / total_cls
                    probs_clean = probs[probs > 0]
                    # Entropía de Shannon (base e) de la mezcla
                    entropies[cls] = float(-np.sum(probs_clean * np.log(probs_clean)))
                    purities[cls] = float(np.max(row_counts) / total_cls)
                else:
                    entropies[cls] = 0.0
                    purities[cls] = 0.0
            else:
                entropies[cls] = 0.0
                purities[cls] = 0.0

        # Calcular Pureza Global
        # Sumatoria de máximos por columna dividido el total
        max_sums = 0
        for col in cross_tab.columns:
            max_sums += cross_tab[col].max()
        global_purity = float(max_sums / len(self.df))

        return {
            'matrix': cross_tab.values.tolist(),
            'classes': unique_classes,
            'clusters': list(cross_tab.columns),
            'entropies': entropies,
            'purities': purities,
            'global_purity': global_purity
        }

    def calculate_interclass_distances(self, intrinsic_dim):
        """Calcula distancias multivariadas de Mahalanobis y Bhattacharyya en espacio PCA reducido.

        Args:
            intrinsic_dim (int): Número de componentes principales a conservar (evita matrices singulares).

        Returns:
            dict: Matrices de distancias interclase de Mahalanobis y Bhattacharyya.
        """
        # Reducir dimensionalidad a componentes ortogonales principales
        pca = PCA(n_components=min(intrinsic_dim, self.X_scaled.shape[1]))
        X_pca = pca.fit_transform(self.X_scaled)
        
        unique_classes = sorted(list(set(self.y_label)))
        n_classes = len(unique_classes)
        
        mahalanobis_matrix = np.zeros((n_classes, n_classes))
        bhattacharyya_matrix = np.zeros((n_classes, n_classes))
        
        # Agrupar datos PCA por clase
        class_groups = {}
        for idx, cls in enumerate(unique_classes):
            mask = (self.y_label == cls)
            class_groups[cls] = X_pca[mask]

        # Calcular distancias por pares
        for i in range(n_classes):
            cls1 = unique_classes[i]
            data1 = class_groups[cls1]
            n1 = len(data1)
            mean1 = np.mean(data1, axis=0)
            cov1 = np.cov(data1, rowvar=False) if n1 > 1 else np.zeros((X_pca.shape[1], X_pca.shape[1]))
            # Regularización Ridge para covarianza
            cov1 += 1e-4 * np.eye(X_pca.shape[1])
            
            for j in range(i, n_classes):
                cls2 = unique_classes[j]
                if i == j:
                    mahalanobis_matrix[i, j] = 0.0
                    bhattacharyya_matrix[i, j] = 0.0
                    continue
                    
                data2 = class_groups[cls2]
                n2 = len(data2)
                mean2 = np.mean(data2, axis=0)
                cov2 = np.cov(data2, rowvar=False) if n2 > 1 else np.zeros((X_pca.shape[1], X_pca.shape[1]))
                cov2 += 1e-4 * np.eye(X_pca.shape[1])
                
                # Covarianza combinada (pooled)
                cov_pooled = (n1 * cov1 + n2 * cov2) / (n1 + n2)
                cov_pooled_inv = np.linalg.inv(cov_pooled)
                
                # Diferencia de medias
                diff = mean1 - mean2
                
                # 1. Distancia de Mahalanobis
                dist_m = np.sqrt(np.dot(np.dot(diff, cov_pooled_inv), diff))
                mahalanobis_matrix[i, j] = float(dist_m)
                mahalanobis_matrix[j, i] = float(dist_m)
                
                # 2. Distancia de Bhattacharyya
                cov_mean = 0.5 * (cov1 + cov2)
                # Determinantes de forma segura para evitar underflow/overflow
                sign_m, logdet_m = np.linalg.slogdet(cov_mean)
                sign1, logdet1 = np.linalg.slogdet(cov1)
                sign2, logdet2 = np.linalg.slogdet(cov2)
                
                term1 = 0.125 * np.dot(np.dot(diff, np.linalg.inv(cov_mean)), diff)
                term2 = 0.5 * (logdet_m - 0.5 * (logdet1 + logdet2))
                dist_b = term1 + term2
                
                # Evitar valores negativos numéricos pequeños
                dist_b = max(0.0, float(dist_b))
                bhattacharyya_matrix[i, j] = dist_b
                bhattacharyya_matrix[j, i] = dist_b

        return {
            'classes': unique_classes,
            'mahalanobis': mahalanobis_matrix.tolist(),
            'bhattacharyya': bhattacharyya_matrix.tolist()
        }

    @staticmethod
    def calculate_tli(mean_mahalanobis, global_purity, optimal_silhouette, redundant_ratio):
        """Calcula el índice sintético Territorial Learnability Index (TLI).

        Alinea el índice a una escala de 0 a 100.
        """
        # 1. Componente de Distancia de Mahalanobis (Sigmoide normalizada)
        # Una distancia promedio de 4.0 representa un excelente separador
        mahalanobis_score = 100.0 * (1.0 - np.exp(-mean_mahalanobis / 4.0))
        
        # 2. Componente de Pureza Global (0 a 100)
        purity_score = global_purity * 100.0
        
        # 3. Componente de Coherencia de Agrupamiento (Silhouette 0-1 normalizado)
        silhouette_score_norm = max(0.0, optimal_silhouette) * 100.0
        
        # 4. Penalización por redundancia de variables (si más del 50% de las variables son redundantes)
        redundancy_penalty = max(0.0, (redundant_ratio - 0.3) * 20.0) # Penaliza hasta 20 puntos si hay alta redundancia
        
        # Combinación lineal ponderada
        tli_raw = 0.40 * mahalanobis_score + 0.35 * purity_score + 0.25 * silhouette_score_norm - redundancy_penalty
        tli = float(np.clip(tli_raw, 0.0, 100.0))
        
        # Clasificación
        if tli >= 80.0:
            classification = "Excelente Separabilidad (Alta Aprendibilidad)"
        elif tli >= 60.0:
            classification = "Buena Separabilidad"
        elif tli >= 40.0:
            classification = "Separabilidad Moderada"
        else:
            classification = "Baja Separabilidad (Alta Interferencia Espectral)"
            
        return {
            'tli': tli,
            'clasificacion': classification,
            'mahalanobis_score': float(mahalanobis_score),
            'purity_score': float(purity_score),
            'silhouette_score_norm': float(silhouette_score_norm),
            'redundancy_penalty': float(redundancy_penalty)
        }
