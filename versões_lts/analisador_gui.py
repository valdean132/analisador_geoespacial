import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import zipfile
import os
import numpy as np
import fiona 
import time
import tkinter as tk
from tkinter import filedialog, scrolledtext, ttk
import threading
import queue
import sys

# --- 1. SEU CÓDIGO DE ANÁLISE (ADAPTADO PARA SER UMA FUNÇÃO) ---
# Todo o seu código original foi colocado dentro desta função.
# Ela agora recebe os caminhos dos arquivos como argumentos.

def extrair_todos_poligonos_do_kmz(arquivo_kmz):
    basename = os.path.basename(arquivo_kmz).split('.')[0]
    temp_dir = f"kmzs/temp/{basename}"
    caminho_kml = None
    if os.path.isdir(temp_dir):
        try:
            kml_filename = next(f for f in os.listdir(temp_dir) if f.lower().endswith('.kml'))
            caminho_kml = os.path.join(temp_dir, kml_filename)
        except StopIteration:
            caminho_kml = None
    if caminho_kml is None:
        try:
            with zipfile.ZipFile(arquivo_kmz, 'r') as kmz:
                kml_files = [f for f in kmz.namelist() if f.lower().endswith('.kml')]
                if not kml_files: return None
                print(f"⚠️ --- Atenção ---: Extraindo arquivo KMZ '{basename}' para KML.")
                caminho_kml = kmz.extract(kml_files[0], path=temp_dir)
        except Exception:
            return None
    try:
        camadas = fiona.listlayers(caminho_kml)
    except Exception:
        return None
    lista_de_gdfs = []
    for camada in camadas:
        try:
            gdf_camada = gpd.read_file(caminho_kml, driver='KML', layer=camada)
            gdf_camada = gdf_camada[gdf_camada.geometry.type.isin(['Polygon', 'MultiPolygon'])]
            if not gdf_camada.empty:
                lista_de_gdfs.append(gdf_camada)
        except Exception:
            continue
    if not lista_de_gdfs:
        return None
    return gpd.GeoDataFrame(pd.concat(lista_de_gdfs, ignore_index=True), crs="EPSG:4326")

