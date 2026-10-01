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
SUPABASE_ANON_KEY=sua_chave_anonima
DEVICE_ID=raspberry-pi
```

A tabela `measurements` deve ter a coluna `rain_accumulated` (`double precision`), em milímetros. Para atualizar uma tabela existente no Supabase, execute no SQL Editor:

```sql
ALTER TABLE public.measurements
ADD COLUMN IF NOT EXISTS rain_accumulated double precision;

ALTER TABLE public.measurements
ADD COLUMN IF NOT EXISTS sync_id uuid;

CREATE UNIQUE INDEX IF NOT EXISTS measurements_sync_id_unique
ON public.measurements (sync_id);

ALTER TABLE public.measurements
ALTER COLUMN pressure DROP NOT NULL;
```

O protocolo serial espera `TEMP`, `HUM` e `RAIN`, por exemplo: `<TEMP=23.4;HUM=58.1;RAIN=12.5>`. CSVs antigos são migrados preservando as leituras; os valores históricos de pressão ficam sem valor de chuva.

Ao executar `python -m estacao_raspberry.main`, cada leitura é gravada localmente antes da sincronização. O CSV mantém um ID estável e o estado `pending`/`synced`; o Raspberry tenta cada pendência até três vezes com espera exponencial. Falhas mantêm a leitura pendente para a próxima execução. A coluna `sync_id` com índice único no Supabase torna seguro repetir uma requisição cuja resposta tenha se perdido.

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
