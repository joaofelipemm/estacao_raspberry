# Backlog de Issues - Estação Raspberry

Este arquivo reúne a visão arquitetural e operacional do projeto, alinhada ao documento [arquitetura_raspberry_supabase_streamlit.docx](arquitetura_raspberry_supabase_streamlit.docx) e ao estado atual do repositório.

## Visão geral da arquitetura

A solução será organizada em camadas com foco em robustez, aquisição serial de dados já processados pelo STM32, persistência local e sincronização com Supabase para visualização via Streamlit.

### Camadas propostas

1. Dispositivos e aquisição de dados
   - STM32 como responsável pela leitura dos sensores físicos e cálculo das grandezas ambientais.
   - Raspberry Pi como concentrador e gateway de dados.
   - Comunicação via serial UART/RS-485/USB entre STM32 e Raspberry Pi.
   - A Raspberry não precisa ler sensores físicos diretamente; ela recebe os dados prontos.

2. Aquisição e protocolo serial
   - O Raspberry lê mensagens do STM32 em intervalos configuráveis.
   - Definição de protocolo de mensagens com temperatura, umidade e chuva acumulada; timestamp e identificador são associados pelo Raspberry.
   - Validação de checksum, delimitadores e integridade das mensagens.
   - Tratamento de frames corrompidos ou incompletos.

3. Persistência local
   - Armazenamento em arquivo CSV/JSON para tolerância a falhas de rede.
   - Diretório local para dados e logs.
   - Reconciliação posterior com serviço central.

4. Sincronização para Supabase
   - Envio de leituras para tabela central.
   - Retry com backoff em caso de falha de rede.
   - Processamento em lotes para reduzir overhead.

5. Visualização com Streamlit
   - Dashboard de temperatura, umidade e chuva acumulada.
   - Histórico e alertas para anomalias.

6. Operação e monitoramento
   - Logs estruturados, service manager e reinicialização automática.
   - Monitoramento da comunicação serial e do status do STM32.

---

## Status geral

- Sprint atual: foco em sensor real + persistência + sincronização
- Prioridade principal: P1
- Caminho recomendado: sensor -> persistência local -> Supabase -> Streamlit -> automação

---

## Issue 1: Implementar leitura serial de dados do STM32 no Raspberry Pi

### Prioridade da Issue 1

P1

### Status da Issue 1

Em andamento

### Descrição da Issue 1

Neste cenário, o STM32 é o responsável pela leitura dos sensores físicos e pelo cálculo das grandezas ambientais. O Raspberry Pi recebe essas medições por serial e não precisa ler sensores diretamente.

### Objetivo da Issue 1

Permitir que a estação receba, valide e normalize mensagens do STM32 pela porta serial.

### Critérios de aceitação da Issue 1

- O Raspberry lê dados vindos do STM32 via UART/serial.
- O protocolo de comunicação define delimitadores e campos esperados.
- O sistema valida pacotes corrompidos, vazios ou incompletos.
- Os dados entram no sistema em formato estruturado de `SensorReading` ou equivalente.
- Há testes para leitura válida e falha de comunicação serial.
- A aplicação continua estável quando o STM32 não responde.

### Tarefas sugeridas da Issue 1

- Definir protocolo de comunicação serial entre STM32 e Raspberry.
- Implementar leitura da porta serial em Python.
- Validar checksum, delimitadores e integridade da mensagem.
- Normalizar payload em objeto de leitura com temperatura, umidade e chuva acumulada (`RAIN`, em mm).
- Criar testes unitários para leitura serial e falha de porta.
- Registrar logs para perda de conexão e mensagens inválidas.

### Observação de arquitetura da Issue 1

Neste cenário, a classe `Sensor` do projeto deve evoluir para representar a interface de entrada de dados do dispositivo, e não necessariamente um sensor físico direto. A camada de abstração fica responsável por receber dados pela serial e converter em `SensorReading`.

---

## Issue 2: Persistir medições recebidas por serial com tolerância a falhas

### Prioridade da Issue 2

P1

### Status da Issue 2

Em andamento

### Descrição da Issue 2

A aplicação precisa registrar os dados coletados em armazenamento local antes de sincronizar com Supabase. Isso garante que a estação continue funcionando mesmo sem internet.