def analisar_viabilidade(pasta_kmz, arquivo_excel, raio_km):
    # --- CONFIGURAÇÕES INTERNAS (NÃO PRECISAM SER MUDADAS) ---
    COLUNA_LATITUDE = 'LATITUDE'
    COLUNA_LONGITUDE = 'LONGITUDE'
    COLUNA_VELOCIDADE = 'VELOCIDADE'
    COLUNA_COORDENADAS = 'COORDENADAS'
    COLUNA_NOME_MANCHA = 'Name'
    
    # Gera o nome do arquivo de saída baseado no de entrada
    base_name, ext = os.path.splitext(os.path.basename(arquivo_excel))
    arquivo_saida = f"{base_name}_resultado.xlsx"
    
    print("🐫 Iniciando análise de viabilidade...")
    
    try:
        print(f"\n🐫 Lendo o arquivo de coordenadas: {os.path.basename(arquivo_excel)}")
        df_pontos = pd.read_excel(arquivo_excel)
    except Exception as e:
        print(f"\n❌ --- ERRO ---: Não foi possível localizar ou ler o arquivo '{os.path.basename(arquivo_excel)}'. Erro: {e}")
        return

    arquivos_kmz = [f for f in os.listdir(pasta_kmz) if f.lower().endswith('.kmz')]
    if not arquivos_kmz:
        print(f"❌ --- ERRO ---: Nenhum arquivo .kmz foi encontrado na pasta selecionada.")
        return

    print(f"\n😎 Arquivos KMZ encontrados para análise: {arquivos_kmz}\n")
    dados_dos_kmz = {}
    dados_dos_kmz_projetados = {}
    for kmz_file in arquivos_kmz:
        caminho_completo = os.path.join(pasta_kmz, kmz_file)
        gdf_poligonos = extrair_todos_poligonos_do_kmz(caminho_completo)
        if gdf_poligonos is not None:
            print(f"🤞 Processando polígonos de: {kmz_file.split('.')[0]}...")
            dados_dos_kmz[kmz_file] = gdf_poligonos
            if raio_km > 0:
                dados_dos_kmz_projetados[kmz_file] = gdf_poligonos.to_crs('EPSG:5880')
    if not dados_dos_kmz:
        print("❌ --- ERRO ---: Nenhum polígono válido foi carregado de nenhum dos arquivos KMZ.")
        return
        
    print("\n🚀 Otimizando dados de entrada (vetorização)...")
    def criar_ponto(row):
        if COLUNA_LONGITUDE in row.index and COLUNA_LATITUDE in row.index and pd.notna(row[COLUNA_LONGITUDE]) and pd.notna(row[COLUNA_LATITUDE]):
            try: return Point(float(row[COLUNA_LONGITUDE]), float(row[COLUNA_LATITUDE]))
            except (ValueError, TypeError): return None
        elif COLUNA_COORDENADAS in row.index and pd.notna(row[COLUNA_COORDENADAS]):
            try:
                coordenada = str(row[COLUNA_COORDENADAS]).split(',')
                if len(coordenada) == 2: return Point(float(coordenada[1]), float(coordenada[0]))
            except (ValueError, TypeError, IndexError): return None
        return None
    df_pontos['geometry'] = df_pontos.apply(criar_ponto, axis=1)
    gdf_pontos = gpd.GeoDataFrame(df_pontos, geometry='geometry', crs="EPSG:4326")
    if raio_km > 0:
        gdf_pontos['geometry_proj'] = gdf_pontos.to_crs('EPSG:5880').geometry
    if COLUNA_VELOCIDADE in gdf_pontos.columns:
        gdf_pontos['velocidade_num'] = pd.to_numeric(gdf_pontos[COLUNA_VELOCIDADE].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0)
    else:
        gdf_pontos['velocidade_num'] = 0
    
    print(f"\n🐫 Iniciando verificação de {len(gdf_pontos)} pontos...")
    resultados = []
    for row in gdf_pontos.itertuples():
        ponto = row.geometry
        if ponto is None:
            resultados.append({'Status Viabilidade': 'Coordenada Inválida', 'Mancha': '---', 'Nome da Mancha': '---', 'Distância (metros)': None})
            continue
        encontrado = False
        for nome_arquivo, gdf_poligonos in dados_dos_kmz.items():
            if gdf_poligonos.contains(ponto).any():
                mancha_encontrada = gdf_poligonos[gdf_poligonos.contains(ponto)].iloc[0]
                nome_da_mancha = mancha_encontrada.get(COLUNA_NOME_MANCHA, 'Nome não encontrado')
                status = 'Viabilidade Expressa' if row.velocidade_num <= 500 else 'Verificar PTP'
                resultados.append({'Status Viabilidade': status, 'Mancha': nome_arquivo.split('.')[0], 'Nome da Mancha': nome_da_mancha, 'Distância (metros)': 0})
                encontrado = True
                break
        if encontrado:
            continue
        if raio_km > 0:
            ponto_projetado = row.geometry_proj
            distancia_minima = float('inf')
            melhor_match = None
            for nome_arquivo, gdf_projetado in dados_dos_kmz_projetados.items():
                distancia_local_min = gdf_projetado.distance(ponto_projetado).min()
                if distancia_local_min < distancia_minima:
                    distancia_minima = distancia_local_min
                    melhor_match = {'arquivo': nome_arquivo.split('.')[0]}
            if distancia_minima <= (raio_km * 1000):
                gdf_original = dados_dos_kmz[melhor_match['arquivo'] + '.kmz']
                gdf_proj_original = dados_dos_kmz_projetados[melhor_match['arquivo'] + '.kmz']
                mancha_mais_proxima = gdf_original.loc[gdf_proj_original.distance(ponto_projetado).idxmin()]
                nome_mancha_proxima = mancha_mais_proxima.get(COLUNA_NOME_MANCHA, 'Nome não encontrado')
                resultados.append({'Status Viabilidade': 'Próximo à mancha', 'Mancha': melhor_match['arquivo'], 'Nome da Mancha': nome_mancha_proxima, 'Distância (metros)': round(distancia_minima, 2)})
                encontrado = True
        if not encontrado:
            resultados.append({'Status Viabilidade': 'Inviável', 'Mancha': '---', 'Nome da Mancha': '---', 'Distância (metros)': None})
    
    print("\n😍 Finalizando e salvando o arquivo de resultado...")
    df_resultados = pd.DataFrame(resultados)
    colunas_para_remover = [col for col in ['geometry', 'geometry_proj', 'velocidade_num'] if col in gdf_pontos.columns]
    df_pontos_sem_geom = gdf_pontos.drop(columns=colunas_para_remover)
    df_final = pd.concat([df_pontos_sem_geom.reset_index(drop=True), df_resultados.reset_index(drop=True)], axis=1)
    
    try:
        df_final.to_excel(arquivo_saida, index=False, engine='openpyxl')
        print(f"\n✅ Concluído! O resultado foi salvo em '{arquivo_saida}'.")
        print("\nResumo da Análise:")
        print(df_final['Status Viabilidade'].value_counts())
    except Exception as e:
        print(f"\n❌ --- ERRO ---: Não foi possível salvar arquivo '{arquivo_saida}'. Verifique se ele não está aberto. Erro: {e}")

# --- 2. CÓDIGO DA INTERFACE GRÁFICA (GUI) ---

