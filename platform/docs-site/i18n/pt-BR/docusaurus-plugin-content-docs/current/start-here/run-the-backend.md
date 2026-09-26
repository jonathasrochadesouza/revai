---
id: run-the-backend
title: Subindo o backend
sidebar_position: 2
slug: /run-the-backend
---

O app web conversa com uma API local. Quando essa API não responde, toda
tela que precisa de dados avisa — e esta página é a solução.

## Dois processos locais, sem containers

Instale as dependências e rode a API direto. Revisões precisam de acesso
direto aos seus repositórios Git no disco — rodar o backend dentro do Docker
quebra isso, já que o container não vê seus projetos, caminhos montados ou
ferramentas de CLI locais.

```bash
cd platform/api
uv sync --all-groups
uv run revai-api
```

A API responde no endpoint de saúde assim que fica pronta. Se não responder,
rode o comando doctor para um diagnóstico de armazenamento e configuração.

```bash
curl http://127.0.0.1:8799/api/health
uv run revai doctor
```

## O endereço e a porta

A API escuta apenas em loopback, então nada fora da sua máquina alcança ela.
O app web espera encontrá-la no endereço mostrado na tela de API e IA; use a
variável de ambiente para apontar para outro lugar.

```bash
http://127.0.0.1:8799
NEXT_PUBLIC_API_URL=http://127.0.0.1:8799
```

## Quando ainda não sobe

Leia os logs primeiro — uma porta já ocupada e uma instalação de dependência
que falhou não se parecem em nada. A tela de API e IA também oferece um
prompt de diagnóstico copiável, já com o erro capturado dentro, para colar
num agente de código.
