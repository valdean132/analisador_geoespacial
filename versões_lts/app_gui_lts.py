# -*- coding: utf-8 -*-
__name = "Analisador de Viabilidade Geoespacial"
__author = "Valdean P. Souza & Gilmar Batista"
__version = "3.0.0"
__license = "CC BY-ND"

import tkinter
import tkinter.messagebox
from tkinter import filedialog
import customtkinter
import threading
import pandas as pd
import geopandas as gpd
from shapely.geometry import Point
import zipfile
import os
import fiona
import time
import uuid

# ========================================================================================
#  PARTE 1: O "MOTOR" DA ANÁLISE (O back-end. Permanece o mesmo, pois já é otimizado)
# ========================================================================================
# (As funções `extrair_todos_poligonos_do_kmz`, `criar_ponto`, e `motor_analise_viabilidade`
#  devem ser coladas aqui. Para não deixar a resposta gigante, vou omiti-las,
#  mas elas são IDÊNTICAS à versão anterior que te passei.)
def extrair_todos_poligonos_do_kmz(arquivo_kmz, pasta_kmz, status_callback):
    basename = os.path.basename(arquivo_kmz).split('.')[0]
    temp_dir = os.path.join(pasta_kmz, "temp", basename)
    os.makedirs(temp_dir, exist_ok=True)
    caminho_kml = next((os.path.join(temp_dir, f) for f in os.listdir(temp_dir) if f.lower().endswith('.kml')), None)
    if not caminho_kml:
        try:
            with zipfile.ZipFile(arquivo_kmz, 'r') as kmz:
                kml_filename = next((f for f in kmz.namelist() if f.lower().endswith('.kml')), None)
                if not kml_filename: return None
                status_callback(f"Extraindo: '{os.path.basename(arquivo_kmz)}'...", None)
                caminho_kml = kmz.extract(kml_filename, path=temp_dir)
        except Exception as e:
            status_callback(f"Erro ao extrair '{arquivo_kmz}': {e}", None)
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
        return gpd.GeoDataFrame(pd.concat(lista_de_gdfs, ignore_index=True), crs="EPSG:4326")
    except Exception as e:
        status_callback(f"Erro ao ler KML '{caminho_kml}': {e}", None)
        return None

def criar_ponto(row, mode, col_lat, col_lon, col_coords):
    if mode == 'latlon':
        try:
            lon, lat = row[col_lon], row[col_lat]
            if pd.isna(lon) or pd.isna(lat) or lon == 0 or lat == 0:
                return None
            return Point(float(lon), float(lat))
        except (ValueError, TypeError):
            return None
    elif mode == 'coords':
        try:
            coords_str = row[col_coords]
            if pd.isna(coords_str) or coords_str == 0 or str(coords_str).strip() == '0':
                return None
            coords = str(coords_str).replace(" ", "").split(',')
            if len(coords) == 2:
                lat, lon = map(float, coords)
                if lat == 0 or lon == 0:
                    return None
                return Point(lon, lat)
        except (ValueError, TypeError, IndexError):
            return None
    return None

