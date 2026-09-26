---
id: privacy-and-data
title: Privacidade e seus dados
sidebar_position: 2
slug: /privacy-and-data
---

O RevAI não tem conta, não tem telemetria e não tem armazenamento hospedado.
Esta página é o quadro completo do que sai da sua máquina.

## O que sai da sua máquina

Somente o contexto da revisão enviado ao provedor que você configurou: os
trechos ou arquivos filtrados, com os segredos detectados mascarados antes
de qualquer envio. Nada mais é transmitido, e escolher um servidor de modelo
local significa que nada sai.

## O que fica

Revisões, achados, configuração e sua lista de projetos são arquivos no seu
diretório de usuário. Credenciais ficam num arquivo próprio, separado de
tudo, e são excluídas das exportações.

```bash
~/.revai/
~/.revai/credentials.yaml
```

## Conteúdo de repositório não é confiável

Código em revisão é tratado como dado, nunca como instrução. Um comentário
num arquivo mandando o revisor ignorar as regras dele é citado, não
obedecido.

## Levando seus dados embora, ou apagando

Exporte tudo como um arquivo portátil nas configurações de dados, ou apague
o diretório. Não existe cópia em servidor para pedir a ninguém.
