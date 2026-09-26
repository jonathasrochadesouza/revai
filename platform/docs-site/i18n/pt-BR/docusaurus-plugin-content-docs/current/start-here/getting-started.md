---
id: getting-started
title: Primeiros passos
sidebar_position: 1
slug: /getting-started
---

O RevAI revisa código na sua máquina. Repositórios nunca são enviados: só o
contexto filtrado e com segredos mascarados chega ao provedor de modelo que
você configurar.

## As duas partes

Uma API local faz o trabalho e guarda sua configuração, e o app web conversa
com ela. As duas rodam na sua máquina, e a CLI roda o mesmo pipeline sem
servidor web nenhum.

```bash
cd platform/api && uv run revai-api
cd platform/web && npm run dev
```

## Sua primeira execução, em ordem

1. Suba o backend e confirme que a tela de conexão está verde.
2. Escolha um provedor, guarde a chave dele e verifique.
3. Abra uma pasta Git local, ou clone um repositório.
4. Confira a prévia do diff e a estimativa de custo, depois rode a revisão.

## Onde as coisas ficam

Revisões, configuração e os metadados mascarados das credenciais ficam no
seu diretório de usuário. Credenciais ficam separadas dos repositórios, e
nada é enviado a lugar algum sem uma ação explícita.

```bash
~/.revai/config.yaml
~/.revai/credentials.yaml
~/.revai/reviews/
```
