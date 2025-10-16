# Analisador de Viabilidade Geoespacial

## Autores

- [Valdean P. Souza](https://www.github.com/valdean132)
- [Gilmar Batista]()

## Versão e licença
- *Versão: 1.2.0*
- *Licença: [CC BY-ND](https://creativecommons.org/licenses/by-nd/4.0/)*

## 1. Visão Geral

Este script automatiza a análise de viabilidade de uma lista de pontos geográficos (coordenadas) em relação a um conjunto de áreas de cobertura (polígonos) fornecidas em arquivos KMZ.

O objetivo principal é determinar, para cada ponto, se ele está:
- **Dentro** de uma ou mais áreas de cobertura.
- **Próximo** a uma área de cobertura (dentro de um raio configurável).
- **Inválável** (fora de qualquer área e do raio de proximidade).
- Possui uma **Coordenada Inválida** (dados ausentes, nulos, 0 ou mal formatados).

## 2. Principais Funcionalidades

- **Múltiplos Arquivos KMZ**: Processa e consolida polígonos de múltiplos arquivos `.kmz` de uma só vez.
- **Validação de Dados**: Valida rigorosamente as coordenadas de entrada, tratando células vazias, valores zero e formatos incorretos.
- **Hierarquia de Coordenadas**: Procura primeiro por colunas `LATITUDE`/`LONGITUDE` e, se não as encontrar, procura por uma coluna `COORDENADAS` (formato "lat, lon").
- **Agregação de Resultados**: Se um ponto for encontrado dentro ou próximo de múltiplas áreas, o script consolida os resultados em uma única linha, listando todas as manchas encontradas e evitando a duplicação de dados.
- **Cálculo de Proximidade**: Utiliza projeção cartográfica adequada para o Brasil (SIRGAS 2000) para calcular distâncias em metros com alta precisão.
- **Relatório Detalhado**: Gera um arquivo Excel de saída com os dados originais enriquecidos com o status da viabilidade, o nome da(s) mancha(s) e a distância.
- **Saída com ID Único**: Salva cada relatório com um identificador único para evitar a sobreescrita de análises anteriores.

## 3. Estrutura de Arquivos e Pastas

Para que o script funcione corretamente, a seguinte estrutura de diretórios e arquivos deve ser respeitada:

```
seu_projeto/
├── kmzs/                  # Pasta para colocar todos os arquivos .kmz
│   ├── area_cobertura_A.kmz
│   └── area_cobertura_B.kmz
├── resultados/            # Pasta onde os relatórios serão salvos (deve ser criada)
├── verificar_viabilidade.xlsx  # Planilha com os pontos a serem analisados
└── analisar_viabilidade.py     # Este script
```

## 4. Configuração do Script

Todas as configurações são feitas no início do arquivo `analisar_viabilidade.py`.

- `PASTA_DOS_KMZ`: Nome da pasta que contém os arquivos `.kmz`. (Padrão: `'kmzs'`)
- `ARQUIVO_EXCEL_PONTOS`: Nome da planilha de entrada. (Padrão: `'verificar_viabilidade.xlsx'`)
- `ARQUIVO_EXCEL_SAIDA`: Define o padrão de nome para o arquivo de saída. Já configurado para gerar um nome único.
- `COLUNA_LATITUDE`, `COLUNA_LONGITUDE`, `COLUNA_COORDENADAS`: Nomes exatos das colunas na sua planilha Excel.
- `COLUNA_VELOCIDADE`: Nome da coluna de velocidade (usada para diferenciar 'Viabilidade Expressa' de 'Verificar PTP').
- `COLUNA_NOME_MANCHA`: Nome da coluna dentro do arquivo KMZ que identifica cada polígono (geralmente `'Name'`).
- `RAIO_PROXIMIDADE_METROS`: Distância em metros para considerar um ponto como "próximo".

## 5. Instalação de Dependências

Antes de executar, você precisa instalar as bibliotecas Python necessárias. Um arquivo `requirements.txt` é fornecido. Para instalar, execute o seguinte comando no seu terminal:

```bash
pip install -r requirements.txt
```

**Nota:** A instalação de bibliotecas geoespaciais como o `geopandas` pode ser complexa. O uso de um ambiente virtual (como `venv`) é fortemente recomendado. Em alguns sistemas, pode ser mais fácil instalar usando `conda`.

## 6. Como Executar

1.  Certifique-se de que a estrutura de pastas está correta e os arquivos de entrada estão nos locais certos.
2.  Abra um terminal ou prompt de comando no diretório do projeto.
3.  Execute o script com o seguinte comando:

```bash
python analisar_viabilidade.py
```

4.  Aguarde o processamento. O script exibirá o progresso no terminal.
5.  Ao final, o arquivo de resultado será salvo na pasta `resultados`.

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