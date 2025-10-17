# Analisador de Viabilidade Geoespacial

## Autores

- [Valdean P. Souza](https://www.github.com/valdean132)
- Gilmar Batista

## Versão e licença
- *Versão: 3.0.0*
- *Licença: [CC BY-ND 4.0](https://creativecommons.org/licenses/by-nd/4.0/)*

## 1. Visão Geral

Este projeto automatiza a análise de viabilidade de uma lista de pontos geográficos (coordenadas) em relação a um conjunto de áreas de cobertura (polígonos) fornecidas em arquivos KMZ.

O objetivo principal é determinar, para cada ponto, se ele está:
- **Dentro** de uma ou mais áreas de cobertura.
- **Próximo** a uma área de cobertura (dentro de um raio configurável).
- **Inviável** (fora de qualquer área e do raio de proximidade).
- Possui uma **Coordenada Inválida** (dados ausentes, nulos, 0 ou mal formatados).

O projeto oferece duas formas de uso: uma **interface gráfica moderna (GUI)** para facilidade de uso e um **script de linha de comando** para automação e processamento em lote.

## 2. Principais Funcionalidades

- **Múltiplos Arquivos KMZ**: Processa e consolida polígonos de múltiplos arquivos `.kmz` de uma só vez.
- **Validação de Dados**: Valida rigorosamente as coordenadas de entrada, tratando células vazias, valores zero e formatos incorretos.
- **Hierarquia de Coordenadas**: Procura primeiro por colunas `LATITUDE`/`LONGITUDE` e, se não as encontrar, procura por uma coluna `COORDENADAS` (formato "lat, lon").
- **Agregação de Resultados**: Se um ponto for encontrado dentro ou próximo de múltiplas áreas, o script consolida os resultados em uma única linha, listando todas as manchas encontradas.
- **Cálculo de Proximidade Preciso**: Utiliza projeção cartográfica adequada para o Brasil (SIRGAS 2000) para calcular distâncias em metros.
- **Relatório Detalhado**: Gera um arquivo Excel de saída com os dados originais enriquecidos com o status da viabilidade, o nome da(s) mancha(s) e a distância.

## 3. Estrutura de Arquivos e Pastas

Para que o projeto funcione corretamente, a seguinte estrutura deve ser respeitada:

```
analisador_geoespacial/
├── .venv/                      # Pasta do ambiente virtual Python.
├── kmzs/                       # Pasta para colocar todos os arquivos .kmz de análise.
│   ├── area_cobertura_A.kmz
│   └── ...
├── resultados/                 # Pasta onde os relatórios serão salvos.
├── app_gui.py                  # A aplicação com interface gráfica (GUI).
├── analisar_viabilidade.py     # O script original para execução via linha de comando.
├── Analizador GeoEspacial.bat  # Lançador com menu para Windows.
├── requirements.txt            # Lista de dependências do projeto.
└── verificar_viabilidade.xlsx  # Planilha de exemplo com os pontos a serem analisados.
```

## 4. Configuração

### Para a Aplicação com Interface Gráfica (`app_gui.py`)
Toda a configuração, como a seleção da pasta KMZ, do arquivo Excel e a definição do raio de proximidade, é feita **diretamente na interface do programa**. Não é necessário editar o código.

### Para a Versão de Linha de Comando (`analisar_viabilidade.py`)
As configurações de arquivos e nomes de colunas são definidas como constantes no início do script. Você pode editá-las diretamente no arquivo, se necessário:
- `PASTA_DOS_KMZ`: Nome da pasta que contém os arquivos `.kmz`.
- `ARQUIVO_EXCEL_PONTOS`: Nome da planilha de entrada.
- `RAIO_PROXIMIDADE_METROS`: Distância em metros para considerar um ponto como "próximo".

## 5. Instalação de Dependências

Antes de executar, você precisa instalar as bibliotecas Python necessárias.

1.  **Crie e ative um ambiente virtual** (altamente recomendado):
    ```bash
    python -m venv .venv
    # No Windows, ative com:
    .venv\Scripts\activate
    ```
2.  **Instale as dependências** a partir do arquivo `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

## 6. Como Executar

Existem três maneiras de executar a ferramenta, da mais fácil à mais avançada.

### Método 1: Usando o Lançador `Analizador GeoEspacial.bat` (Recomendado para Windows)
Este é o método mais simples e não requer o uso do terminal.

1.  Dê um duplo-clique no arquivo `Analizador GeoEspacial.bat`.
2.  Um menu aparecerá na tela de comando.
3.  Digite `1` e pressione `Enter` para abrir a **aplicação com interface gráfica**.
4.  Digite `2` e pressione `Enter` para executar a **análise via linha de comando** (usará os arquivos configurados no script `analisar_viabilidade.py`).

### Método 2: Executando a Interface Gráfica Diretamente
Se você não quiser usar o `.bat`, pode iniciar a interface gráfica diretamente.

1.  Abra um terminal (CMD, PowerShell, etc.) e ative o ambiente virtual (`.venv\Scripts\activate`).
2.  Execute o seguinte comando:
    ```bash
    python app_gui.py
    ```
3.  A janela da aplicação será aberta.

### Método 3: Executando via Linha de Comando (Avançado)
Este método é útil para automação ou se você prefere usar o terminal.

1.  Certifique-se de que os arquivos de entrada (`verificar_viabilidade.xlsx` e os `.kmz`) estão nas pastas corretas e configurados dentro do script `analisar_viabilidade.py`.
2.  Abra um terminal e ative o ambiente virtual.
3.  Execute o seguinte comando:
    ```bash
    python analisar_viabilidade.py
    ```
4.  Aguarde o processamento. O progresso será exibido no terminal e o arquivo de resultado será salvo na pasta `resultados`.

## 7. Entendendo o Arquivo de Saída

O arquivo Excel gerado conterá todas as colunas do seu arquivo original, mais as seguintes colunas de análise:

- **`Status Viabilidade`**: O resultado da análise. Pode ser:
    - `Viabilidade Expressa`: O ponto está dentro de uma mancha e a velocidade é <= 500.
    - `Verificar PTP`: O ponto está dentro de uma mancha e a velocidade é > 500.
    - `Próximo à mancha`: O ponto está fora de uma mancha, mas dentro do raio de proximidade definido.
    - `Inviável`: O ponto não está dentro nem próximo de nenhuma mancha.
    - `Coordenada Inválida`: A coordenada na planilha original estava vazia, continha o valor 0 ou estava mal formatada.
- **`Mancha`**: O nome do arquivo KMZ (sem a extensão) onde a correspondência foi encontrada. Se houver múltiplas, serão separadas por vírgula.
- **`Nome da Mancha`**: O nome específico do polígono (da coluna `Name` do KMZ) onde a correspondência foi encontrada. Se houver múltiplas, serão separadas por vírgula.
- **`Distância (metros)`**: A distância em metros até a borda do polígono mais próximo. Será `0` para pontos que estão dentro da mancha.