import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import zipfile
import os
import fiona
import concurrent.futures

from api.core.models.ptp_model import PTPModel

class GeoAnalyzer:
    def __init__(
        self, 
        pasta_kmz: str, 
        arquivo_excel_path: str, 
        raio_km: float, 
        coluna_coordenadas: str, 
        coluna_velocidade, 
        type_busca: int
    ):
        self.pasta_kmz = pasta_kmz
        self.arquivo_excel_path = arquivo_excel_path
        self.raio_km = raio_km
        self.type_busca = type_busca
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
            
            # Verificando Tipo de busca;
            if self.type_busca == 1:
                tipo_busca = 'Redes Na Cidade'
            elif self.type_busca == 2:
                tipo_busca = 'Mancha GPON'
            elif self.type_busca == 3:
                tipo_busca = 'Mancha GPON e Redes Na Cidade'
            
            yield 1, f"Tipo de busca: {tipo_busca}"
            
            # ============================================================
            # TYPE_BUSCA = 1  → SOMENTE BANCO DE DADOS
            # ============================================================
            
            if self.type_busca == 1:
                yield 10, "Preparando dados para busca PTP..."

                df_pontos = pd.read_excel(self.arquivo_excel_path)
                # Inicializa colunas
                df_pontos["Status"] = ""
                df_pontos["Rede PTP"] = ""

                modo_coordenadas = self._validar_colunas_pontos(df_pontos)
                
                # Função auxiliar para processar uma única linha (será executada em paralelo)
                def processar_linha(args):
                    index, row = args
                    try:
                        # Usa sua função _extrair_coord (assumindo que ela existe na classe)
                        lat, lon = self._extrair_coord(row, modo_coordenadas)
                        
                        if lat is None or lon is None:
                            return index, "Coordenada Inválida", ""

                        # Chamada ao banco
                        resultado = PTPModel.rede_ptp(lat, lon) 
                        
                        if resultado and resultado.get('redes'):
                            return index, "Analisar (Rede/SW na Cidade)", resultado['redes']
                        else:
                            return index, "Inviável", "---"
                    except Exception:
                        return index, "Coordenada Inválida", ""

                # Prepara os dados para o executor (lista de tuplas)
                linhas_para_processar = list(df_pontos.iterrows())
                total_linhas = len(linhas_para_processar)
                
                yield 15, "Iniciando consultas paralelas..."

                # Executa em paralelo (ajuste max_workers conforme a capacidade do seu banco)
                # max_workers=10 ou 20 costuma ser seguro para consultas rápidas
                with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                    # Submete as tarefas
                    futures = [executor.submit(processar_linha, item) for item in linhas_para_processar]
                    
                    # Processa os resultados à medida que ficam prontos
                    for i, future in enumerate(concurrent.futures.as_completed(futures)):
                        idx, status, rede = future.result()
                        
                        # Atualiza o DataFrame (acesso direto pelo índice é rápido)
                        df_pontos.at[idx, "Status"] = status
                        df_pontos.at[idx, "Rede PTP"] = rede
                        
                        # Atualiza o progresso a cada X linhas para não floodar o frontend
                        if i % 10 == 0:
                            progresso = 15 + int(85 * (i + 1) / total_linhas)
                            yield progresso, f"Consultando {i + 1}/{total_linhas}"

                self.df_final = df_pontos
                self.resumo = df_pontos["Status"].value_counts().to_dict()
                
                yield 100, "Análise concluída (modo: somente PTP)"
                return
            
            
            # ============================================================
            # TYPE_BUSCA 2 e 3 → SEGUEM O KMZ NORMAL
            # ============================================================
            
            # --- Etapa 1: Carregar polígonos ---
            yield 5, "Carregando arquivos KMZ..."
            arquivos_kmz = [os.path.join(self.pasta_kmz, f) for f in os.listdir(self.pasta_kmz) if f.lower().endswith('.kmz')]
            if not arquivos_kmz:
                os.remove(self.arquivo_excel_path)
                raise ValueError(f"Nenhum arquivo .kmz encontrado em '{self.pasta_kmz}'")

            lista_poligonos_gdfs = []
            for i, kmz_file_path in enumerate(arquivos_kmz):
                # Usando um método auxiliar para manter o código limpo
                gdf_poligonos = self._extrair_poligonos(kmz_file_path)
                if gdf_poligonos is not None:
                    gdf_poligonos['Mancha GPON'] = os.path.basename(kmz_file_path).split('.')[0]
                    lista_poligonos_gdfs.append(gdf_poligonos)
                yield 10 + int(20 * (i + 1) / len(arquivos_kmz)), f"Processando KMZ {i + 1}/{len(arquivos_kmz)}"

            if not lista_poligonos_gdfs:
                os.remove(self.arquivo_excel_path)
                raise ValueError("Nenhum polígono válido foi carregado dos arquivos KMZ.")
            
            gdf_manchas_global = gpd.GeoDataFrame(pd.concat(lista_poligonos_gdfs, ignore_index=True), crs=self.CRS_GEOGRAFICO)
            
            # ============================================================
            # ANALISAR ARQUIVO DE PONTOS
            # ============================================================
            
            # --- Etapa 2 & 3: Carregar e processar pontos ---
            yield 35, "Lendo e validando arquivo de pontos..."
            df_pontos = pd.read_excel(self.arquivo_excel_path)
            
            # ... (Lógica de validação e criação de geometria idêntica à anterior) ...
            modo_coordenadas = self._validar_colunas_pontos(df_pontos)
            
            df_pontos['geometry'] = df_pontos.apply(
                lambda row: self._criar_ponto(row, modo_coordenadas), 
                axis=1
            )
            
            invalidos_mask = df_pontos['geometry'].isna()
                
            # --- Etapa 4, 5, 6: Análise Espacial ---
            df_validos = df_pontos[~invalidos_mask]

            # ============================================================
            # ANÁLISE ESPACIAL (KMZ NORMAL)
            # ============================================================
            if not df_validos.empty:
                gdf_pontos = gpd.GeoDataFrame(df_validos, geometry='geometry', crs=self.CRS_GEOGRAFICO)
                if self.COLUNA_VELOCIDADE in gdf_pontos.columns:
                    gdf_pontos['velocidade_num'] = pd.to_numeric(gdf_pontos[self.COLUNA_VELOCIDADE].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0)
                else:
                    gdf_pontos['velocidade_num'] = 0
                
                # Dentro da Mancha
                yield 50, "Analisando pontos DENTRO das manchas..."
                # ... (Lógica sjoin e agregação para 'dentro') ...
                gdf_dentro_bruto = gpd.sjoin(gdf_pontos, gdf_manchas_global, how="inner", predicate="within")
                gdf_dentro_agregado = self._aggregate_results(gdf_dentro_bruto, 'dentro', gdf_pontos)

                # Próximo a Mancha
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
                        gdf_proximos_bruto['Dist. GPON (mts)'] = gdf_proximos_bruto.geometry.distance(aligned_polygons)
                        gdf_proximos_agregado = self._aggregate_results(gdf_proximos_bruto, 'proximo', gdf_pontos)

                # resultados_geo = pd.concat([gdf_dentro_agregado, gdf_proximos_agregado]).rename(columns={self.COLUNA_NOME_MANCHA: 'Nome da Mancha'})
                resultados_geo = pd.concat([gdf_dentro_agregado, gdf_proximos_agregado])
            else:
                resultados_geo = pd.DataFrame()
            
            # ============================================================
            # CONSOLIDAR RESULTADOS
            # ============================================================
            
            # --- Etapa 7: Consolidar ---
            yield 95, "Consolidando resultados GPON..."
            df_final = df_pontos.merge(resultados_geo, left_index=True, right_index=True, how="left")
            df_final.loc[invalidos_mask, 'Status'] = 'Coordenada Inválida'
            df_final.fillna({'Status': 'Inviável'}, inplace=True)
            
            
            # Preenche colunas GPON vazias
            df_final.fillna({'Mancha GPON': '---', 'Dist. GPON (mts)': '---'}, inplace=True)
            
            # ============================================================
            # TYPE_BUSCA = 3 → FAZER BUSCA PTP APENAS PARA OS INVIÁVEIS
            # ============================================================
            if self.type_busca == 3:
                df_final["Rede PTP"] = "---"

                # Fltrar apenas os índices que deram "Inviáveis" na busca GPON
                indices_inviaveis = df_final[df_final['Status'] == 'Inviável'].index

                total_inviaveis = len(indices_inviaveis)

                if total_inviaveis > 0:
                    yield 96, f"Buscando PTP para {total_inviaveis} pontos sem cobertura GPON..."
                
                    # Define a função de busca PTP (similar à do Nível 1)
                    def buscar_ptp_fallback(idx):
                        try:
                            row = df_final.loc[idx]
                            # Recria geometria se necessário ou usa lat/lon originais
                            # Assumindo que _extrair_coord funciona com a linha do df_final
                            lat, lon = self._extrair_coord(row, modo_coordenadas)
                            
                            if lat is None or lon is None:
                                return idx, None

                            resultado = PTPModel.rede_ptp(lat, lon)
                            if resultado and resultado.get('redes'):
                                return idx, resultado['redes']
                            return idx, None
                        except:
                            return idx, None

                    # Executa em paralelo apenas para os inviáveis
                    with concurrent.futures.ThreadPoolExecutor(max_workers=30) as executor:
                        futures = [executor.submit(buscar_ptp_fallback, idx) for idx in indices_inviaveis]
                        
                        for i, future in enumerate(concurrent.futures.as_completed(futures)):
                            idx, rede_encontrada = future.result()

                            if rede_encontrada:
                                # Atualiza o Status e a Rede
                                df_final.at[idx, 'Status'] = 'Analisar (Rede/SW na Cidade)'
                                df_final.at[idx, 'Rede PTP'] = rede_encontrada

                            if i % 50 == 0:
                                yield 96 + int(3 * (i+1)/total_inviaveis), f"Verificando PTP {i+1}/{total_inviaveis}..."
            
            # ============================================================
            # FINALIZAR
            # ============================================================
            # --- Finalização e Organização ---
            yield 99, "Finalizando relatório..."
            
            df_final = df_final.drop(columns=['geometry'], errors='ignore')
            
            resumo = df_final['Status'].value_counts().to_dict()
            
            # Organizando Colunas;
            if self.type_busca == 1:
                colunas_fixas = ['Status', 'Rede PTP']
            elif self.type_busca == 2:
                colunas_fixas = ['Status', 'Mancha GPON', 'Dist. GPON (mts)']
            elif self.type_busca == 3:
                colunas_fixas = ['Status', 'Mancha GPON', 'Dist. GPON (mts)', 'Rede PTP']

            colunas_originais = [c for c in df_final.columns if c not in colunas_fixas]

            df_final = df_final[colunas_originais + colunas_fixas]

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
    
    def _extrair_coord(self, row, mode):
        """
        Reusa _criar_ponto() para extrair latitude e longitude validados.
        Retorna (lat, lon) ou (None, None).
        """
        ponto = self._criar_ponto(row, mode)
        if ponto is None:
            return None, None
        
        # point.x = lon, point.y = lat
        return ponto.y, ponto.x
    
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
            os.remove(self.arquivo_excel_path)
            raise ValueError(f"Nenhuma coluna de coordenada encontrada.")
    
    def _aggregate_results(self, df_bruto, mode, gdf_pontos):
        if df_bruto.empty:
            return pd.DataFrame()
        if mode == 'dentro':
            df_bruto['Status'] = df_bruto.apply(
                lambda row: 'Viabilidade Expressa' if gdf_pontos.loc[row.name]['velocidade_num'] <= 500 else 'Verificar PTP', axis=1)
            df_bruto['Dist. GPON (mts)'] = 0
            agg_rules = {'Dist. GPON (mts)': 'first'}
        else: # modo 'proximo'
            df_bruto['Status'] = 'Próximo à mancha'
            agg_rules = {'Dist. GPON (mts)': 'min'}
        
        agg_rules.update({
            'Status': 'first',
            'Mancha GPON': lambda x: ', '.join(x.unique()),
            # self.COLUNA_NOME_MANCHA: lambda x: ', '.join(x.unique()), #! Apagar após todos os testes serem concluídos
        })
        
        df_agregado = df_bruto.groupby(df_bruto.index).agg(agg_rules)
        
        if 'Dist. GPON (mts)' in df_agregado.columns:
            df_agregado['Dist. GPON (mts)'] = round(df_agregado['Dist. GPON (mts)'], 2)
            
        return df_agregado