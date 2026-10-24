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
   - O coletor escuta continuamente a porta serial do STM32; o intervalo de transmissão é definido pelo dispositivo.
   - O protocolo observado envia dispositivo, data, hora, temperatura, umidade e chuva acumulada; o Raspberry normaliza os campos.
   - Mensagens inválidas/status são ignoradas; a validação de checksum depende da especificação final do firmware.
   - O fluxo foi testado no notebook Windows pela COM11 a 115200 baud; falta validar operação no Raspberry Pi.

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

- Sprint atual: retomar e validar a atualização das medições no dashboard publicado
- Prioridade atual: confirmar coleta e sincronização de dados recentes (P1); validar acesso público e operação no Raspberry Pi.
- Fluxo validado no notebook: STM32 -> USB/serial (COM11, 115200 baud) -> CSV local -> Supabase -> dashboard Streamlit local.
- O dashboard está publicado no Community Cloud com Python 3.12. A versão local atual consulta o histórico completo do Supabase em páginas e foi validada com 15.317 medições; as mudanças mais recentes ainda não foram publicadas no Cloud.
- Os Secrets estão configurados e o usuário confirmou que apontam para o projeto esperado. O commit `4912257` também adicionou mensagens de diagnóstico seguras para falhas HTTP/rede; não houve erro de consulta durante a validação após o deploy.
- A conexão entre Cloud e Supabase está validada; falta publicar a versão atualizada e confirmar a chegada contínua de novas medições.
- Commits enviados para `main`: `0c8e575` (integração serial/CSV/Supabase/dashboard), `e3811f9` (preparação de Secrets e dependências do Streamlit Cloud), `32a093f` (progresso anterior) e `4912257` (diagnóstico da consulta remota).

---

## Issue 1: Implementar leitura serial de dados do STM32 no Raspberry Pi

### Prioridade da Issue 1

P1

### Status da Issue 1

Parcialmente concluída

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

- [x] Implementar leitura serial em Python, detecção automática quando há uma única porta e padrão de 115200 baud.
- [x] Interpretar o registro real observado (`DADOS:<device_id>;<data>;<hora>;<temperatura>;<umidade>;<chuva>`) e manter suporte ao protocolo legado.
- [x] Ignorar mensagens de status e descartar quadros inválidos sem parar o coletor.
- [x] Testar comunicação real no notebook pela COM11 e capturar medições.
- [x] Criar testes automatizados de parser e leitor.
- [ ] Completar validação de checksum/integridade conforme o protocolo final do firmware.
- [ ] Validar a operação no Raspberry Pi, incluindo recuperação após desconexão ou ausência de dados.

### Observação de arquitetura da Issue 1

Neste cenário, a classe `Sensor` do projeto deve evoluir para representar a interface de entrada de dados do dispositivo, e não necessariamente um sensor físico direto. A camada de abstração fica responsável por receber dados pela serial e converter em `SensorReading`.

---

## Issue 2: Persistir medições recebidas por serial com tolerância a falhas

### Prioridade da Issue 2

P1

### Status da Issue 2

Parcialmente concluída

### Descrição da Issue 2

A aplicação precisa registrar os dados coletados em armazenamento local antes de sincronizar com Supabase. Isso garante que a estação continue funcionando mesmo sem internet.

### Objetivo da Issue 2

Salvar leituras em arquivo local de forma confiável, com timestamp e sem perda de dados.

### Critérios de aceitação da Issue 2

- O diretório `data` e os arquivos são criados automaticamente.
- Cada leitura inclui timestamp com fuso horário; o Supabase armazena o horário normalizado em UTC.
- O armazenamento local é consistente em CSV ou JSON.
- A aplicação continua funcionando mesmo quando o arquivo ainda não existe.
- Há suporte para reprocessamento de arquivos locais.

### Tarefas sugeridas da Issue 2

- [x] Definir registro CSV com ID estável, timestamp, device_id, valores ambientais e estado de sincronização.
- [x] Criar diretório/arquivo automaticamente e migrar CSVs antigos preservando dados.
- [x] Salvar localmente antes da sincronização e manter pendências em falhas.
- [x] Criar testes de persistência, migração e leitura do CSV.
- [ ] Definir política de retenção e rotação do arquivo local.

---

## Issue 3: Criar CLI de ingestão serial e configuração da estação

### Prioridade da Issue 3

P2

### Status da Issue 3

Parcialmente concluída

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

- [x] Implementar execução contínua, mensagens de status e encerramento com `Ctrl+C`.
- [x] Permitir configurar porta, baudrate, timeout e caminho CSV pela função de entrada.
- [x] Documentar o uso no README.
- [ ] Adicionar CLI com `argparse`, modo de leitura única e intervalo configurável.
- [ ] Adicionar testes dos argumentos de linha de comando.

---

## Issue 4: Sincronizar dados com Supabase de forma resiliente

### Prioridade da Issue 4

P1

### Status da Issue 4

Concluída para o fluxo atual

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

- [x] Criar o schema `public.measurements` com `sync_id` único, RLS e leitura pública para o dashboard (`supabase_measurements.sql`).
- [x] Implementar cliente REST, sincronização após persistência local, retry com backoff e retomada de pendências.
- [x] Validar envio real e confirmar as medições pela API; CSV atualizado para `synced`.
- [x] Preservar o identificador do dispositivo e o horário enviados pelo STM32.
- [ ] Confirmar coleta contínua e sincronização de uma nova leitura até o Supabase.
- [ ] Avaliar worker periódico independente e processamento em lote se o volume justificar.

