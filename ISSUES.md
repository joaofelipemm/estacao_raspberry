# Backlog de Issues - Estação Raspberry

Este arquivo reúne as issues iniciais do projeto, baseadas na estrutura atual do repositório e nos próximos passos documentados no README.

## Status geral

- Sprint atual: Issue 1 em andamento
- Prioridade principal: P1
- Fluxo sugerido: começar pela infraestrutura básica do sensor antes de persistência e interface

## Issue 1: Implementar leitura de sensores reais

### Prioridade
P1

### Status
Em andamento

### Descrição
O projeto atual possui uma classe `Sensor` com dados simulados. A próxima etapa é substituir a leitura mockada por drivers reais para sensores comuns em Raspberry Pi, como DHT22 e BMP280.

### Objetivo
Permitir que a estação leia temperatura, umidade e pressão com dados reais do hardware.

### Critérios de aceitação
- A classe `Sensor` aceita configuração de tipo de sensor.
- Há suporte para pelo menos um sensor de temperatura/umidade e um de pressão.
- Erros de leitura do hardware são tratados com mensagens claras.
- Os testes cobrem leitura válida e falha de comunicação.

### Tarefas sugeridas
- Criar abstração de sensor base.
- Implementar driver para DHT22.
- Implementar driver para BMP280/BME280.
- Validar dependências e compatibilidade com Raspberry Pi.

---

## Issue 2: Persistir medições em arquivo

### Prioridade
P2

### Status
Planejada

### Descrição
A aplicação precisa registrar as medidas coletadas em armazenamento local para histórico e análise posterior.

### Objetivo
Salvar leituras em JSON ou CSV de forma confiável.

### Critérios de aceitação
- O diretório de dados é criado automaticamente.
- Cada leitura é gravada com timestamp.
- O formato CSV/JSON é consistente.
- A aplicação consegue continuar funcionando mesmo quando o arquivo ainda não existe.

### Tarefas sugeridas
- Definir estrutura de dados de registro.
- Implementar salva em JSON/CSV.
- Adicionar rotacionamento ou limite de arquivos.
- Criar testes de persistência.

---

## Issue 3: Criar CLI para coleta e configuração

### Prioridade
P3

### Status
Planejada

### Descrição
A aplicação atual só imprime uma mensagem fixa. É necessário um ponto de entrada com opções de execução, como intervalo de coleta, leitura única e configuração de sensor.

### Objetivo
Tornar a estação útil em linha de comando e fácil de operar no Raspberry Pi.

### Critérios de aceitação
- O comando principal aceita parâmetros de configuração.
- É possível executar uma leitura única ou loop contínuo.
- O intervalo de coleta é configurável.
- A interface mostra mensagens claras de status.

### Tarefas sugeridas
- Definir argumentos com argparse ou Typer.
- Implementar leitura manual e modo contínuo.
- Integrar com a classe `Settings`.
- Documentar uso no README.

---

## Issue 4: Automatizar coleta em background

### Prioridade
P4

### Status
Planejada

### Descrição
Para uso real em Raspberry Pi, a estação precisa rodar automaticamente em segundo plano sem intervenção humana.

### Objetivo
Permitir execução automática com cron, systemd ou serviço do sistema.

### Critérios de aceitação
- Há instruções de instalação para execução automática.
- O serviço cria diretórios necessários.
- O processo continua estável após reinicialização.
- Logs relevantes são registrados.

### Tarefas sugeridas
- Criar script de serviço ou serviço `systemd`.
- Definir comportamento em caso de falha de sensor.
- Documentar rotina de reinício e monitoramento.

---

## Issue 5: Expor dados por API ou painel web

### Prioridade
P5

### Status
Planejada

### Descrição
A estação pode evoluir para permitir visualização remota dos dados em tempo real ou histórico.

### Objetivo
Oferecer acesso simples às medições por interface web ou API REST.

### Critérios de aceitação
- Existe endpoint ou página que retorna as últimas leituras.
- A API responde em JSON.
- Os dados são lidos a partir do armazenamento local.
- A solução é simples e segura para uso em rede local.

### Tarefas sugeridas
- Avaliar FastAPI ou Flask.
- Implementar rota de leitura atual.
- Implementar rota de histórico.
- Adicionar documentação de uso.

---

## Issue 6: Melhorar testes e qualidade do projeto

### Prioridade
P2

### Status
Planejada

### Descrição
O repositório tem testes iniciais, mas ainda falta cobertura para configurações, persistência e casos de erro.

### Objetivo
Aumentar a confiabilidade do código e facilitar futuras mudanças.

### Critérios de aceitação
- Há testes para leitura do sensor, configurações e armazenamento.
- Os testes cobrem falha de leitura e criação de diretórios.
- O projeto usa lint e validação mínima em CI.

### Tarefas sugeridas
- Adicionar pytest para casos de erro.
- Configurar `ruff` no fluxo de desenvolvimento.
- Rodar testes em CI.

---

## Priorização final

1. Issue 1 - leitura de sensores reais (P1)
2. Issue 2 - persistência de dados (P2)
3. Issue 6 - qualidade e testes (P2)
4. Issue 3 - CLI de operação (P3)
5. Issue 4 - automação em background (P4)
6. Issue 5 - API/painel (P5)

## Observação
Essas issues foram preparadas a partir do contexto atual do projeto e podem ser ajustadas conforme a arquitetura final do produto.