### Objetivo da Issue 2

Salvar leituras em arquivo local de forma confiável, com timestamp e sem perda de dados.

### Critérios de aceitação da Issue 2

- O diretório `data` e os arquivos são criados automaticamente.
- Cada leitura inclui timestamp em UTC.
- O armazenamento local é consistente em CSV ou JSON.
- A aplicação continua funcionando mesmo quando o arquivo ainda não existe.
- Há suporte para reprocessamento de arquivos locais.

### Tarefas sugeridas da Issue 2

- Definir estrutura do registro de leitura.
- Implementar gravação em CSV/JSON local.
- Adicionar rotina de criação do diretório e arquivos.
- Criar testes de persistência e de leitura de arquivo.
- Planejar rotação de arquivos ou retenção de dados.

---

## Issue 3: Criar CLI de ingestão serial e configuração da estação

### Prioridade da Issue 3

P2

### Status da Issue 3

Planejada

### Descrição da Issue 3

A aplicação atual ainda é simples e não expõe parâmetros de operação. A estação precisa ter um ponto de entrada com opções para execução e configuração.

### Objetivo da Issue 3

Tornar a estação útil em linha de comando para uso no Raspberry Pi.

### Critérios de aceitação da Issue 3

- O comando principal aceita parâmetros de configuração.
- É possível executar uma leitura única e um modo contínuo.
- O intervalo de coleta é configurável.
- A aplicação exibe mensagens úteis de status.
- A interface usa `argparse` ou equivalente confiável.

### Tarefas sugeridas da Issue 3

- Definir argumentos de execução: sensor, intervalo, modo, arquivo de saída.
- Implementar leitura única e loop contínuo.
- Integrar a camada de `Settings` ao CLI.
- Documentar uso no README.
- Adicionar testes de comandos e parâmetros.

---

## Issue 4: Sincronizar dados com Supabase de forma resiliente

### Prioridade da Issue 4

P1

### Status da Issue 4

Em andamento

### Descrição da Issue 4

O projeto deve enviar as medições para um banco central em Supabase, preservando as leituras locais em caso de falha de rede.

### Objetivo da Issue 4

Centralizar os dados para histórico, análise e visualização remota.

### Critérios de aceitação da Issue 4

- Há tabelas para armazenar medições com ID, timestamp, temperatura, umidade e chuva acumulada.
- A ingestão salva localmente antes de tentar sincronizar com Supabase.
- Falhas de rede mantêm os dados no CSV com status pendente.
- A sincronização tenta novamente até três vezes com backoff exponencial e retoma pendências na próxima execução.
- Cada leitura usa `sync_id` estável com índice único no Supabase para evitar duplicatas em retries.
- Os dados enviados têm campo de status e origem.
- Existe tratamento para dados duplicados ou incompletos.

### Tarefas sugeridas da Issue 4

- Definir schema da tabela `measurements`.
- Implementar cliente Python para Supabase.
- Ampliar retries para um worker periódico independente da leitura serial.
- Adicionar filas ou lotes de envio.
- Validar integração com ambiente de desenvolvimento.

### Estrutura sugerida da tabela

| Campo | Tipo | Descrição |
| --- | --- | --- |
| id | uuid / serial | Identificador da medição |
| device_id | text | Identificador do Raspberry |
| measured_at | timestamptz | Momento da leitura |
| temperature | numeric | Temperatura |
| humidity | numeric | Umidade |
| rain_accumulated | numeric | Chuva acumulada em milímetros |
| created_at | timestamptz | Momento do registro |
| source | text | Origem da leitura |
| status | text | Status da sincronização |
| metadata | jsonb | Dados extras opcionais |

---

## Issue 5: Construir dashboard com Streamlit

### Prioridade da Issue 5

P2

### Status da Issue 5

Planejada

### Descrição da Issue 5

A visualização é parte central da solução. O Streamlit deve reunir um painel simples para acompanhar as medidas em tempo real e em histórico.

### Objetivo da Issue 5

Disponibilizar indicadores e gráficos de monitoramento para o usuário.

### Critérios de aceitação da Issue 5

