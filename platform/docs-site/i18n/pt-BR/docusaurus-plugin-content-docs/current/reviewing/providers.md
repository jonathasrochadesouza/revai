---
id: providers
title: Escolhendo um provedor
sidebar_position: 1
slug: /providers
---

Uma revisão roda com exatamente um provedor configurado. O RevAI aceita APIs
hospedadas e agentes de CLI locais, e testa os dois sem gastar tokens.

## APIs hospedadas

Guarde uma chave e o RevAI a verifica com uma requisição que não consome
tokens. Chaves vão para um arquivo de credenciais separado dos seus projetos
e nunca são devolvidas por nenhum endpoint — só a forma mascarada aparece.

## Agentes de CLI locais

Eles reaproveitam o login que você já tem no agente, então não há chave para
guardar. O RevAI resolve o binário, mostra o caminho absoluto que encontrou e
roda um agente somente-leitura, sem herdar ferramentas.

## O que cada estado significa

Os termos abaixo são os valores literais de estado que a API reporta, então
ficam sem tradução: quem for comparar um badge com esta lista precisa deles
exatamente assim.

- **`ready`** — Instalado ou acessível, e autenticado. Pode rodar uma
  revisão com segurança.
- **`needs_auth`** — Presente, mas sem login ou sem chave.
- **`unknown`** — Presente, mas o estado de login não dá para determinar sem
  gastar uma requisição. Um dos agentes realmente não responde isso, então o
  RevAI diz a verdade em vez de adivinhar.
- **`not_found`** — Não instalado, ou fora do seu PATH.
- **`error`** — Presente, mas se comportando mal — travou, estourou o tempo,
  ou devolveu algo que não deu para interpretar.

## Ficando 100% local

Aponte o RevAI para um servidor de modelo rodando na sua própria máquina e
nenhum código sai dela. A qualidade depende do modelo que você baixar, mas os
analisadores determinísticos rodam de qualquer forma.
