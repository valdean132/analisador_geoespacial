# -*- coding: utf-8 -*-
__name = "Analisador de Viabilidade Geoespacial"
__author = "Valdean P. Souza & Gilmar Batista"
__version = "1.3.0"
__license = "CC BY-ND"

import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import zipfile
import os
import fiona
import time
import uuid

#  -- Gerando UUID para não repetir arquivo análisado
id_unico = uuid.uuid4()
id_unico = str(id_unico).split('-', 2)
id_unico = id_unico[0]+id_unico[1]

# --- 1. CONFIGURAÇÃO (AJUSTE CONFORME NECESSÁRIO) ---
PASTA_DOS_KMZ = 'kmzs'
ARQUIVO_EXCEL_PONTOS = 'verificar_viabilidade.xlsx'
ARQUIVO_EXCEL_SAIDA = f'resultados/resultado_viabilidade-{id_unico}.xlsx'

# --- Nomes das colunas na sua planilha ---
COLUNA_LATITUDE = 'LATITUDE'
COLUNA_LONGITUDE = 'LONGITUDE'
COLUNA_COORDENADAS = 'COORDENADAS' # Coluna alternativa
COLUNA_VELOCIDADE = 'VELOCIDADE'
COLUNA_NOME_MANCHA = 'Name'

# --- Configurações Geo ---
RAIO_PROXIMIDADE_METROS = .5 * 1000
CRS_GEOGRAFICO = "EPSG:4326"  # WGS84, padrão para lat/lon (KML/GPS)
CRS_PROJETADO = "EPSG:5880"   # SIRGAS 2000 / Brazil Polyconic, para cálculos em metros

# --- 2. FUNÇÕES AUXILIARES ---
def print_header(name, author, version, license):
    """
    Imprime um cabeçalho estilizado e profissional no console.
    
    Args:
        name (str): nome do programa.
        author (str): nome do Autor.
        version (str): Versão do Script
        license (str): Licença do Script

    """
    box_width = 80
    title = name

    # Monta as linhas do cabeçalho usando f-strings para centralizar e alinhar
    top_bottom_border = "=" * box_width
    separator = "|" + "-" * (box_width - 2) + "|"
    empty_line = "|" + " " * (box_width - 2) + "|"
    
    title_line = f"|{title:^{box_width - 2}}|"
    author_line = f"| {'Autor:':<10} {author:<{box_width - 14}} |"
    version_line = f"| {'Versão:':<10} {version:<{box_width - 14}} |"
    license_line = f"| {'Licença:':<10} {license:<{box_width - 14}} |"

    # Imprime o cabeçalho completo com espaçamento
    print("\n" + top_bottom_border)
    print(empty_line)
    print(title_line)
    print(empty_line)
    print(separator)
    print(author_line)
    print(version_line)
    print(license_line)
    print(empty_line)
    print(top_bottom_border + "\n")

def extrair_todos_poligonos_do_kmz(arquivo_kmz):
    """ 
    Extrai os arquivos KMZ's para KML's na pasta TEMP caso ainda na esteja extraido
    Depois retorna os poligonos encontrados de cada arquivo extraido para KML
    
    Args:
        arquivo_kmz (str): caminho do arquivo KMZ encontrado.
    """
    basename = os.path.basename(arquivo_kmz).split('.')[0]
    temp_dir = os.path.join(PASTA_DOS_KMZ, "temp", basename)
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
        return gpd.GeoDataFrame(pd.concat(lista_de_gdfs, ignore_index=True), crs=CRS_GEOGRAFICO)
    except Exception as e:
        print(f"❌ Erro ao ler KML '{caminho_kml}': {e}")
        return None

def criar_ponto(row, mode):
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
            lon = row[COLUNA_LONGITUDE]
            lat = row[COLUNA_LATITUDE]
            
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
            coords_str = row[COLUNA_COORDENADAS]
            
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

