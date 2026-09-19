/**
 * pt-BR message catalog.
 *
 * Typed as `Record<MessageKey, string>` against the en-US catalog, so a missing
 * or extra key here is a compile error — the two locales stay structurally
 * isolated and complete.
 */

import type { MessageKey } from "./en-US";

export const ptBR: Record<MessageKey, string> = {
  // --- common / shell -------------------------------------------------------
  "common.projects": "Projetos",
  "common.insights": "Indicadores",
  "common.data": "Dados",
  "common.appearance": "Aparência",
  "common.engine": "Engine",
  "common.settings": "Configurações",
  "common.menu": "Menu",
  "common.platform": "Plataforma",
  "common.loading": "Carregando",
  "common.cancel": "Cancelar",
  "common.breadcrumb": "Navegação estrutural",
  "common.primaryNavigation": "Navegação principal",
  "common.dismissMessage": "Descartar mensagem",
  "common.closeDialog": "Fechar diálogo",
  "common.apiConnected": "API conectada",
  "common.apiUnreachable": "API inacessível",
  "common.couldNotReachApi": "Não foi possível acessar a API.",
  "common.allProjects": "Todos os projetos",
  "common.backToProjects": "Voltar aos projetos",
  "common.unsavedOne": "1 alteração não salva",
  "common.unsavedOther": "{count} alterações não salvas",

  // --- relative time --------------------------------------------------------
  "time.justNow": "agora mesmo",
  "time.minutesAgo": "{count}min atrás",
  "time.hoursAgo": "{count}h atrás",
  "time.daysAgo": "{count}d atrás",

  // --- projects page --------------------------------------------------------
  "projects.title": "Projetos",
  "projects.subtitle":
    "O acesso aos repositórios permanece local. Apenas o contexto de revisão filtrado chega ao provedor que você configurar.",
  "projects.searchProjects": "Buscar projetos",
  "projects.addRepository": "Adicionar um repositório",
  "projects.openLocalFolder": "Abrir pasta local",
  "projects.openLocalFolderDescription":
    "Aponte o RevAI para um repositório Git que já esteja nesta máquina.",
  "projects.openLocalFolderAction": "Escolher ou digitar caminho",
  "projects.cloneFromRemote": "Clonar repositório remoto",
  "projects.cloneFromRemoteDescription":
    "Clone um remoto Git (HTTPS, SSH ou local) para uma pasta à sua escolha.",
  "projects.cloneFromRemoteAction": "Informar URL e pasta",
  "projects.yourProjects": "Seus projetos",
  "projects.filterAll": "Todos",
  "projects.filterActive": "Ativos",
  "projects.filterArchived": "Arquivados",
  "projects.repository": "Repositório",
  "projects.branch": "Branch",
  "projects.languages": "Linguagens",
  "projects.added": "Adicionado",
  "projects.notDetected": "Não detectadas",
  "projects.noMatchView": "Nenhum projeto corresponde a esta visão",
  "projects.noRepositories": "Nenhum repositório ainda",
  "projects.tryDifferentSearch": "Tente outra busca ou outro filtro de projeto.",
  "projects.openLocalGitFolder":
    "Abra uma pasta Git local para começar a inspecionar alterações.",
  "projects.openRepository": "Abrir repositório",
  "projects.gettingStarted": "Primeiros passos",
  "projects.gettingStartedTitle": "Prepare-se para a primeira revisão",
  "projects.stepConfigureEngine": "Configurar uma engine",
  "projects.stepVerifyProvider": "Verificar acesso ao provedor",
  "projects.stepAddRepository": "Adicionar um repositório",
  "projects.complete": "Concluído",

  // --- repository dialog ----------------------------------------------------
  "projects.dialog.openTitle": "Abrir pasta local",
  "projects.dialog.openDescription":
    "Procure um repositório Git ou informe o caminho absoluto dele.",
  "projects.dialog.cloneTitle": "Clonar repositório remoto",
  "projects.dialog.cloneDescription":
    "Escolha um repositório remoto e onde salvar o checkout local dele.",
  "projects.dialog.folderPath": "Caminho da pasta",
  "projects.dialog.repositoryUrl": "URL do repositório",
  "projects.dialog.saveIn": "Salvar em",
  "projects.dialog.browse": "Procurar",
  "projects.dialog.selecting": "Selecionando",
  "projects.dialog.open": "Abrir",
  "projects.dialog.opening": "Abrindo",
  "projects.dialog.clone": "Clonar",
  "projects.dialog.cloning": "Clonando",

  // --- review setup page ----------------------------------------------------
  "review.eyebrow": "Revisão",
  "review.setupTitle": "Configure uma revisão",
  "review.setupSubtitle":
    "Escolha a comparação entre branches, inspecione o contexto proposto e execute a revisão quando o escopo e o custo estimado estiverem adequados.",
  "review.projectUnavailable": "Projeto indisponível",
  "review.projectUnavailableFallback": "Não foi possível carregar este projeto.",

  // --- review inspector -----------------------------------------------------
  "review.base": "Base",
  "review.head": "Head",
  "review.scope": "Escopo",
  "review.reviewMode": "Modo de revisão",
  "review.branchDiff": "Diff entre branches",
  "review.selectedFiles": "Arquivos selecionados",
  "review.wholeProject": "Projeto inteiro",
  "review.staticOnly": "Somente análise estática",
  "review.aiAssisted": "Assistida por IA",
  "review.both": "Ambas",
  "review.preview": "Prévia",
  "review.runStatic": "Executar revisão estática",
  "review.runAi": "Executar revisão com IA",
  "review.runCombined": "Executar revisão combinada",
  "review.runAgain": "Executar novamente",
  "review.providerChecking": "Verificando o provedor de IA configurado…",
  "review.providerUnavailable":
    "O provedor de IA configurado está indisponível. Atualize-o antes de iniciar uma revisão com IA.",
  "review.openSettings": "Abrir configurações",
  "review.degradedCoverage":
    "A cobertura determinística ficará degradada: {analyzers}.",
  "review.reviewSetup": "Configurar revisão",
  "review.files": "Arquivos",
  "review.lines": "Linhas",
  "review.estTokens": "Tokens estimados",
  "review.estInput": "Entrada estimada",
  "review.noChanges": "Nenhuma alteração nesta comparação",
  "review.noChangesDetail":
    "Quando base e head coincidem, o RevAI pré-visualiza as alterações não commitadas da árvore de trabalho.",
  "review.diffTruncated":
    "Prévia limitada a 1 MB. O diff completo permanece inalterado no Git.",
  "review.configureAnother": "Configurar outra revisão",
  "review.loadingRepository": "Carregando dados do repositório",

  // --- quality commands -----------------------------------------------------
  "review.qualityCommands": "Comandos de qualidade do projeto",
  "review.qualityCommandsOptional": "opcional · shell desabilitado",
  "review.jsonArgumentArrays":
    "Use arrays JSON de argumentos para manter seguros os caminhos com espaços, por exemplo",
  "review.defaultBaseBranch": "Branch base padrão",
  "review.checkstyle": "Checkstyle",
  "review.checkstyleDescription":
    "Verifica as regras configuradas de estilo Java e análise estática.",
  "review.tests": "Testes",
  "review.testsDescription":
    "Executa a suíte de testes do projeto para detectar falhas e regressões.",
  "review.build": "Build",
  "review.buildDescription":
    "Compila ou empacota o projeto para validar dependências, tipos e artefatos gerados.",
  "review.moreInformationAbout": "Mais informações sobre",
  "review.saving": "Salvando…",
  "review.saveProjectCommands": "Salvar comandos do projeto",
  "review.commandMustBeArray": "deve ser um array JSON de argumentos do comando.",

  // --- live review panel ----------------------------------------------------
  "review.staticReview": "Revisão estática",
  "review.combinedReview": "Revisão combinada",
  "review.aiReview": "Revisão com IA",
  "review.status.failed": "Falhou",
  "review.status.cancelled": "Cancelada",
  "review.status.degraded": "Concluída com cobertura degradada",
  "review.status.reviewing": "Revisando",
  "review.status.completed": "Concluída",
  "review.status.completedTokens": "Concluída · {tokens} tokens",
  "review.metric.findings": "Achados",
  "review.metric.filesReviewed": "Arquivos revisados",
  "review.metric.tokens": "Tokens",
  "review.metric.estContext": "Contexto estimado",
  "review.metric.estCost": "Custo estimado",
  "review.metric.cost": "Custo",
  "review.metric.duration": "Duração",
  "review.metric.live": "Ao vivo",
  "review.eventStream": "Eventos",
  "review.analyzers": "Analisadores",
  "review.analyzersPending": "Pendente",
  "review.event.queued": "Na fila — aguardando uma vaga de revisão",
  "review.event.started": "Revisão iniciada",
  "review.event.completed": "Revisão concluída",
  "review.event.cancelled": "Revisão cancelada",
  "review.event.findings": "{count} achados",
  "review.event.model": "Modelo · {model}",
  "review.event.delta": "Saída do modelo · {chars} caracteres",
  "review.event.retry": "Tentativa {attempt} · {message}",
  "review.event.usage": "Uso · {tokens} tokens",
  "review.event.persisted": "{count} eventos persistidos · {status}",
  "review.startingAnalysis": "Iniciando análise local…",
  "review.inProgress": "Revisão em andamento",
  "review.validatingStreamed": "Validando achados em streaming",
  "review.runningLocalAnalyzers": "Executando analisadores locais",
  "review.stopped": "Revisão interrompida",
  "review.noFindings": "Nenhum achado",
  "review.jobCancelled": "O trabalho em segundo plano foi cancelado.",
  "review.noIssuesReported":
    "Os analisadores disponíveis e a IA não reportaram problemas.",
  "review.finding.whyThisMatters": "Por que isso importa",
  "review.finding.hideEvidence": "Ocultar evidência",
  "review.finding.confidence": "Confiança {percent}%",
  "review.finding.copyPatch": "Copiar patch sugerido",
  "review.finding.patchCopied": "Patch copiado",
  "review.finding.defaultRationale":
    "Este achado foi reportado pelo analisador selecionado.",
  "review.finding.markFixed": "Marcar como corrigido",
  "review.finding.falsePositive": "Falso positivo",
  "review.finding.dismiss": "Descartar",
  "review.finding.status.open": "Aberto",
  "review.finding.status.fixed": "Corrigido",
  "review.finding.status.false_positive": "Falso positivo",
  "review.finding.status.dismissed": "Descartado",
  "review.severity.critical": "Crítico",
  "review.severity.medium": "Médio",
  "review.severity.low": "Baixo",
  "review.history": "Histórico de revisões",
  "review.historyFindings": "{count} achados",
  "review.localAnalysis": "Análise local",

  // --- cost confirmation ----------------------------------------------------
  "review.cost.title": "Confirme o custo estimado da revisão",
  "review.cost.exceedsThreshold":
    "Esta revisão excede o seu limite de aviso.",
  "review.cost.model": "Modelo:",
  "review.cost.scope": "Escopo:",
  "review.cost.scopeDetail": "{count} arquivos, {tokens} tokens estimados",
  "review.cost.estimatedInput": "Entrada estimada:",
  "review.cost.budgetSuffix": " de {cap} de orçamento",
  "review.cost.runReview": "Executar revisão",

  // --- file browser ---------------------------------------------------------
  "files.trackedFiles": "Arquivos rastreados",
  "files.selected": "selecionados",
  "files.changed": "Alterados",
  "files.all": "Todos",
  "files.searchFiles": "Pesquisar arquivos",
  "files.clearSearch": "Limpar pesquisa de arquivos",
  "files.showFlatList": "Mostrar lista direta",
  "files.showFolderTree": "Mostrar árvore de pastas",
  "files.expandAllFolders": "Expandir todas as pastas",
  "files.collapseAllFolders": "Recolher todas as pastas",
  "files.flatList": "Lista direta",
  "files.noFilesMatch": "Nenhum arquivo corresponde à pesquisa.",
  "files.noChangedFiles": "Nenhum arquivo alterado.",
  "files.noTrackedFiles": "Nenhum arquivo rastreado.",
  "files.notAtHead": "Fora do Head",
  "files.notAtHeadReason":
    "Este caminho não está rastreado no Head. Use o diff entre branches para revisá-lo.",

  // --- branch select --------------------------------------------------------
  "branches.search": "Pesquisar branches",
  "branches.noMatches": "Nenhuma branch corresponde à pesquisa.",

  // --- settings shell -------------------------------------------------------
  "settings.eyebrow": "Configurações",
  "settings.unsavedChanges": "alterações não salvas",

  // --- appearance -----------------------------------------------------------
  "settings.appearance.title": "Aparência & idioma",
  "settings.appearance.subtitle":
    "Ajuste um espaço de trabalho confortável e o idioma que o RevAI usa na interface. Essas preferências ficam na sua máquina, em config.yaml.",
  "settings.appearance.unavailable": "Preferências indisponíveis",
  "settings.appearance.cardTitle": "Aparência",
  "settings.appearance.themeAria": "Tema de cores",
  "settings.appearance.theme.light": "Claro",
  "settings.appearance.theme.lightDetail": "Paper Light",
  "settings.appearance.theme.dark": "Escuro",
  "settings.appearance.theme.darkDetail": "Ambiente com menos reflexo",
  "settings.appearance.theme.system": "Sistema",
  "settings.appearance.theme.systemDetail": "Seguir o seu dispositivo",
  "settings.appearance.themeHint":
    "As mudanças de tema são aplicadas imediatamente e salvas no seu arquivo de configuração local.",
  "settings.appearance.languageCard": "Idioma & comportamento de revisão",
  "settings.appearance.displayLanguage": "Idioma de exibição",
  "settings.appearance.supportedLocales": "Inglês e português do Brasil",
  "settings.appearance.locale.enUS": "English (United States)",
  "settings.appearance.locale.ptBR": "Português (Brasil)",
  "settings.appearance.localeHint":
    "Alterna o idioma de toda a interface, aplicado imediatamente neste rascunho.",
  "settings.appearance.confirmExpensive": "Confirmar revisões caras",
  "settings.appearance.confirmExpensiveHint":
    "Mostra a estimativa e pede confirmação antes que a revisão ultrapasse o seu limite de aviso.",

  // --- save bar -------------------------------------------------------------
  "save.discard": "Descartar",
  "save.saving": "Salvando…",
  "save.saveChanges": "Salvar alterações",
  "save.allChangesSaved": "Todas as alterações salvas",
  "save.changesSaveAutomatically": "As alterações são salvas automaticamente",
  "save.couldNotSave": "Não foi possível salvar",
  "save.autoSaveOffer":
    "Salvar as alterações automaticamente? Você pode ativar ou desativar a qualquer momento em Configurações › Aparência.",
  "save.autoSaveDecline": "Não, não perguntar novamente",
  "save.autoSaveEnable": "Ativar salvamento automático",
  "save.autoSavePreference": "Salvar alterações automaticamente",
  "save.autoSaveHint":
    "Salva as alterações de configuração pouco depois de você fazê-las. A oferta é apresentada a quem ainda não decidiu sempre que houver alterações pendentes; desligar aqui encerra a oferta definitivamente.",

  // --- engine page ----------------------------------------------------------
  "settings.engine.title": "Engine & provedores",
  "settings.engine.subtitle.before":
    "Escolha como o RevAI acessa um modelo. Tudo é gravado em",
  "settings.engine.subtitle.after":
    "— texto simples que você pode ler, comparar e versionar.",
  "settings.engine.configurationUnavailable": "Configuração indisponível",
  "settings.engine.noConfigReturned": "A API não retornou uma configuração",
  "settings.engine.startBackendHint":
    "Se o backend não estiver em execução, inicie-o em um segundo terminal:",
  "settings.engine.backToDashboard": "← Voltar ao painel",

  // --- engine form ----------------------------------------------------------
  "engine.executionMode": "Modo de execução",
  "engine.modeAria": "Modo de execução",
  "engine.mode.api.title": "API de modelo",
  "engine.mode.api.description":
    "Use a sua própria chave e chame o provedor diretamente. Telemetria completa de custo e tokens, saída estruturada garantida.",
  "engine.mode.badge": "Recomendado",
  "engine.mode.cli.title": "Agente CLI local",
  "engine.mode.cli.description":
    "Reutilize um agente CLI já instalado e autenticado nesta máquina. Cobrado na sua assinatura existente.",
  "engine.provider": "Provedor",
  "engine.adapterLater": " — adapter chega depois",
  "engine.model": "Modelo",
  "engine.offlineSuggestions": "{count} sugestões offline",
  "engine.modelHint.kiro":
    "O RevAI passa exatamente este modelo para o Kiro CLI 2.18+ e executa um agente isolado, somente leitura, com MCP e ferramentas desabilitadas.",
  "engine.modelHint.custom":
    "IDs personalizados são passados como estão. Confirme o id no painel do seu provedor antes de executar uma revisão.",
  "engine.modelHint.catalogue":
    "Estas são sugestões offline. Catálogos de modelos dos provedores mudam com frequência; use Personalizado quando o seu provedor listar um id mais novo.",
  "engine.customModel": "Personalizado…",
  "engine.customModelAria": "Id do modelo personalizado",
  "engine.recommended": " — recomendado",
  "engine.baseUrl": "URL base",
  "engine.optional": "opcional",
  "engine.baseUrlHint":
    "Substitui o endpoint do provedor selecionado por um proxy ou serviço self-hosted.",
  "engine.apiKey": "Chave de API",
  "engine.storedApiKeys": "Chaves de API armazenadas",
  "engine.keyFor": "Chave para {provider}",
  "engine.keyStoredNote": "armazenada com chmod 600",
  "engine.keyHint.before": "Gravada em",
  "engine.keyHint.after":
    ", nunca dentro de uma pasta de projeto e nunca em git. A chave nunca é retornada pela API depois de armazenada.",
  "engine.storing": "Armazenando…",
  "engine.store": "Armazenar",
  "engine.storedKeys": "Chaves armazenadas",
  "engine.remove": "Remover",
  "engine.couldNotSave": "Não foi possível salvar",
  "engine.couldNotStoreKey": "Não foi possível armazenar a chave",
  "engine.couldNotRemoveKey": "Não foi possível remover a chave",

  // --- budget ---------------------------------------------------------------
  "engine.budgetCard": "Orçamento & limites",
  "engine.budgetHardStops": "limites rígidos",
  "engine.maxSpend": "Gasto máximo por revisão",
  "engine.noLimit": "sem limite",
  "engine.abortsWhenExceeded": "interrompe ao exceder",
  "engine.warnAbove": "Avisar acima de",
  "engine.asksConfirmation": "pede confirmação",
  "engine.contextBudget": "Orçamento de contexto",
  "engine.tokensSent": "tokens enviados ao modelo",
  "engine.requestTimeout": "Tempo limite de requisição",
  "engine.seconds": "segundos",
  "engine.timeoutHint":
    "O Kiro CLI não tem timeout próprio, então o RevAI impõe este.",
  "engine.concurrentReviews": "Revisões concorrentes",
  "engine.localQueue": "fila local",
  "engine.queueHint":
    "Revisões adicionais aguardam com segurança até que uma revisão em execução libere uma vaga.",
  "engine.retryFailures": "Repetir falhas transitórias",
  "engine.sameProvider": "mesmo provedor",
  "engine.retryHint":
    "Repete apenas timeouts, limites de taxa e falhas de transporte. Nunca troca de modelo silenciosamente.",
  "engine.unlimited": "Ilimitado",
  "engine.unlimitedPlaceholder": "Ilimitado",
  "engine.noCapEnforced": "— nenhum limite será aplicado",
  "engine.unit.tokens": "tokens",
  "engine.unit.sec": "seg",
  "engine.unit.runs": "execuções",
  "engine.unit.retries": "tentativas",
  "engine.warn.both": "Gasto e contexto estão ambos ilimitados",
  "engine.warn.spend": "O gasto está ilimitado",
  "engine.warn.context": "O tamanho do contexto está ilimitado",
  "engine.warn.spendBody":
    "Uma revisão executará até o fim, custe o que custar. Em um repositório grande com um modelo caro, isso pode custar dezenas de dólares em uma única execução.",
  "engine.warn.contextBody":
    "Uma única requisição pode enviar o diff inteiro, o que pode exceder a janela de contexto do modelo e falhar depois que você já pagou pela entrada.",
  "engine.warn.keepThreshold":
    "Mantenha o limite de aviso configurado para ainda ser questionado antes de uma execução cara.",
  "engine.warn.thresholdAboveCap":
    "O limite de aviso está acima do teto rígido, então nunca dispararia. O backend rejeitará isto.",

  // --- deterministic stage --------------------------------------------------
  "engine.deterministicCard": "Etapa determinística",
  "engine.deterministicIntro":
    "Estes analisadores executam antes do modelo e não custam tokens de IA. Os resultados são mesclados por identidade estável após a análise; ferramentas indisponíveis são reportadas como degradadas em vez de aparecerem silenciosamente como bem-sucedidas.",
  "engine.analyser.builtinSecurity": "Segurança integrada",
  "engine.analyser.builtinSecurityDetail": "APIs de execução perigosa",
  "engine.analyser.semgrep": "Semgrep",
  "engine.analyser.semgrepDetail": "padrões de segurança",
  "engine.analyser.ruff": "Ruff",
  "engine.analyser.ruffDetail": "python",
  "engine.analyser.eslint": "ESLint",
  "engine.analyser.eslintDetail": "javascript / typescript",
  "engine.analyser.gitleaks": "Gitleaks",
  "engine.analyser.gitleaksDetail": "segredos vazados",
  "engine.analyser.treesitter": "tree-sitter",
  "engine.analyser.treesitterDetail": "AST, integrado",
  "engine.analyser.checkstyle": "Checkstyle",
  "engine.analyser.checkstyleDetail": "java",
  "engine.analyser.projectTests": "Testes do projeto",
  "engine.analyser.projectTestsDetail": "configurado por projeto",
  "engine.analyser.projectBuild": "Build do projeto",
  "engine.analyser.projectBuildDetail": "configurado por projeto",
  "engine.sonar.title": "SonarQube Server / Community Build",
  "engine.sonar.detail":
    "Varredura ciente da ferramenta de build, espera do Compute Engine, issues de código novo e quality gate.",
  "engine.sonar.enable": "Ativar SonarQube",
  "engine.sonar.serverUrl": "URL do servidor",
  "engine.sonar.projectKey": "Chave do projeto",
  "engine.sonar.scanner": "Scanner",
  "engine.sonar.scanner.auto": "Automático — prefere Maven/Gradle",
  "engine.sonar.scanner.maven": "Maven",
  "engine.sonar.scanner.gradle": "Gradle",
  "engine.sonar.scanner.cli": "CLI genérico",
  "engine.sonar.newCodeOnly": "Apenas issues de código novo",
  "engine.sonar.qualityGate": "Exigir quality gate",
  "engine.behaviour.skip_noise": "Ignorar ruído automaticamente",
  "engine.behaviour.skip_noise_hint":
    "Descarta lockfiles, código gerado, bundles minificados, snapshots e binários antes de qualquer outra coisa.",
  "engine.behaviour.changed_lines_only": "Revisar apenas linhas alteradas",
  "engine.behaviour.changed_lines_only_hint":
    "Linhas de contexto são enviadas para compreensão, mas nunca reportadas como achados.",
  "engine.behaviour.dedupe_across_sources": "Mesclar achados duplicados",
  "engine.behaviour.dedupe_across_sources_hint":
    "Quando um linter e o modelo reportam o mesmo problema, mantém o de maior confiança e mescla a explicação.",

  // --- provider panel -------------------------------------------------------
  "engine.providerStatus": "Status dos provedores",
  "engine.usableCount": "{usable} de {total} utilizáveis",
  "engine.state.ready": "Pronto",
  "engine.state.needs_auth": "Precisa de login",
  "engine.state.unknown": "Desconhecido",
  "engine.state.not_found": "Não instalado",
  "engine.state.error": "Erro",
  "engine.providerSelected": "Selecionado",
  "engine.probingNote":
    "A verificação nunca gasta tokens de modelo: APIs hospedadas validam pelo endpoint de lista de modelos, enquanto agentes locais informam versão e estado de autenticação.",
  "engine.rescan": "Re-escanear",
  "engine.test": "Testar",
  "engine.testing": "Testando…",
  "engine.fix": "Correção:",
  "engine.adapterNotReady":
    "O RevAI ainda não consegue controlar este provedor, mesmo que esteja instalado e autenticado — o adapter chega em uma fase posterior.",
  "engine.probingHealth":
    "Verificando a saúde dos provedores — agentes locais podem levar alguns segundos para iniciar.",
  "engine.couldNotReachApi": "Não foi possível acessar a API",

  // --- insights -------------------------------------------------------------
  "insights.title": "Saúde do código, medida.",
  "insights.subtitle":
    "Todas as revisões que você executou, agregadas dos arquivos YAML no seu disco. Sem conta em nuvem, telemetria ou upload de repositório.",
  "insights.periodAria": "Período de indicadores",
  "insights.loadError": "Não foi possível carregar os indicadores.",
  "insights.kpi.reviewsRun": "Revisões executadas",
  "insights.kpi.completed": "{count} concluídas",
  "insights.kpi.issuesCaught": "Problemas detectados",
  "insights.kpi.criticalOpen": "{count} críticos abertos",
  "insights.kpi.totalSpend": "Gasto total",
  "insights.kpi.acrossReviews": "Nas revisões selecionadas",
  "insights.kpi.medianDuration": "Duração mediana",
  "insights.kpi.perReview": "Por revisão",
  "insights.findingsOverTime": "Achados ao longo do tempo",
  "insights.latest12": "Últimas 12 revisões",
  "insights.byCategory": "Por categoria",
  "insights.total": "{count} no total",
  "insights.debtTitle": "Retrato da dívida técnica",
  "insights.debtDescription":
    "A saúde atual usa a revisão mais recente de cada repositório no período selecionado. Uma pontuação de 100 significa que essa revisão não tem achados pendentes.",
  "insights.debt.openCritical": "Críticos abertos",
  "insights.debt.resolved": "Resolvidos",
  "insights.debt.fixRate": "Taxa de correção",
  "insights.repositoryBreakdown": "Detalhamento por repositório",
  "insights.tracked": "{count} rastreados",
  "insights.category.security": "Segurança",
  "insights.category.bug": "Corretude",
  "insights.category.performance": "Performance",
  "insights.category.maintainability": "Manutenibilidade",
  "insights.category.style": "Estilo",
  "insights.legend.critical": "Crítico",
  "insights.legend.medium": "Médio",
  "insights.legend.low": "Baixo",
  "insights.openFindingsTooltip": "{project}: {count} achados abertos",
  "insights.trendEmpty":
    "Execute uma revisão para começar a medir achados ao longo do tempo.",
  "insights.repoEmpty":
    "Abra um repositório para incluí-lo nos indicadores de saúde do código.",
  "insights.table.repository": "Repositório",
  "insights.table.reviews": "Revisões",
  "insights.table.open": "Abertos",
  "insights.table.critical": "Críticos",
  "insights.table.health": "Saúde",
  "insights.table.change": "Variação",
  "insights.languageUnknown": "linguagem desconhecida",
  "insights.new": "novo",

  // --- data / export --------------------------------------------------------
  "data.title": "Exportação & dados",
  "data.subtitle":
    "Baixe relatórios individuais ou um arquivo portátil completo. As exportações são geradas localmente a partir do YAML e nunca incluem credenciais de API.",
  "data.unavailable": "Dados indisponíveis",
  "data.exportCard": "Exportação & dados",
  "data.reviewHistory": "Histórico de revisões",
  "data.reviewsCount": "{count} revisões",
  "data.exportEverything": "Exportar tudo",
  "data.exportEverythingDetail":
    "Configuração, regras, projetos e todas as revisões como JSON portátil.",
  "data.credentialSafety": "Segurança das credenciais",
  "data.credentialSafetyDetail":
    "Credenciais de API, caches e conteúdo dos repositórios nunca são incluídos nos arquivos.",
  "data.excluded": "Excluídos",
  "data.buildingArchive": "Gerando arquivo…",
  "data.exported": "Exportado",
  "data.exportZip": "Exportar .zip",
  "data.exportError": "Não foi possível exportar os dados.",
  "data.recentExports": "Exportações recentes de revisões",
  "data.recentExportsDetail":
    "JSON e SARIF para automação, Markdown para pull requests, ou um relatório HTML offline autônomo.",
  "data.runReviewFirst":
    "Execute uma revisão antes de exportar um relatório.",
  "data.findingsCount": "{count} achados",
  "data.workingTree": "árvore de trabalho",
  "data.unknownProject": "Projeto desconhecido",
  "data.legacy": "Legado",

  // --- status values --------------------------------------------------------
  "status.completed": "concluída",
  "status.failed": "falhou",
  "status.aborted": "cancelada",
  "status.degraded": "degradada",
  "status.running": "em execução",

  // --- model catalogue ------------------------------------------------------
  "models.note.longDiffs": "forte em diffs longos",
  "models.note.highestQuality": "maior qualidade",
  "models.note.fastAndCheap": "rápido e barato",
  "models.note.frontierCoding": "codificação de fronteira",
  "models.note.balanced": "equilibrado",
  "models.note.largeContext": "contexto amplo",
  "models.note.veryLargeContext": "contexto muito amplo",
  "models.note.fast": "rápido",
  "models.note.openWeights": "pesos abertos",
  "models.note.codeSpecialist": "especialista em código",
  "models.note.fastAndCapable": "rápido e capaz",
  "models.note.lowestCost": "menor custo",
  "models.note.fastest": "o mais rápido",
  "models.note.cheapest": "o mais barato",
  "models.note.cliDefault": "padrão do CLI",
  "models.note.letCopilotChoose": "deixe o Copilot escolher",
  "models.note.fastAndCostEfficient": "rápido e econômico",
  "models.note.strongerReasoning": "raciocínio mais forte",
  "models.note.auto": "Automático",

  // --- logo -----------------------------------------------------------------
  "logo.aria": "RevAI — ir para o painel",
};
