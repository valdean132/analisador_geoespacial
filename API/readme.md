# Analisador de Viabilidade Geoespacial - API REST

## 1. Visão Geral

Esta API fornece uma interface RESTful para a ferramenta de análise de viabilidade geoespacial. Ela permite que sistemas externos e interfaces de usuário enviem arquivos de pontos (em formato `.xlsx`) para serem analisados em relação a um conjunto de áreas de cobertura (polígonos) definidas em arquivos `.kmz`.

A API foi construída com **FastAPI**, garantindo alta performance, processamento assíncrono e documentação interativa automática.

### Principais Funcionalidades

- **Endpoint de Análise Assíncrono**: Inicia a análise e retorna um stream de atualizações de progresso em tempo real usando Server-Sent Events (SSE).
- **Feedback em Tempo Real**: Permite que o cliente (frontend) exiba logs de processo e uma barra de progresso que é atualizada à medida que a análise avança.
- **Endpoint de Download**: Fornece um endpoint seguro para baixar o arquivo Excel com os resultados após a conclusão da análise.
- **Arquitetura Orientada a Objetos**: A lógica de negócio é encapsulada em uma classe `GeoAnalyzer`, promovendo um código limpo, modular e reutilizável.
- **Documentação Automática**: Gera automaticamente uma documentação interativa da API (Swagger UI e ReDoc).

## 2. Estrutura do Projeto

O projeto está organizado da seguinte forma para garantir a separação de responsabilidades:

```
analisador_geo_api/
├── api/
│   ├── core/
│   │   └── analysis.py      # A classe GeoAnalyzer com toda a lógica da análise.
│   ├── schemas/
│   │   └── models.py        # Modelos de dados Pydantic para validação e serialização.
│   ├── main.py              # Arquivo principal da API (endpoints, configuração).
│   ├── uploads/             # Diretório temporário para arquivos .xlsx enviados.
│   └── results/             # Diretório para armazenar os relatórios .xlsx gerados.
│
├── kmzs/                    # Pasta onde os arquivos .kmz de cobertura devem ser colocados.
│   ├── mancha_A.kmz
│   └── mancha_B.kmz
│
├── frontend_example.html    # Um cliente web simples para testar a API.
├── requirements.txt         # Lista de dependências Python.
└── README.md                # Esta documentação.
```

## 3. Instalação

**Pré-requisitos**:
- Python 3.9 ou superior
- Pip (gerenciador de pacotes Python)

**Passos**:

1.  **Clone o repositório** (ou crie a estrutura de pastas e arquivos conforme descrito acima).

2.  **Crie e ative um ambiente virtual** (altamente recomendado):
    ```bash
    python -m venv .venv
    # No Windows
    .venv\Scripts\activate
    # No macOS/Linux
    source .venv/bin/activate
    ```

3.  **Instale as dependências** a partir do arquivo `requirements.txt`:
    ```bash
    pip install -r requirements.txt
    ```

4.  **Popule a pasta `kmzs/`** com todos os arquivos de mancha de cobertura `.kmz` que você usará para a análise.

## 4. Como Executar a API

Com as dependências instaladas, você pode iniciar o servidor da API.

1.  Navegue até o diretório raiz do projeto (`analisador_geo_api/`) no seu terminal.

2.  Execute o servidor Uvicorn:
    ```bash
    uvicorn api.main:app --reload
    ```
    - `api.main:app`: Indica ao Uvicorn para encontrar o objeto `app` dentro do arquivo `api/main.py`.
    - `--reload`: Reinicia o servidor automaticamente sempre que você fizer alterações no código, ideal para desenvolvimento.

3.  O servidor estará rodando em `http://127.0.0.1:8000`.

## 5. Endpoints da API

A API expõe dois endpoints principais:

---

### `POST /analyze/`

Inicia um processo de análise. Este endpoint recebe os dados como `multipart/form-data`.

- **Parâmetros**:
  - `raio_km` (float, *form-data*): O raio de proximidade em quilômetros. Padrão é `0.0`.
  - `file` (file, *form-data*): O arquivo `.xlsx` contendo a lista de pontos a serem analisados.

- **Resposta**:
  - `200 OK`: Retorna um `StreamingResponse` com `Content-Type: text/event-stream`. Os eventos são objetos JSON com o progresso da análise.

- **Fluxo de Eventos (SSE)**:
  - **Eventos de Progresso**:
    ```json
    {"progress": 25, "message": "Processando KMZ 2/5"}
    ```
  - **Evento de Erro**:
    ```json
    {"status": "error", "message": "Nenhum polígono válido foi carregado..."}
    ```
  - **Evento Final de Sucesso**:
    ```json
    {
      "status": "complete",
      "summary": {
        "Viabilidade Expressa": 150,
        "Inviável": 80,
        "Coordenada Inválida": 5
      },
      "result_id": "a1b2c3d4-e5f6-..."
    }
    ```

---

### `GET /download/{result_id}`

Baixa o arquivo Excel com o resultado completo da análise.

- **Parâmetros**:
  - `result_id` (string, *path*): O ID único retornado no evento final do endpoint `/analyze/`.

- **Resposta**:
  - `200 OK`: Retorna o arquivo `.xlsx` (`Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet`).
  - `404 Not Found`: Se o `result_id` for inválido ou o arquivo não existir mais.

---

## 6. Documentação Interativa (Swagger UI)

Com o servidor rodando, acesse `http://127.0.0.1:8000/docs` no seu navegador.

Você encontrará uma interface Swagger UI completa onde pode:
- Visualizar todos os endpoints e seus detalhes.
- Ver os modelos de dados (schemas).
- **Testar a API diretamente pelo navegador**, enviando arquivos e parâmetros e vendo as respostas em tempo real.

## 7. Usando o Cliente de Exemplo

O arquivo `frontend_example.html` é uma página web autônoma que consome a API.

1.  Certifique-se de que o servidor da API está rodando.
2.  Abra o arquivo `frontend_example.html` diretamente em um navegador web (ex: Chrome, Firefox).
3.  Use a interface para selecionar um arquivo `.xlsx` e definir o raio.
4.  Clique em "Iniciar Análise" para ver o progresso, os logs e o resumo serem preenchidos em tempo real.
5.  Após a conclusão, um link para download do relatório aparecerá.