### Estrutura sugerida da tabela

| Campo | Tipo | Descrição |
| --- | --- | --- |
| id | bigint identity | Identificador interno da medição |
| sync_id | uuid unique | Identificador estável usado para evitar duplicatas |
| device_id | text | Identificador do dispositivo que enviou a leitura |
| measured_at | timestamptz | Momento da leitura |
| temperature | double precision | Temperatura |
| humidity | double precision | Umidade |
| rain_accumulated | double precision | Chuva acumulada em milímetros |
| source | text | Origem da leitura |
| status | text | Status da sincronização |
| metadata | jsonb | Dados extras opcionais |

---

## Issue 5: Construir dashboard com Streamlit

### Prioridade da Issue 5

P2

### Status da Issue 5

Parcialmente concluída

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

- [x] Implementar página com métricas, última leitura, gráficos e histórico.
- [x] Consultar Supabase primeiro e usar CSV local como fallback.
- [x] Testar o dashboard local no navegador com dados reais do Supabase.
- [x] Preparar leitura de Streamlit Secrets, ignorar `secrets.toml` local e documentar configuração segura.
- [x] Configurar `SUPABASE_URL` e `SUPABASE_PUBLISHABLE_KEY` (ou `SUPABASE_ANON_KEY`) em **App settings > Secrets** no Community Cloud.
- [x] Publicar o dashboard no Streamlit Community Cloud com Python 3.12 e confirmar que o app abre.
- [x] Exibir diagnóstico seguro quando a consulta ao Supabase falhar, incluindo o status HTTP quando disponível.
- [x] Confirmar no Cloud que a consulta retorna medições existentes em `public.measurements`.
- [x] Carregar todo o histórico do Supabase por páginas, incluindo mais de 10.000 medições.
- [x] Atualizar os dados do dashboard a cada 60 segundos enquanto a página estiver aberta.
- [x] Limitar os gráficos de temperatura e umidade ao dia da medição mais recente, mantendo chuva e histórico diário completos.
- [ ] Publicar no Community Cloud as mudanças locais de paginação, atualização periódica e gráficos do último dia.
- [ ] Confirmar que uma nova medição é coletada e sincronizada continuamente.
- [ ] Confirmar acesso ao dashboard como visitante sem autenticação.
- [ ] Implementar filtros por período/dispositivo e alertas de anomalia.

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

Parcialmente concluída

### Descrição da Issue 7

O projeto precisa reforçar cobertura e qualidade para reduzir regressões e facilitar manutenção.

### Objetivo da Issue 7

Aumentar confiabilidade e preparar o código para evoluir com segurança.

### Critérios de aceitação da Issue 7

- Há testes para leitura, persistência, configuração e falha de sensor.
- O projeto usa lint e validações mínimas em CI.
- O código segue convenções consistentes e nomes claros.

### Tarefas sugeridas da Issue 7

- [x] Adicionar testes de parser, armazenamento, falhas/retries do Supabase e configuração do dashboard.
- [x] Executar a suíte completa; 31 testes passaram antes do último push.
- [ ] Configurar lint com `ruff` ou equivalente.
- [ ] Executar testes automaticamente em CI.
- [ ] Medir cobertura e definir uma meta.

---

## Issue 8: Definir boas práticas de arquitetura e produção

### Prioridade da Issue 8

P3

### Status da Issue 8

Parcialmente concluída

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

- [x] Manter endpoints e credenciais em variáveis de ambiente/Secrets; `.env` e `secrets.toml` ficam fora do Git.
- [x] Restringir o dashboard às chaves públicas do Supabase e documentar que chaves `SECRET`/`SERVICE_ROLE` não devem ser usadas nele.
- [x] Implementar retry com backoff exponencial para sincronização.
- [ ] Separar formalmente ambientes de desenvolvimento, teste e produção.
- [ ] Definir retenção/backup local e documentação de operação/manutenção do Raspberry Pi.

---

## Priorização final

1. Issues 4 e 5 - confirmar a chegada de leituras recentes ao dashboard (P1)
2. Issue 1 - validar operação no Raspberry Pi e fechar validação do protocolo (P1)
3. Issue 2 - definir retenção e rotação do CSV (P1)
4. Issue 7 - configurar lint e CI (P2)
5. Issue 3 - concluir CLI com argparse e intervalo configurável (P2)
6. Issue 6 - automação e logs estruturados no Raspberry Pi (P2)
7. Issue 8 - boas práticas de operação em produção (P3)

---

## Observação arquitetural

A abordagem ideal para este projeto é um modelo híbrido e resiliente:

- coleta e processamento no STM32;
- ingestão e validação da mensagem no Raspberry Pi via serial;
- persistência local para tolerância a falhas;
- sincronização segura com Supabase;
- visualização em Streamlit.

Essa arquitetura combina simplicidade operacional com robustez, sendo adequada tanto para protótipo quanto para evolução em produção real, especialmente quando o STM32 é o dispositivo de campo e o Raspberry atua como gateway e concentrador.
