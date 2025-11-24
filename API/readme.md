# 🌍 Analisador de Viabilidade Geoespacial (API REST)

## 1. Visão Geral

Uma solução robusta e de alto desempenho para análise de viabilidade técnica em telecomunicações. O sistema processa arquivos em massa (Excel) para verificar a cobertura baseada em polígonos (KMZ) e proximidade de redes PTP armazenadas em banco de dados espacial (MySQL), com fallback inteligente e processamento paralelo.

### 🚀 Funcionalidades Principais

#### 1. Motor de Análise Híbrida & Paralela

O sistema opera com uma lógica de decisão inteligente e multithreading para máxima performance:

- **Verificação GPON (Polígonos):** Verifica se a coordenada está DENTRO de uma mancha (arquivo KMZ).

- **Verificação de Proximidade (KMZ):** Se não estiver dentro, verifica se está no raio de borda da mancha.

- **Fallback PTP (Banco de Dados):** Se não houver cobertura GPON, o sistema consulta automaticamente o banco de dados MySQL (usando índices espaciais) para encontrar redes de rádio (PTP) próximas.

- **Processamento Paralelo:** Utiliza `ThreadPoolExecutor` para realizar milhares de consultas espaciais simultaneamente sem travar a aplicação.

#### 2. API RESTful Assíncrona

- **Feedback em Tempo Real:** Endpoints utilizam Server-Sent Events (SSE) para transmitir o progresso da análise e logs para o frontend em tempo real.

- **Endpoints de CRUD:** Gestão completa de redes PTP (Criar, Ler, Atualizar, Deletar) via API.

- **Autocomplete:** Busca inteligente de cidades baseada na base do IBGE.

- **Gestão de Arquivos:** Endpoints seguros para download e exclusão de relatórios gerados.

#### 3. Frontend & Administração

- **Exemplo de Integração:** Inclui `frontend_example.html` e `ptp_admin.html` demonstrando como consumir a API.

- **Interface Administrativa:** Painel completo com Bootstrap 5 para gerenciar redes PTP e visualizar análises.

## 🛠️ Arquitetura do Projeto

A estrutura segue os padrões modernos de desenvolvimento FastAPI:

```
analisador_geo_api/
├── api/
│   ├── core/
│   │   ├── analysis.py       # Motor de Análise (Pandas/GeoPandas + Threading)
│   │   ├── database.py       # Gerenciador de Conexão MySQL (Pooling)
│   │   ├── excel_styler.py   # Formatação automática de relatórios Excel
│   │   ├── settings.py       # Carregamento de configurações (.env)
│   │   └── models/
│   │       └── ptp_model.py  # DAO (Data Access Object) para Redes e Cidades
│   ├── migrations/           # Scripts SQL para versionamento do banco
│   ├── schemas/
│   │   └── models.py         # Schemas Pydantic (Validação de Dados)
│   ├── static/               # Arquivos estáticos (HTML/JS de administração)
│   └── main.py               # Entrypoint da API (Rotas e Configuração)
│
├── kmzs/                     # Pasta para arquivos .kmz de cobertura
├── results/                  # Armazenamento de relatórios gerados
├── uploads/                  # Área temporária para upload
├── requirements.txt          # Dependências do Python
├── .env                      # Variáveis de ambiente (Configuração Sensível)
└── start_api.bat             # Script de inicialização rápida
```

## ⚙️ Instalação e Configuração

#### 1. Pré-requisitos
- **Python 3.9+**
- **Pip (gerenciador de pacotes Python)**
- **MySQL 8.0+ (Obrigatório para suporte a funções espaciais ST_Distance_Sphere)**

#### 2. Instalação

```
# Clone o repositório
git clone https://github.com/valdean132/analisador_geoespacial.git
cd analisador_geoespacial

# Crie o ambiente virtual
python -m venv .venv

# Ative o ambiente
# Windows:
.venv\Scripts\activate
# Linux/Mac:
source .venv/bin/activate

# Instale as dependências
pip install -r requirements.txt
```

#### 3. Configuração do Banco de Dados

Execute os scripts SQL na pasta `api/migrations/` na ordem para criar a estrutura do banco:

- `001_create_estados.sql`

- `002_create_municipios.sql`

- `003_create_redes_ptp.sql`

#### 4. Arquivo .env

Crie um arquivo `.env` na raiz baseado no `env.example`:

``` venv
# API
API_TITLE="Analisador de Viabilidade Geoespacial API"
API_VERSION="3.3.0"
DEBUG=false

# CORS (Segurança)
CORS_ORIGINS=*,http://localhost:3000

# Banco de Dados
DB_HOST=localhost
DB_PORT=3306
DB_USER=root
DB_PASS=sua_senha
DB_NAME=analysis_db
DB_POOL_SIZE=5        # Conexões simultâneas
DB_POOL_RECYCLE=280   # Tempo de renovação (segundos)

# Configurações de Análise
MAX_UPLOAD_SIZE_MB=50
ALLOWED_EXTENSIONS=xlsx
```

## ▶️ Como Executar

**Modo Fácil (Windows)**

Dê um duplo clique no arquivo start_api.bat. Ele ativará o ambiente e subirá o servidor automaticamente.

**Modo Manual (Terminal)**
```Bash
uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
```
Após iniciar, acesse:

- **Documentação Interativa**: `http://localhost:8000/docs`

- **Admin PTP:** `http://localhost:8000/static/ptp_admin.html` (se servido estaticamente) ou abra o arquivo localmente.

## 📡 Documentação da API (Endpoints)

#### **🔍 Análise**

`POST /analyze/`
Envia um arquivo Excel para processamento. Retorna um stream de eventos (SSE).

```csv
Parâmetro      Tipo      Descrição                                 Padrão
file           File      Arquivo .xlsx com pontos.                 -
raio_km        Float     Raio de busca em km.                      0.0
coordenadas    String    "Nome das colunas (ex: ""LAT, LON"")."    -
type_busca     Int       "1=Só PTP, 2=Só GPON, 3=Híbrido."         3
```

**Resposta (Stream SSE):**

```json
data: {"progress": 50, "message": "Analisando pontos DENTRO das manchas..."}
...
data: {"status": "complete", "summary": {...}, "result_id": "uuid..."}
```

#### **📂 Gestão de Arquivos**

`GET /download/{result_id}`
Baixa o relatório gerado.

`GET /delete/{result_id}`
Remove o relatório do servidor. Retorna confirmação via SSE.

#### **📡 Redes PTP (CRUD)**
Endpoints para integração com o painel administrativo.

- `GET /ptp/find:` Busca rede mais próxima por lat/lon.
- `GET /ptp/list:` Lista paginada de todas as redes.
- `GET /ptp/municipios/search:` Autocomplete de cidades.
- `POST /ptp/create:` Cadastra nova rede vinculada a uma cidade.
- `POST /ptp/update:` Atualiza nome da rede.
- `POST /ptp/delete:` Remove uma rede.

#### **📝 Autores**
- [Valdean P. Souza](https://www.github.com/valdean132)
- Gilmar Batista

#### **📝 Versão e licença**
- *Versão: 3.3.0*
- *Licença: [CC BY-ND 4.0](https://creativecommons.org/licenses/by-nd/4.0/)*