# --- 3. CÓDIGO DE PROCESSAMENTO OTIMIZADO ---
def analisar_viabilidade_otimizado():
    print("🐫 Iniciando análise de viabilidade com agregação completa de resultados...")
    
    # Verificando se arquivo realmente existe ou foi exportado corretamente antes de prosseguir com o código
    try:
        df_pontos = pd.read_excel(ARQUIVO_EXCEL_PONTOS)
    except FileNotFoundError:
        print(f"\n❌ ERRO: Arquivo '{ARQUIVO_EXCEL_PONTOS}' não encontrado.")
        return
    
    # --- Etapa 1: Carregar polígonos (sem alteração) ---
    print("\n[1/7] 🗺️  Carregando e processando arquivos KMZ...")
    # (código omitido para brevidade, é o mesmo da versão anterior)
    arquivos_kmz = [f for f in os.listdir(PASTA_DOS_KMZ) if f.lower().endswith('.kmz')]
    if not arquivos_kmz:
        print(f"❌ ERRO: Nenhum arquivo .kmz encontrado em '{PASTA_DOS_KMZ}'.")
        return
    lista_poligonos_gdfs = []
    for kmz_file in arquivos_kmz:
        caminho_completo = os.path.join(PASTA_DOS_KMZ, kmz_file)
        gdf_poligonos = extrair_todos_poligonos_do_kmz(caminho_completo)
        if gdf_poligonos is not None and not gdf_poligonos.empty:
            gdf_poligonos['Mancha'] = os.path.basename(kmz_file).split('.')[0]
            lista_poligonos_gdfs.append(gdf_poligonos)
    if not lista_poligonos_gdfs:
        print("❌ ERRO: Nenhum polígono válido foi carregado dos arquivos KMZ.")
        return
    gdf_manchas_global = gpd.GeoDataFrame(pd.concat(lista_poligonos_gdfs, ignore_index=True), crs=CRS_GEOGRAFICO)
    if COLUNA_NOME_MANCHA not in gdf_manchas_global.columns:
        gdf_manchas_global[COLUNA_NOME_MANCHA] = 'Nome não encontrado'
    else:
        gdf_manchas_global[COLUNA_NOME_MANCHA] = gdf_manchas_global[COLUNA_NOME_MANCHA].fillna('Nome não encontrado')

    # --- Etapa 2: Carregar pontos e VALIDAR COLUNAS (sem alteração) ---
    print("\n[2/7] 📍 Lendo e validando o arquivo de coordenadas...")
    # (código omitido para brevidade, é o mesmo da versão anterior)
    
    modo_coordenadas = None
    if COLUNA_LATITUDE in df_pontos.columns and COLUNA_LONGITUDE in df_pontos.columns:
        modo_coordenadas = 'latlon'
    elif COLUNA_COORDENADAS in df_pontos.columns:
        modo_coordenadas = 'coords'
    else:
        print(f"❌ ERRO FATAL: Nenhuma coluna de coordenada encontrada.")
        return

    # --- Etapa 3: Criar geometrias e separar pontos (sem alteração) ---
    print("\n[3/7] 🧐 Validando cada ponto e criando geometrias...")
    # (código omitido para brevidade, é o mesmo da versão anterior)
    df_pontos['geometry'] = df_pontos.apply(lambda row: criar_ponto(row, mode=modo_coordenadas), axis=1)
    invalidos_mask = df_pontos['geometry'].isna()
    df_invalidos = df_pontos[invalidos_mask].copy()
    df_validos = df_pontos[~invalidos_mask].copy()
    print(f"   -> {len(df_validos)} pontos válidos para análise.")
    print(f"   -> {len(df_invalidos)} pontos marcados como 'Coordenada Inválida'.")
    
    resultados_geo = pd.DataFrame()
    if not df_validos.empty:
        gdf_pontos = gpd.GeoDataFrame(df_validos, geometry='geometry', crs=CRS_GEOGRAFICO)
        if COLUNA_VELOCIDADE in gdf_pontos.columns:
            gdf_pontos['velocidade_num'] = pd.to_numeric(
                gdf_pontos[COLUNA_VELOCIDADE].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0)
        else:
            gdf_pontos['velocidade_num'] = 0

        # --- Etapa 4: Análise Espacial "DENTRO" e Agregação ---
        print("\n[4/7] ⚡ Executando análise 'DENTRO' e agregando resultados...")
        
        gdf_dentro_bruto = gpd.sjoin(gdf_pontos, gdf_manchas_global, how="inner", predicate="within")
        
        gdf_dentro_agregado = pd.DataFrame()
        if not gdf_dentro_bruto.empty:
            gdf_dentro_bruto['Status Viabilidade'] = gdf_dentro_bruto.apply(
                lambda row: 'Viabilidade Expressa' if row.velocidade_num <= 500 else 'Verificar PTP', axis=1)
            gdf_dentro_bruto['Distância (metros)'] = 0
            agg_rules = {
                'Mancha': lambda x: ', '.join(x.unique()),
                COLUNA_NOME_MANCHA: lambda x: ', '.join(x.unique()),
                'Status Viabilidade': 'first',
                'Distância (metros)': 'first'
            }
            gdf_dentro_agregado = gdf_dentro_bruto.groupby(gdf_dentro_bruto.index).agg(agg_rules)

        # --- Etapa 5: Análise "PRÓXIMO" e Agregação ---
        print("\n[5/7] 🛰️  Executando análise 'PRÓXIMO' para os pontos restantes...")
        indices_encontrados = gdf_dentro_agregado.index
        gdf_pontos_fora = gdf_pontos.drop(indices_encontrados)
        
        gdf_proximos_agregado = pd.DataFrame()
        if not gdf_pontos_fora.empty and RAIO_PROXIMIDADE_METROS > 0:
            gdf_pontos_proj = gdf_pontos_fora.to_crs(CRS_PROJETADO)
            gdf_manchas_proj = gdf_manchas_global.to_crs(CRS_PROJETADO)
            
            # 1. Obter resultados brutos (com possíveis duplicatas)
            gdf_proximos_bruto = gpd.sjoin_nearest(gdf_pontos_proj, gdf_manchas_proj, max_distance=RAIO_PROXIMIDADE_METROS, how="inner")
            
            if not gdf_proximos_bruto.empty:
                print("\n[6/7] 🧬 Agregando resultados de proximidade...")
                # 2. Calcular a distância para CADA correspondência bruta
                nearest_polygons = gdf_manchas_proj.loc[gdf_proximos_bruto['index_right'], 'geometry']
                aligned_polygons = gpd.GeoSeries(nearest_polygons.values, index=gdf_proximos_bruto.index, crs=CRS_PROJETADO)
                gdf_proximos_bruto['Distância (metros)'] = gdf_proximos_bruto.geometry.distance(aligned_polygons)
                gdf_proximos_bruto['Status Viabilidade'] = 'Próximo à mancha'

                # 3. Definir as regras de agregação para proximidade
                agg_rules_prox = {
                    'Mancha': lambda x: ', '.join(x.unique()),
                    COLUNA_NOME_MANCHA: lambda x: ', '.join(x.unique()),
                    'Status Viabilidade': 'first',
                    'Distância (metros)': 'min' # <-- Pega a MENOR distância
                }

                # 4. Agregar os resultados para garantir uma linha por ponto
                gdf_proximos_agregado = gdf_proximos_bruto.groupby(gdf_proximos_bruto.index).agg(agg_rules_prox)
                gdf_proximos_agregado['Distância (metros)'] = round(gdf_proximos_agregado['Distância (metros)'], 2)

        # --- Etapa 7: Consolidar e salvar o relatório final ---
        print("\n[7/7] 💾 Montando e salvando o relatório final...")
        
        # Junta os resultados dos agregados
        resultados_geo = pd.concat([
            gdf_dentro_agregado,
            gdf_proximos_agregado # Agora usamos o agregado aqui também
        ]).rename(columns={COLUNA_NOME_MANCHA: 'Nome da Mancha'})

        df_final = df_pontos.merge(resultados_geo, left_index=True, right_index=True, how="left")
        df_final.loc[invalidos_mask, 'Status Viabilidade'] = 'Coordenada Inválida'
        
        # df_final['Status Viabilidade'].fillna('Inviável', inplace=True)
        df_final.fillna({'Status Viabilidade': 'Inviável'}, inplace=True)

        df_final[['Mancha', 'Nome da Mancha']] = df_final[['Mancha', 'Nome da Mancha']].fillna('---')
        df_final = df_final.drop(columns=['geometry'], errors='ignore')

    try:
        print("\n📊 Resumo da Análise:")
        print(df_final['Status Viabilidade'].value_counts())
        
        df_final.to_excel(ARQUIVO_EXCEL_SAIDA, index=False, engine='openpyxl')
        
        print(f"\n✅ Concluído! O resultado foi salvo em '{ARQUIVO_EXCEL_SAIDA}'.")
    except Exception as e:
        print(f"\n❌ ERRO ao salvar '{ARQUIVO_EXCEL_SAIDA}': {e}")

# --- Executa a função principal ---
if __name__ == "__main__":

    # Imprime o cabeçalho no início
    print_header(__name, __author, __version, __license)
    
    start_time = time.perf_counter()
    
    analisar_viabilidade_otimizado()
    end_time = time.perf_counter()
    duration = end_time - start_time
    print(f"\n⏳--- Tempo total de execução: {duration:.2f} segundos ---")