# Estação Raspberry

Projeto base para monitoramento ambiental com Raspberry Pi, incluindo leitura de sensores, armazenamento de dados e uso em linha de comando.

## Estrutura

- `src/estacao_raspberry/` — código principal do pacote
- `tests/` — testes automáticos
- `requirements.txt` — dependências do projeto
- `pyproject.toml` — configuração do pacote Python

## Requisitos

- Python 3.10+
- Raspberry Pi (opcional para sensores reais)
- Ambiente virtual recomendado

## Instalação

```bash
python -m venv .venv
source .venv/bin/activate  # Linux/macOS
.venv\Scripts\activate     # Windows
pip install -r requirements.txt
pip install -e .
pip install pytest
```

## Execução

```bash
python -m estacao_raspberry.main
pytest -q
```

## Dashboard online-first

O dashboard pode funcionar em nuvem sem depender de hardware local. Ao configurar as variáveis de ambiente do Supabase, a aplicação carrega os dados da tabela `measurements` automaticamente. Caso as variáveis não existam, o sistema usa o CSV local como fallback.

```bash
cp .env.example .env
```

Exemplo:

```bash
SUPABASE_URL=https://seu-projeto.supabase.co
SUPABASE_PUBLISHABLE_KEY=sua_chave_publica
DEVICE_ID=raspberry-pi
```

Para publicar no Streamlit Community Cloud, envie primeiro as alterações para o GitHub e configure `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` em **App settings > Secrets**. A chave pública (ou `SUPABASE_ANON_KEY`) é usada apenas para leitura pelo dashboard; não coloque `SUPABASE_SECRET_KEY` nem `SUPABASE_SERVICE_ROLE_KEY` nos Secrets do dashboard.

A aplicação espera uma tabela `public.measurements` com `sync_id` único para que o retry não duplique leituras. Para criar a tabela e permitir que o dashboard consulte as medições, execute o arquivo [`supabase_measurements.sql`](supabase_measurements.sql) no SQL Editor do Supabase. Se já houver uma tabela antiga, preserve os dados e aplique somente as alterações necessárias:

```sql
ALTER TABLE public.measurements
ADD COLUMN IF NOT EXISTS rain_accumulated double precision;

ALTER TABLE public.measurements
ADD COLUMN IF NOT EXISTS solar_radiation double precision;

ALTER TABLE public.measurements
ADD COLUMN IF NOT EXISTS sync_id uuid;

CREATE UNIQUE INDEX IF NOT EXISTS measurements_sync_id_unique
ON public.measurements (sync_id);

ALTER TABLE public.measurements
ALTER COLUMN pressure DROP NOT NULL;
```

O protocolo serial espera `TEMP`, `HUM` e `RAIN`, por exemplo: `<TEMP=23.4;HUM=58.1;RAIN=12.5>`. A radiação solar é opcional e pode ser enviada como `RAD`, em W/m²: `<TEMP=23.4;HUM=58.1;RAIN=12.5;RAD=450>`. Para registros STM32, o último campo numérico opcional de `DADOS` é a radiação, por exemplo `DADOS:est_01;05/10/2026;16:15:57;23.66;77.06;0.4;450`. Execute a migração SQL antes de sincronizar registros com o campo novo. CSVs antigos são migrados preservando as leituras; os valores históricos de pressão ficam sem valor de chuva ou radiação.

Ao executar `python -m estacao_raspberry.main`, cada leitura é gravada localmente antes da sincronização. O CSV mantém um ID estável e o estado `pending`/`synced`; o Raspberry tenta cada pendência até três vezes com espera exponencial. Falhas mantêm a leitura pendente para a próxima execução. A coluna `sync_id` com índice único no Supabase torna seguro repetir uma requisição cuja resposta tenha se perdido.

O coletor permanece escutando a porta serial até ser interrompido com `Ctrl+C`. Se houver uma única porta serial disponível, ela é detectada automaticamente; com várias portas, informe a desejada. O padrão é 115200 baud. São aceitos quadros legados como `<TEMP=23.4;HUM=58.1;RAIN=12.5>` e registros STM32 no formato `DADOS:est_01;05/10/2026;16:15:57;23.66;77.06;0.4` (dispositivo, data, hora, temperatura, umidade e chuva). Cada leitura válida é acrescentada em `data/measurements.csv`, preservando o identificador e o timestamp do dispositivo quando informados.

Depois:

```bash
.\.venv\Scripts\streamlit.exe run dashboard.py
```

## Próximos passos

1. Adicionar leitura de sensores reais (DHT22, BMP280, etc.)
2. Gravar dados em arquivo JSON/CSV
3. Criar API ou painel web para visualizar informações
4. Automatizar coleta com cron/systemd
5. Melhorar a visualização do dashboard em Streamlit

## Observação

O projeto foi inicializado em uma estrutura modular para facilitar o crescimento sem misturar leitura de sensores, configuração e execução principal.
