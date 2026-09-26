---
id: cli-and-ci
title: CLI e CI
sidebar_position: 1
slug: /cli-and-ci
---

A CLI instalada roda o mesmo pipeline somente-leitura sem servidor web, o
que é o que torna o RevAI usável em integração contínua.

## Revisando pelo terminal

Aponte para um repositório, informe base e head, e escolha o modo. Os
escopos de arquivos selecionados e projeto inteiro também estão disponíveis.

```bash
revai review . --base main --head feature/payments \
  --mode both --model claude-haiku-4.5 \
  --format sarif --output revai.sarif --fail-on medium
```

## Códigos de saída

Zero significa que a execução terminou dentro do seu limite. Um significa
que o limite de achados configurado foi atingido — é nele que um pipeline
deve falhar. Dois significa erro de configuração ou execução, que é outro
problema e merece outro alerta.

```text
0  under threshold
1  threshold reached
2  configuration or execution error
```

## Formatos de relatório

JSON para máquinas, Markdown para comentar num pull request, um HTML
autônomo que abre em qualquer lugar, e SARIF para integrações de code
scanning.

```bash
--format json | md | html | sarif
```

## Dentro de um pipeline

Passe a chave do provedor como segredo, escolha um modelo barato e limite a
revisão ao diff da branch. Falhe o job pelo código de saída, não
interpretando o relatório.