def motor_analise_viabilidade(pasta_kmz, arquivo_excel, raio_km, status_callback):
    try:
        RAIO_PROXIMIDADE_METROS = float(raio_km) * 1000
        CRS_GEOGRAFICO = "EPSG:4326"
        CRS_PROJETADO = "EPSG:5880"
        COLUNA_LATITUDE = 'LATITUDE'
        COLUNA_LONGITUDE = 'LONGITUDE'
        COLUNA_COORDENADAS = 'COORDENADAS'
        COLUNA_VELOCIDADE = 'VELOCIDADE'
        COLUNA_NOME_MANCHA = 'Name'
        status_callback("Iniciando análise...", 0)
        status_callback("Carregando arquivos KMZ...", 5)
        arquivos_kmz = [os.path.join(pasta_kmz, f) for f in os.listdir(pasta_kmz) if f.lower().endswith('.kmz')]
        if not arquivos_kmz:
            raise ValueError(f"Nenhum arquivo .kmz encontrado em '{pasta_kmz}'")
        lista_poligonos_gdfs = []
        for i, kmz_file in enumerate(arquivos_kmz):
            gdf_poligonos = extrair_todos_poligonos_do_kmz(kmz_file, pasta_kmz, status_callback)
            if gdf_poligonos is not None and not gdf_poligonos.empty:
                gdf_poligonos['Mancha'] = os.path.basename(kmz_file).split('.')[0]
                lista_poligonos_gdfs.append(gdf_poligonos)
            status_callback(f"Processando KMZ {i+1}/{len(arquivos_kmz)}...", 10 + int(20 * (i+1)/len(arquivos_kmz)))
        if not lista_poligonos_gdfs:
            raise ValueError("Nenhum polígono válido foi carregado dos arquivos KMZ.")
        gdf_manchas_global = gpd.GeoDataFrame(pd.concat(lista_poligonos_gdfs, ignore_index=True), crs=CRS_GEOGRAFICO)
        if COLUNA_NOME_MANCHA not in gdf_manchas_global.columns:
            gdf_manchas_global[COLUNA_NOME_MANCHA] = 'Nome não encontrado'
        else:
            gdf_manchas_global[COLUNA_NOME_MANCHA] = gdf_manchas_global[COLUNA_NOME_MANCHA].fillna('Nome não encontrado')
        status_callback("Lendo e validando arquivo Excel...", 30)
        df_pontos = pd.read_excel(arquivo_excel)
        modo_coordenadas = None
        if COLUNA_LATITUDE in df_pontos.columns and COLUNA_LONGITUDE in df_pontos.columns:
            modo_coordenadas = 'latlon'
        elif COLUNA_COORDENADAS in df_pontos.columns:
            modo_coordenadas = 'coords'
        else:
            raise ValueError(f"Nenhuma coluna de coordenada (LATITUDE/LONGITUDE ou COORDENADAS) encontrada no Excel.")
        status_callback("Validando coordenadas e criando geometrias...", 40)
        df_pontos['geometry'] = df_pontos.apply(lambda row: criar_ponto(row, modo_coordenadas, COLUNA_LATITUDE, COLUNA_LONGITUDE, COLUNA_COORDENADAS), axis=1)
        invalidos_mask = df_pontos['geometry'].isna()
        df_validos = df_pontos[~invalidos_mask].copy()
        resultados_geo = pd.DataFrame()
        if not df_validos.empty:
            gdf_pontos = gpd.GeoDataFrame(df_validos, geometry='geometry', crs=CRS_GEOGRAFICO)
            if COLUNA_VELOCIDADE in gdf_pontos.columns:
                gdf_pontos['velocidade_num'] = pd.to_numeric(gdf_pontos[COLUNA_VELOCIDADE].astype(str).str.extract(r'(\d+)')[0], errors='coerce').fillna(0)
            else:
                gdf_pontos['velocidade_num'] = 0
            status_callback("Analisando pontos DENTRO das manchas...", 50)
            gdf_dentro_bruto = gpd.sjoin(gdf_pontos, gdf_manchas_global, how="inner", predicate="within")
            gdf_dentro_agregado = pd.DataFrame()
            if not gdf_dentro_bruto.empty:
                gdf_dentro_bruto['Status Viabilidade'] = gdf_dentro_bruto.apply(lambda row: 'Viabilidade Expressa' if row.velocidade_num <= 500 else 'Verificar PTP', axis=1)
                gdf_dentro_bruto['Distância (metros)'] = 0
                agg_rules = {'Mancha': lambda x: ', '.join(x.unique()), COLUNA_NOME_MANCHA: lambda x: ', '.join(x.unique()), 'Status Viabilidade': 'first', 'Distância (metros)': 'first'}
                gdf_dentro_agregado = gdf_dentro_bruto.groupby(gdf_dentro_bruto.index).agg(agg_rules)
            status_callback("Analisando pontos PRÓXIMOS às manchas...", 70)
            indices_encontrados = gdf_dentro_agregado.index
            gdf_pontos_fora = gdf_pontos.drop(indices_encontrados)
            gdf_proximos_agregado = pd.DataFrame()
            if not gdf_pontos_fora.empty and RAIO_PROXIMIDADE_METROS > 0:
                gdf_pontos_proj = gdf_pontos_fora.to_crs(CRS_PROJETADO)
                gdf_manchas_proj = gdf_manchas_global.to_crs(CRS_PROJETADO)
                gdf_proximos_bruto = gpd.sjoin_nearest(gdf_pontos_proj, gdf_manchas_proj, max_distance=RAIO_PROXIMIDADE_METROS, how="inner")
                if not gdf_proximos_bruto.empty:
                    status_callback("Agregando resultados de proximidade...", 85)
                    nearest_polygons = gdf_manchas_proj.loc[gdf_proximos_bruto['index_right'], 'geometry']
                    aligned_polygons = gpd.GeoSeries(nearest_polygons.values, index=gdf_proximos_bruto.index, crs=CRS_PROJETADO)
                    gdf_proximos_bruto['Distância (metros)'] = gdf_proximos_bruto.geometry.distance(aligned_polygons)
                    gdf_proximos_bruto['Status Viabilidade'] = 'Próximo à mancha'
                    agg_rules_prox = {'Mancha': lambda x: ', '.join(x.unique()), COLUNA_NOME_MANCHA: lambda x: ', '.join(x.unique()),'Status Viabilidade': 'first', 'Distância (metros)': 'min'}
                    gdf_proximos_agregado = gdf_proximos_bruto.groupby(gdf_proximos_bruto.index).agg(agg_rules_prox)
                    gdf_proximos_agregado['Distância (metros)'] = round(gdf_proximos_agregado['Distância (metros)'], 2)
            resultados_geo = pd.concat([gdf_dentro_agregado, gdf_proximos_agregado]).rename(columns={COLUNA_NOME_MANCHA: 'Nome da Mancha'})
        status_callback("Montando relatório final...", 95)
        df_final = df_pontos.merge(resultados_geo, left_index=True, right_index=True, how="left")
        df_final.loc[invalidos_mask, 'Status Viabilidade'] = 'Coordenada Inválida'
        df_final.fillna({'Status Viabilidade': 'Inviável'}, inplace=True)
        df_final[['Mancha', 'Nome da Mancha']] = df_final[['Mancha', 'Nome da Mancha']].fillna('---')
        df_final = df_final.drop(columns=['geometry'], errors='ignore')
        resumo = df_final['Status Viabilidade'].value_counts().to_dict()
        resumo['Total de Pontos Verificados'] = len(df_pontos)
        status_callback("Análise Concluída!", 100)
        return df_final, resumo
    except Exception as e:
        return None, str(e)


