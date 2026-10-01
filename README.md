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

## Próximos passos

1. Adicionar leitura de sensores reais (DHT22, BMP280, etc.)
2. Gravar dados em arquivo JSON/CSV
3. Criar API ou painel web para visualizar informações
4. Automatizar coleta com cron/systemd

## Observação

O projeto foi inicializado em uma estrutura modular para facilitar o crescimento sem misturar leitura de sensores, configuração e execução principal.
