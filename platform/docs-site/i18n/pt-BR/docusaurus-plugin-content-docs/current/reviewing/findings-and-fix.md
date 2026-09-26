---
id: findings-and-fix
title: Achados e correções
sidebar_position: 3
slug: /findings-and-fix
---

Um achado nomeia um arquivo e um intervalo de linhas, se explica e — muitas
vezes — traz um patch sugerido.

## Triagem

Marque cada achado como corrigido, descartado ou falso positivo. A escolha
fica gravada na revisão, então a tela de indicadores consegue separar
problema real de ruído ao longo do tempo.

## Aplicando um patch sugerido

O patch é aplicado na sua árvore de trabalho, sempre sem stage e nunca
commitado. O RevAI recusa quando a branch ativa é diferente da head da
revisão ou quando o arquivo mudou desde então, valida o patch antes e roda
de novo o analisador que gerou o achado depois. Se a regra ainda dispara, a
mudança é revertida.

```bash
revai fix . --review <review-id> --finding <finding-id> --dry-run
revai fix . --review <review-id> --finding <finding-id>
```

## Quando não existe patch

Gerar uma correção pede ao modelo configurado a menor edição possível,
converte em um diff real e aplica pela mesma validação. Custa tokens, então
é sempre uma ação explícita.

```bash
revai fix . --review <review-id> --finding <finding-id> --generate
```

## Revise antes de commitar

Tudo chega sem stage de propósito: leia o diff você mesmo antes de commitar.
O RevAI nunca commita, nunca faz push e nunca mexe numa branch.

```bash
git diff
```