class App:
    def __init__(self, root):
        self.root = root
        self.root.title("Analisador de Viabilidade Geográfica")
        self.root.geometry("800x600")

        self.kmz_folder_path = tk.StringVar()
        self.excel_file_path = tk.StringVar()
        self.raio_km = tk.DoubleVar(value=1.0) # Valor padrão de 1 KM
        
        # --- Frame para os inputs ---
        input_frame = ttk.Frame(root, padding="10")
        input_frame.pack(fill=tk.X)

        # Seleção da Pasta KMZ
        ttk.Label(input_frame, text="Pasta dos KMZ:").grid(row=0, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.kmz_folder_path, width=60).grid(row=0, column=1, sticky=(tk.W, tk.E))
        ttk.Button(input_frame, text="Selecionar Pasta...", command=self.select_kmz_folder).grid(row=0, column=2, padx=5)

        # Seleção do Arquivo Excel
        ttk.Label(input_frame, text="Planilha de Coordenadas:").grid(row=1, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.excel_file_path, width=60).grid(row=1, column=1, sticky=(tk.W, tk.E))
        ttk.Button(input_frame, text="Selecionar Arquivo...", command=self.select_excel_file).grid(row=1, column=2, padx=5)
        
        # Input do Raio
        ttk.Label(input_frame, text="Raio de Proximidade (KM):").grid(row=2, column=0, sticky=tk.W, padx=5, pady=5)
        ttk.Entry(input_frame, textvariable=self.raio_km, width=10).grid(row=2, column=1, sticky=tk.W)

        input_frame.columnconfigure(1, weight=1)

        # --- Botão de Análise ---
        self.analyze_button = ttk.Button(root, text="Iniciar Análise", command=self.start_analysis)
        self.analyze_button.pack(pady=10)

        # --- Área de Log ---
        log_frame = ttk.Frame(root, padding="10")
        log_frame.pack(fill=tk.BOTH, expand=True)
        self.log_area = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD, height=10)
        self.log_area.pack(fill=tk.BOTH, expand=True)
        
        # --- Fila para comunicação entre threads ---
        self.log_queue = queue.Queue()
        self.process_log_queue()

    def select_kmz_folder(self):
        path = filedialog.askdirectory(title="Selecione a pasta com os arquivos KMZ")
        if path:
            self.kmz_folder_path.set(path)

    def select_excel_file(self):
        path = filedialog.askopenfilename(
            title="Selecione a planilha de coordenadas",
            filetypes=(("Arquivos Excel", "*.xlsx *.xls"), ("Todos os arquivos", "*.*"))
        )
        if path:
            self.excel_file_path.set(path)

    def start_analysis(self):
        kmz_path = self.kmz_folder_path.get()
        excel_path = self.excel_file_path.get()
        raio = self.raio_km.get()

        if not kmz_path or not excel_path:
            self.log_area.insert(tk.END, "❌ ERRO: Por favor, selecione a pasta KMZ e o arquivo Excel antes de iniciar.\n")
            return
        
        self.log_area.delete('1.0', tk.END)
        self.analyze_button.config(state=tk.DISABLED, text="Analisando...")
        
        # Inicia a análise em uma thread separada para não travar a GUI
        self.analysis_thread = threading.Thread(
            target=self.run_analysis_thread,
            args=(kmz_path, excel_path, raio)
        )
        self.analysis_thread.start()

    def run_analysis_thread(self, kmz_path, excel_path, raio):
        # Redireciona o print para a nossa fila
        sys.stdout = QueueLogger(self.log_queue)
        
        start_time = time.perf_counter()
        try:
            analisar_viabilidade(kmz_path, excel_path, raio)
        except Exception as e:
            print(f"\n❌ UM ERRO INESPERADO OCORREU: {e}")
        finally:
            # Restaura o print e reabilita o botão
            sys.stdout = sys.__stdout__
            end_time = time.perf_counter()
            duration = end_time - start_time
            self.log_queue.put(f"\n⏳--- Tempo total de execução: {duration:.2f} segundos ---")
            self.analyze_button.config(state=tk.NORMAL, text="Iniciar Análise")

    def process_log_queue(self):
        try:
            while True:
                message = self.log_queue.get_nowait()
                self.log_area.insert(tk.END, message)
                self.log_area.see(tk.END) # Auto-scroll
        except queue.Empty:
            pass
        self.root.after(100, self.process_log_queue)

# Classe para redirecionar o 'print' para a fila da GUI
class QueueLogger:
    def __init__(self, queue):
        self.queue = queue
    def write(self, text):
        self.queue.put(text)
    def flush(self):
        pass

# --- 3. INICIA A APLICAÇÃO ---
if __name__ == "__main__":
    root = tk.Tk()
    app = App(root)
    root.mainloop()
    
    
    
""" # df_final['Status Viabilidade'].fillna('Inviável', inplace=True)
    df_final.fillna({'Status Viabilidade': 'Inviável'}, inplace=True) """