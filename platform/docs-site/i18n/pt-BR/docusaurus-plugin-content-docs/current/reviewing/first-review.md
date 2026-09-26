---
id: first-review
title: Rodando uma revisão
sidebar_position: 2
slug: /first-review
---

Revisões são deliberadas: você escolhe o que será revisado, vê quanto vai
custar e então executa.

## Três escopos

- **Diff de branch** — tudo que mudou entre uma branch base e uma head. É o
  padrão, e o que corresponde a um pull request.
- **Arquivos selecionados** — alguns arquivos escolhidos por você no
  navegador de arquivos.
- **Projeto inteiro** — a árvore completa. Caro, então reserve para uma
  primeira avaliação.

## Estática, IA, ou as duas

Os analisadores determinísticos rodam primeiro e não custam nada: linters,
varredura de segredos e uma passada estrutural. Depois a IA julga só o que
merece julgamento. Rodar as duas é o ponto do produto.

## A estimativa de custo

Antes de enviar qualquer coisa, o RevAI estima tokens e preço. Acima do seu
limite de aviso, ele pede confirmação; acima do orçamento máximo, ele
recusa. Os dois ficam nas configurações da engine.

## Enquanto roda

Cada etapa se reporta ao terminar, e o trabalho sobrevive ao fechamento da
aba porque pertence ao processo local, não à página. Cancelar interrompe na
etapa atual.