- Dashboard mostra temperatura, umidade e chuva acumulada.
- Existe visão de histórico temporal.
- Há indicadores de última leitura e alertas de anomalia.
- A interface funciona em rede local e pode ser expandida para acesso remoto.

### Tarefas sugeridas da Issue 5

- Definir página principal e métricas.
- Consultar dados do Supabase.
- Implementar filtros por período e dispositivo.
- Exibir alertas visuais para valores fora do esperado.
- Documentar como abrir o dashboard localmente.

---

## Issue 6: Automatizar operação em background e registrar logs estruturados

### Prioridade da Issue 6

P2

### Status da Issue 6

Planejada

### Descrição da Issue 6

Para uso real em Raspberry Pi, a estação precisa rodar de forma contínua e registrar eventos importantes sem intervenção manual.

### Objetivo da Issue 6

Garantir execução estável e observabilidade do sistema.

### Critérios de aceitação da Issue 6

- O processo roda em segundo plano como serviço do sistema.
- Há instruções para `systemd` ou cron.
- Logs de inicialização, falhas e coleta são registrados.
- O sistema reinicia automaticamente quando necessário.

### Tarefas sugeridas da Issue 6

- Criar script de serviço para Linux.
- Definir comportamento em caso de falha de sensor ou rede.
- Integrar logs de coleta e sincronização.
- Documentar rotina de reinicialização e monitoramento.

---

## Issue 7: Aumentar qualidade de software com testes e integração contínua

### Prioridade da Issue 7

P2

### Status da Issue 7

Planejada

### Descrição da Issue 7

O projeto precisa reforçar cobertura e qualidade para reduzir regressões e facilitar manutenção.

### Objetivo da Issue 7

Aumentar confiabilidade e preparar o código para evoluir com segurança.

### Critérios de aceitação da Issue 7

- Há testes para leitura, persistência, configuração e falha de sensor.
- O projeto usa lint e validações mínimas em CI.
- O código segue convenções consistentes e nomes claros.

### Tarefas sugeridas da Issue 7

- Adicionar testes para casos de erro e falha de rede.
- Configurar `ruff` ou equivalente para lint.
- Rodar testes em CI em cada mudança.
- Adicionar cobertura para módulos de storage e sincronização.

---

## Issue 8: Definir boas práticas de arquitetura e produção

### Prioridade da Issue 8

P3

### Status da Issue 8

Planejada

### Descrição da Issue 8

Além do desenvolvimento funcional, o projeto deve seguir boas práticas de engenharia para desempenho, segurança e operação em ambiente real.

### Objetivo da Issue 8

Preparar a solução para uso em produção com escalabilidade e robustez.

### Critérios de aceitação da Issue 8

- O projeto usa UTC em timestamps.
- Variáveis de ambiente são usadas para configuração sensível.
- Há política básica de retry e observabilidade.
- Há plano para retenção de dados, backup e monitoramento.

### Tarefas sugeridas da Issue 8

- Separar ambientes de desenvolvimento, teste e produção.
- Definir `env` variables para tokens, endpoints e intervalos.
- Adicionar backoff para sincronização com Supabase.
- Criar estratégia de retenção/limpeza de arquivos locais.
- Preparar documentação de manutenção para Raspberry Pi.

---

## Priorização final

1. Issue 1 - leitura serial do STM32 (P1)
2. Issue 2 - persistência local (P1)
3. Issue 4 - sincronização com Supabase (P1)
4. Issue 7 - qualidade e testes (P2)
5. Issue 3 - CLI e configuração da ingestão serial (P2)
6. Issue 5 - dashboard Streamlit (P2)
7. Issue 6 - automação e logs (P2)
8. Issue 8 - boas práticas de produção (P3)

---

## Observação arquitetural

A abordagem ideal para este projeto é um modelo híbrido e resiliente:

- coleta e processamento no STM32;
- ingestão e validação da mensagem no Raspberry Pi via serial;
- persistência local para tolerância a falhas;
- sincronização segura com Supabase;
- visualização em Streamlit.

Essa arquitetura combina simplicidade operacional com robustez, sendo adequada tanto para protótipo quanto para evolução em produção real, especialmente quando o STM32 é o dispositivo de campo e o Raspberry atua como gateway e concentrador.
