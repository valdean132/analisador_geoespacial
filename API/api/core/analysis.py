import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import zipfile
import os
import fiona
import time

class GeoAnalyzer:
    def __init__(self, pasta_kmz: str, arquivo_excel_path: str, raio_km: float, coluna_coordenadas: str, coluna_velocidade):
        self.pasta_kmz = pasta_kmz
        self.arquivo_excel_path = arquivo_excel_path
        self.raio_km = raio_km
        self.RAIO_PROXIMIDADE_METROS = float(raio_km) * 1000

        # --- ATRIBUTOS DE RESULTADO ---
        self.df_final = None
        self.resumo = None
        
        # Constantes
        separa_coordenadas = coluna_coordenadas.split(',', 2)
        self.CRS_GEOGRAFICO = "EPSG:4326"
        self.CRS_PROJETADO = "EPSG:5880"
        self.COLUNA_LATITUDE = 'LATITUDE'
        self.COLUNA_LONGITUDE = 'LONGITUDE'
        self.COLUNA_COORDENADAS = 'COORDENADAS'
        
        if len(separa_coordenadas) == 2:
            self.COLUNA_LATITUDE = separa_coordenadas[0].strip()
            self.COLUNA_LONGITUDE = separa_coordenadas[1].strip()
        else:
            self.COLUNA_COORDENADAS = coluna_coordenadas
            
        
        self.COLUNA_VELOCIDADE = coluna_velocidade
        self.COLUNA_NOME_MANCHA = 'Name'


    def run_analysis(self):
        """
        Gerador que executa a análise passo a passo e produz (yields)
        atualizações de progresso.
        """
        try:
            # --- Etapa 1: Carregar polígonos ---
            yield 5, "Carregando arquivos KMZ..."
            arquivos_kmz = [os.path.join(self.pasta_kmz, f) for f in os.listdir(self.pasta_kmz) if f.lower().endswith('.kmz')]
            if not arquivos_kmz:
                raise ValueError(f"Nenhum arquivo .kmz encontrado em '{self.pasta_kmz}'")

            lista_poligonos_gdfs = []
            for i, kmz_file_path in enumerate(arquivos_kmz):
                # Usando um método auxiliar para manter o código limpo
                gdf_poligonos = self._extrair_poligonos(kmz_file_path)
                if gdf_poligonos is not None:
                    gdf_poligonos['Mancha'] = os.path.basename(kmz_file_path).split('.')[0]
                    lista_poligonos_gdfs.append(gdf_poligonos)
                yield 10 + int(20 * (i + 1) / len(arquivos_kmz)), f"Processando KMZ {i + 1}/{len(arquivos_kmz)}"

            if not lista_poligonos_gdfs:
                raise ValueError("Nenhum polígono válido foi carregado dos arquivos KMZ.")
            
            gdf_manchas_global = gpd.GeoDataFrame(pd.concat(lista_poligonos_gdfs, ignore_index=True), crs=self.CRS_GEOGRAFICO)
            if self.COLUNA_NOME_MANCHA not in gdf_manchas_global.columns:
                gdf_manchas_global[self.COLUNA_NOME_MANCHA] = 'Nome não encontrado'
            else:
                # gdf_manchas_global[self.COLUNA_NOME_MANCHA].fillna('Nome não encontrado', inplace=True)
                gdf_manchas_global[self.COLUNA_NOME_MANCHA] = gdf_manchas_global[self.COLUNA_NOME_MANCHA].fillna('Nome não encontrado')
            
            # --- Etapa 2 & 3: Carregar e processar pontos ---
            yield 35, "Lendo e validando arquivo de pontos..."
            df_pontos = pd.read_excel(self.arquivo_excel_path)
            # ... (Lógica de validação e criação de geometria idêntica à anterior) ...
            modo_coordenadas = self._validar_colunas_pontos(df_pontos)
            df_pontos['geometry'] = df_pontos.apply(lambda row: self._criar_ponto(row, modo_coordenadas), axis=1)
            invalidos_mask = df_pontos['geometry'].isna()

            # --- Etapa 4, 5, 6: Análise Espacial ---
            df_validos = df_pontos[~invalidos_mask]
            if not df_validos.empty:
                gdf_pontos = gpd.GeoDataFrame(df_validos, geometry='geometry', crs=self.CRS_GEOGRAFICO)
                if self.COLUNA_VELOCIDADE in gdf_pontos.columns:
                    gdf_pontos['velocidade_num'] = pd.to_numeric(gdf_pontos[self.COLUNA_VELOCIDADE].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0)
                else:
                    gdf_pontos['velocidade_num'] = 0

                yield 50, "Analisando pontos DENTRO das manchas..."
                # ... (Lógica sjoin e agregação para 'dentro') ...
                gdf_dentro_bruto = gpd.sjoin(gdf_pontos, gdf_manchas_global, how="inner", predicate="within")
                gdf_dentro_agregado = self._aggregate_results(gdf_dentro_bruto, 'dentro', gdf_pontos)

                yield 70, "Analisando pontos PRÓXIMOS às manchas..."
                # ... (Lógica sjoin_nearest e agregação para 'próximo') ...
                indices_encontrados = gdf_dentro_agregado.index
                gdf_pontos_fora = gdf_pontos.drop(indices_encontrados)
                gdf_proximos_agregado = pd.DataFrame()
                if not gdf_pontos_fora.empty and self.RAIO_PROXIMIDADE_METROS > 0:
                    gdf_pontos_proj = gdf_pontos_fora.to_crs(self.CRS_PROJETADO)
                    gdf_manchas_proj = gdf_manchas_global.to_crs(self.CRS_PROJETADO)
                    gdf_proximos_bruto = gpd.sjoin_nearest(gdf_pontos_proj, gdf_manchas_proj, max_distance=self.RAIO_PROXIMIDADE_METROS, how="inner")
                    if not gdf_proximos_bruto.empty:
                        yield 85, "Agregando resultados de proximidade..."
                        # ... cálculo de distância ...
                        nearest_polygons = gdf_manchas_proj.loc[gdf_proximos_bruto['index_right'], 'geometry']
                        aligned_polygons = gpd.GeoSeries(nearest_polygons.values, index=gdf_proximos_bruto.index, crs=self.CRS_PROJETADO)
                        gdf_proximos_bruto['Distância (metros)'] = gdf_proximos_bruto.geometry.distance(aligned_polygons)
                        gdf_proximos_agregado = self._aggregate_results(gdf_proximos_bruto, 'proximo', gdf_pontos)

                resultados_geo = pd.concat([gdf_dentro_agregado, gdf_proximos_agregado]).rename(columns={self.COLUNA_NOME_MANCHA: 'Nome da Mancha'})
            else:
                resultados_geo = pd.DataFrame()

            # --- Etapa 7: Consolidar ---
            yield 95, "Montando relatório final..."
            df_final = df_pontos.merge(resultados_geo, left_index=True, right_index=True, how="left")
            df_final.loc[invalidos_mask, 'Status Viabilidade'] = 'Coordenada Inválida'
            df_final.fillna({'Status Viabilidade': 'Inviável'}, inplace=True)
            
            # df_final[['Mancha', 'Nome da Mancha']] = df_final[['Mancha', 'Nome da Mancha']].fillna('---')
            # Preenche 'NaN's nas colunas de Mancha, mesmo que elas não existam
            df_final.fillna({'Mancha': '---', 'Nome da Mancha': '---'}, inplace=True)
            
            df_final = df_final.drop(columns=['geometry'], errors='ignore')
            
            resumo = df_final['Status Viabilidade'].value_counts().to_dict()
            
            # Antes:
            # yield 100, "Análise Concluída!"
            # return df_final, resumo
        
            # Agora fica assim:

            # Salva os resultados nos atributos da instância
            self.df_final = df_final
            self.resumo = resumo

            yield 100, "Análise Concluída!"

        except Exception as e:
            # Em caso de erro, produz uma mensagem de erro
            yield -1, str(e)
            # return None, None

    # --- Métodos Auxiliares da Classe ---
    def _extrair_poligonos(self, arquivo_kmz):
        basename = os.path.basename(arquivo_kmz).split('.')[0]
        temp_dir = os.path.join(self.pasta_kmz, "temp", basename)
        os.makedirs(temp_dir, exist_ok=True)
        caminho_kml = next((os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.lower().endswith('.kml')), None)
        if not caminho_kml:
            try:
                with zipfile.ZipFile(arquivo_kmz, 'r') as kmz:
                    kml_filename = next((f for f in kmz.namelist() if f.lower().endswith('.kml')), None)
                    if not kml_filename: return None
                    print(f"⚠️  Extraindo: '{os.path.basename(arquivo_kmz)}'")
                    caminho_kml = kmz.extract(kml_filename, path=temp_dir)
            except Exception as e:
                print(f"❌ Erro ao extrair '{arquivo_kmz}': {e}")
                return None
        try:
            with fiona.Env():
                camadas = fiona.listlayers(caminho_kml)
            lista_de_gdfs = []
            for camada in camadas:
                try:
                    gdf_camada = gpd.read_file(caminho_kml, driver='KML', layer=camada)
                    gdf_camada = gdf_camada[gdf_camada.geometry.type.isin(['Polygon', 'MultiPolygon']) & gdf_camada.geometry.is_valid]
                    if not gdf_camada.empty:
                        lista_de_gdfs.append(gdf_camada)
                except Exception:
                    continue
            if not lista_de_gdfs: return None
            return gpd.GeoDataFrame(pd.concat(lista_de_gdfs, ignore_index=True), crs=self.CRS_GEOGRAFICO)
        except Exception as e:
            print(f"❌ Erro ao ler KML '{caminho_kml}': {e}")
            return None
    
    def _criar_ponto(self, row, mode):
        """
        Cria um objeto Point a partir de uma linha do DataFrame, com validação rigorosa.
        Retorna None se os dados forem inválidos (vazios, 0 ou mal formatados).
        
        Args:
            row (pd.Series): A linha do DataFrame.
            mode (str): O modo de operação ('latlon' ou 'coords').
        """
        if mode == 'latlon':
            try:
                # Pega os valores
                lon = row[self.COLUNA_LONGITUDE]
                lat = row[self.COLUNA_LATITUDE]
                
                # VALIDAÇÃO: Verifica se são nulos ou 0
                if pd.isna(lon) or pd.isna(lat) or lon == 0 or lat == 0:
                    return None
                
                # Converte para float e cria o ponto
                return Point(float(lon), float(lat))
            except (ValueError, TypeError):
                return None # Retorna None se a conversão para float falhar

        elif mode == 'coords':
            try:
                # Pega o valor
                coords_str = row[self.COLUNA_COORDENADAS]
                
                # VALIDAÇÃO: Verifica se é nulo, 0 ou uma string '0'
                if pd.isna(coords_str) or coords_str == 0 or str(coords_str).strip() == '0':
                    return None
                
                # Processa a string de coordenadas
                coords = str(coords_str).replace(" ", "").split(',')
                if len(coords) == 2:
                    lat, lon = map(float, coords)
                    # VALIDAÇÃO extra para o caso de "0,0" na string
                    if lat == 0 or lon == 0:
                        return None
                    return Point(lon, lat)
            except (ValueError, TypeError, IndexError):
                return None # Retorna None se o formato for inválido
        
        return None

    def _validar_colunas_pontos(self, df):
        if self.COLUNA_LATITUDE in df.columns and self.COLUNA_LONGITUDE in df.columns:
            return 'latlon'
        elif self.COLUNA_COORDENADAS in df.columns:
            return 'coords'
        else:
            raise ValueError(f"Nenhuma coluna de coordenada encontrada.")
    
    def _aggregate_results(self, df_bruto, mode, gdf_pontos):
        if df_bruto.empty:
            return pd.DataFrame()
        if mode == 'dentro':
            df_bruto['Status Viabilidade'] = df_bruto.apply(
                lambda row: 'Viabilidade Expressa' if gdf_pontos.loc[row.name]['velocidade_num'] <= 500 else 'Verificar PTP', axis=1)
            df_bruto['Distância (metros)'] = 0
            agg_rules = {'Distância (metros)': 'first'}
        else: # modo 'proximo'
            df_bruto['Status Viabilidade'] = 'Próximo à mancha'
            agg_rules = {'Distância (metros)': 'min'}
        
        agg_rules.update({
            'Mancha': lambda x: ', '.join(x.unique()),
            self.COLUNA_NOME_MANCHA: lambda x: ', '.join(x.unique()),
            'Status Viabilidade': 'first'
        })
        
        df_agregado = df_bruto.groupby(df_bruto.index).agg(agg_rules)
        if 'Distância (metros)' in df_agregado.columns:
            df_agregado['Distância (metros)'] = round(df_agregado['Distância (metros)'], 2)
            
        return df_agregado