# ========================================================================================
#  PARTE 2: A NOVA INTERFACE GRÁFICA (FRONT-END MODERNO)
# ========================================================================================

customtkinter.set_appearance_mode("Light") # "System", "Dark", "Light"

class App(customtkinter.CTk):
    def __init__(self):
        super().__init__()

        # --- Paleta de Cores e Estilo ---
        self.COLOR_PRIMARY = "#0d6efd"
        self.COLOR_SECONDARY = "#6c757d"
        self.COLOR_BACKGROUND = "#f4f7f6"
        self.COLOR_CARD = "#ffffff"
        self.COLOR_TEXT_DARK = "#343a40"
        self.COLOR_TEXT_MUTED = "#8692a6"
        self.COLOR_BORDER = "#e9ecef"
        
        # --- Configuração da Janela ---
        self.title("Analisador de Viabilidade Geoespacial")
        self.geometry("850x650")
        self.minsize(800, 600)
        self.configure(fg_color=self.COLOR_BACKGROUND)

        # --- Variáveis de estado ---
        self.kmz_folder_path = ""
        self.excel_file_path = ""
        self.final_df = None

        # --- Layout Principal ---
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)
        
        self.tab_view = customtkinter.CTkTabview(self,
            fg_color=self.COLOR_CARD,
            segmented_button_selected_color=self.COLOR_PRIMARY,
            segmented_button_unselected_color=self.COLOR_CARD,
            segmented_button_fg_color=self.COLOR_CARD
        )
        self.tab_view.grid(row=0, column=0, padx=20, pady=20, sticky="nsew")

        # --- MUDANÇA CRÍTICA: Criamos APENAS a primeira aba ---
        self.tab_view.add("1. Configuração")
        self.tab_view.set("1. Configuração")

        # --- Cria os widgets dentro da aba de configuração ---
        self.create_config_tab()

    def create_config_tab(self):
        config_tab = self.tab_view.tab("1. Configuração")
        config_tab.grid_columnconfigure(0, weight=1)

        # Frame de Título
        title_frame = customtkinter.CTkFrame(config_tab, fg_color="transparent")
        title_frame.grid(row=0, column=0, padx=40, pady=(20, 10), sticky="ew")
        customtkinter.CTkLabel(title_frame, text="Preparar Análise", font=("Roboto", 24, "bold"), text_color=self.COLOR_TEXT_DARK).pack(anchor="w")
        customtkinter.CTkLabel(title_frame, text="Selecione os arquivos e defina o raio para iniciar", font=("Roboto", 14), text_color=self.COLOR_TEXT_MUTED).pack(anchor="w")

        # Frame de Inputs
        inputs_frame = customtkinter.CTkFrame(config_tab, fg_color="transparent")
        inputs_frame.grid(row=1, column=0, padx=40, pady=20, sticky="nsew")
        inputs_frame.grid_columnconfigure(1, weight=1)

        # Input Pasta KMZ
        self.kmz_button = customtkinter.CTkButton(inputs_frame, text="📁  Selecionar Pasta KMZ", command=self.select_kmz_folder, fg_color=self.COLOR_SECONDARY, height=40, font=("Roboto", 14))
        self.kmz_button.grid(row=0, column=0, pady=10, sticky="w")
        self.kmz_label = customtkinter.CTkLabel(inputs_frame, text="Nenhuma pasta selecionada", text_color=self.COLOR_TEXT_MUTED, wraplength=450, justify="left")
        self.kmz_label.grid(row=0, column=1, padx=20, sticky="w")
        
        # Input Arquivo Excel
        self.excel_button = customtkinter.CTkButton(inputs_frame, text="📄  Selecionar Arquivo Excel", command=self.select_excel_file, fg_color=self.COLOR_SECONDARY, height=40, font=("Roboto", 14))
        self.excel_button.grid(row=1, column=0, pady=10, sticky="w")
        self.excel_label = customtkinter.CTkLabel(inputs_frame, text="Nenhum arquivo selecionado", text_color=self.COLOR_TEXT_MUTED, wraplength=450, justify="left")
        self.excel_label.grid(row=1, column=1, padx=20, sticky="w")

        # Input Raio
        customtkinter.CTkLabel(inputs_frame, text="Raio de Proximidade (km):", font=("Roboto", 14, "bold"), text_color=self.COLOR_TEXT_DARK).grid(row=2, column=0, pady=(20, 10), sticky="w")
        self.radius_entry = customtkinter.CTkEntry(inputs_frame, placeholder_text="Ex: 1.5 (padrão é 0)", width=200, height=40, border_color=self.COLOR_BORDER)
        self.radius_entry.grid(row=2, column=1, pady=(20, 10), sticky="w", padx=20)
        
        # Botão de Ação
        self.run_button = customtkinter.CTkButton(config_tab, text="Iniciar Análise", command=self.start_analysis_thread, height=50, font=("Roboto", 18, "bold"), fg_color=self.COLOR_PRIMARY)
        self.run_button.grid(row=2, column=0, padx=40, pady=(20, 40), sticky="ew")

    def create_results_tab(self):
        # Esta função agora é chamada sob demanda
        results_tab = self.tab_view.tab("2. Resultados")
        results_tab.grid_columnconfigure(0, weight=1)
        results_tab.grid_rowconfigure(1, weight=1)

        # Status Label e Progress Bar
        self.status_label = customtkinter.CTkLabel(results_tab, text="", text_color=self.COLOR_TEXT_DARK, font=("Roboto", 14))
        self.status_label.grid(row=0, column=0, padx=20, pady=(20,15), sticky="ew")
        self.progress_bar = customtkinter.CTkProgressBar(results_tab, progress_color=self.COLOR_PRIMARY)
        self.progress_bar.set(0)
        self.progress_bar.grid(row=0, column=0, padx=20, pady=(50, 20), sticky="ew")
        
        # Caixa de Texto para Resumo
        self.summary_textbox = customtkinter.CTkTextbox(results_tab, wrap="word", font=("Courier New", 13), border_spacing=10, fg_color=self.COLOR_BACKGROUND)
        self.summary_textbox.grid(row=1, column=0, padx=20, pady=10, sticky="nsew")
        self.summary_textbox.configure(state="disabled")

        # Botão para Salvar
        self.save_button = customtkinter.CTkButton(results_tab, text="Salvar Relatório Excel...", command=self.save_results, height=50, font=("Roboto", 16, "bold"), state="disabled", fg_color=self.COLOR_SECONDARY)
        self.save_button.grid(row=2, column=0, padx=20, pady=20, sticky="ew")

    def start_analysis_thread(self):
        # Lógica para reiniciar a análise se o botão for "Iniciar Nova Análise"
        if self.run_button.cget("text") == "Iniciar Nova Análise":
            # Limpa os inputs para uma nova rodada
            self.kmz_folder_path = self.kmz_folder_path
            self.excel_file_path = ""
            if self.kmz_folder_path == "":
                self.kmz_label.configure(text="Nenhuma pasta selecionada", text_color=self.COLOR_TEXT_MUTED)
            
            self.excel_label.configure(text="Nenhum arquivo selecionado", text_color=self.COLOR_TEXT_MUTED)
            self.final_df = None
            self.run_button.configure(text="Iniciar Análise")
            # Remove a aba de resultados e volta para a configuração
            if "2. Resultados" in self.tab_view._name_list:
                self.tab_view.delete("2. Resultados")
            self.tab_view.set("1. Configuração")
            return

        # Validação normal
        if not self.kmz_folder_path or not self.excel_file_path:
            tkinter.messagebox.showwarning("Entradas Faltando", "Por favor, selecione a pasta KMZ e o arquivo Excel.")
            return
        
        radius_str = self.radius_entry.get()
        if not radius_str:
            radius_km = 0.0
        else:
            try:
                radius_km = float(radius_str.replace(",", "."))
            except ValueError:
                tkinter.messagebox.showerror("Entrada Inválida", "O valor do Raio de Proximidade deve ser um número.")
                return

        self.run_button.configure(state="disabled", text="Processando...")
        
        # --- MUDANÇA CRÍTICA: Adiciona e cria a aba de resultados dinamicamente ---
        if "2. Resultados" not in self.tab_view._name_list:
            self.tab_view.add("2. Resultados")
            self.create_results_tab() # Popula a nova aba com os widgets
        
        self.tab_view.set("2. Resultados") # Muda o foco para a nova aba

        analysis_thread = threading.Thread(target=self.run_analysis, args=(self.kmz_folder_path, self.excel_file_path, radius_km))
        analysis_thread.start()

    # --- O resto das funções (`select_...`, `update_status`, `run_analysis`, `analysis_finished`, `save_results`) permanecem idênticas à versão anterior ---
    def select_kmz_folder(self):
        folder_selected = filedialog.askdirectory(title="Selecione a pasta com os arquivos KMZ")
        if folder_selected:
            self.kmz_folder_path = folder_selected
            self.kmz_label.configure(text=folder_selected, text_color=self.COLOR_TEXT_DARK)

    def select_excel_file(self):
        file_selected = filedialog.askopenfilename(title="Selecione a planilha Excel", filetypes=(("Excel Files", "*.xlsx"), ("All files", "*.*")))
        if file_selected:
            self.excel_file_path = file_selected
            self.excel_label.configure(text=file_selected, text_color=self.COLOR_TEXT_DARK)

    def update_status(self, message, progress):
        self.status_label.configure(text=message)
        if progress is not None:
            self.progress_bar.set(progress / 100)
        self.update_idletasks()
        
    def run_analysis(self, kmz_path, excel_path, radius_km):
        self.final_df, summary_or_error = motor_analise_viabilidade(
            pasta_kmz=kmz_path, arquivo_excel=excel_path, raio_km=radius_km,
            status_callback=lambda msg, prog: self.after(0, self.update_status, msg, prog)
        )
        self.after(0, self.analysis_finished, summary_or_error)

    def analysis_finished(self, summary_or_error):
        self.summary_textbox.configure(state="normal")
        self.summary_textbox.delete("0.0", "end")

        if self.final_df is not None:
            header = " RESUMO DA ANÁLISE "
            formatted_summary = f"{header:=^60}\n\n"
            for key, value in summary_or_error.items():
                formatted_summary += f"{key:<40}: {value}\n"
            self.summary_textbox.insert("0.0", formatted_summary)
            self.save_button.configure(state="normal", fg_color=self.COLOR_PRIMARY)
        else:
            error_message = f" OCORREU UM ERRO DURANTE A ANÁLISE \n\n{summary_or_error}"
            self.summary_textbox.insert("0.0", error_message)
            tkinter.messagebox.showerror("Erro na Análise", summary_or_error)

        self.summary_textbox.configure(state="disabled")
        self.run_button.configure(state="normal", text="Iniciar Nova Análise")
        
    def save_results(self):
        if self.final_df is not None:
            id_unico = uuid.uuid4().hex[:12]
            save_path = filedialog.asksaveasfilename(
                defaultextension=".xlsx", filetypes=(("Excel Files", "*.xlsx"),),
                initialfile=f"resultado_viabilidade-{id_unico}.xlsx"
            )
            if save_path:
                try:
                    self.update_status(f"Salvando relatório...", None)
                    self.final_df.to_excel(save_path, index=False, engine='openpyxl')
                    tkinter.messagebox.showinfo("Sucesso", f"Relatório salvo com sucesso em:\n{save_path}")
                except Exception as e:
                    tkinter.messagebox.showerror("Erro ao Salvar", f"Não foi possível salvar o arquivo.\nErro: {e}")
                finally:
                    self.update_status("Aguardando nova análise.", 0)

""" Header no CMD """
def print_header(name, author, version, license):
    """
    Imprime um cabeçalho estilizado e profissional no console.
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


if __name__ == "__main__":
    
    # Imprime o cabeçalho no início
    print_header(__name, __author, __version, __license)
    
    app = App()
    app.mainloop()