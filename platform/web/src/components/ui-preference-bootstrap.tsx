"use client";

import { createContext, type ReactNode, useContext, useEffect, useMemo, useState } from "react";

import { api, type UiConfig } from "@/lib/api";

type Locale = UiConfig["locale"];
type Translator = (english: string) => string;

const PT_BR: Record<string, string> = {
  Projects: "Projetos",
  Insights: "Indicadores",
  Data: "Dados",
  Appearance: "Aparência",
  Settings: "Configurações",
  Menu: "Menu",
  "Primary navigation": "Navegação principal",
  Breadcrumb: "Navegação estrutural",
  "Review setup": "Configurar revisão",
  Review: "Revisão",
  "Configure a review": "Configure uma revisão",
  "All projects": "Todos os projetos",
  "Project unavailable": "Projeto indisponível",
  "Back to projects": "Voltar aos projetos",
  "Search projects": "Buscar projetos",
  "Add a repository": "Adicionar um repositório",
  "Your projects": "Seus projetos",
  Repository: "Repositório",
  Branch: "Branch",
  Languages: "Linguagens",
  Added: "Adicionado",
  "Open local folder": "Abrir pasta local",
  "Clone from remote": "Clonar repositório remoto",
  "Review mode": "Modo de revisão",
  Scope: "Escopo",
  Base: "Base",
  Head: "Head",
  "Default base branch": "Branch base padrão",
  "Search branches": "Pesquisar branches",
  "No branches match your search.": "Nenhuma branch corresponde à pesquisa.",
  Preview: "Prévia",
  Cancel: "Cancelar",
  "Run again": "Executar novamente",
  "Tracked files": "Arquivos rastreados",
  Changed: "Alterados",
  All: "Todos",
  selected: "selecionados",
  "Search files": "Pesquisar arquivos",
  "Clear file search": "Limpar pesquisa de arquivos",
  "Show flat list": "Mostrar lista direta",
  "Show folder tree": "Mostrar árvore de pastas",
  "Expand all folders": "Expandir todas as pastas",
  "Collapse all folders": "Recolher todas as pastas",
  "Flat list": "Lista direta",
  "No files match your search.": "Nenhum arquivo corresponde à pesquisa.",
  "No changed files.": "Nenhum arquivo alterado.",
  "No tracked files.": "Nenhum arquivo rastreado.",
  "Not at Head": "Fora do Head",
  "This path is not tracked at Head. Use Branch diff to review it.":
    "Este caminho não está rastreado no Head. Use o diff entre branches para revisá-lo.",
  "Configure another review": "Configurar outra revisão",
  "Run static review": "Executar revisão estática",
  "Run AI review": "Executar revisão com IA",
  "Run combined review": "Executar revisão combinada",
  "Review history": "Histórico de revisões",
  Findings: "Achados",
  Analyzers: "Analisadores",
  "Event stream": "Eventos",
  "Project quality commands": "Comandos de qualidade do projeto",
  "optional · shell disabled": "opcional · shell desabilitado",
  "Use JSON argument arrays so paths with spaces remain safe, for example":
    "Use arrays JSON de argumentos para manter seguros os caminhos com espaços, por exemplo",
  Checkstyle: "Checkstyle",
  Tests: "Testes",
  Build: "Build",
  "More information about": "Mais informações sobre",
  "Checks configured Java style and static-code rules.":
    "Verifica as regras configuradas de estilo Java e análise estática.",
  "Runs the project's test suite to detect failures and regressions.":
    "Executa a suíte de testes do projeto para detectar falhas e regressões.",
  "Compiles or packages the project to validate dependencies, types, and generated artifacts.":
    "Compila ou empacota o projeto para validar dependências, tipos e artefatos gerados.",
  "Saving…": "Salvando…",
  "Save project commands": "Salvar comandos do projeto",
  "Branch diff": "Diff entre branches",
  "Selected files": "Arquivos selecionados",
  "Whole project": "Projeto inteiro",
  "Static only": "Somente análise estática",
  "AI-assisted": "Assistida por IA",
  Both: "Ambas",
  Completed: "Concluída",
  Failed: "Falhou",
  Cancelled: "Cancelada",
  Reviewing: "Revisando",
};

const UiLocaleContext = createContext<{ locale: Locale; t: Translator }>({
  locale: "en-US",
  t: (value) => value,
});

export function UiPreferenceProvider({ children }: { children: ReactNode }) {
  const [locale, setLocale] = useState<Locale>("en-US");
  useEffect(() => {
    const apply = (config: UiConfig) => {
      document.documentElement.dataset.theme = config.theme;
      document.documentElement.lang = config.locale;
      setLocale(config.locale);
    };
    void api.getConfig().then(({ config }) => apply(config.ui)).catch(() => undefined);
    const changed = (event: Event) => apply((event as CustomEvent<UiConfig>).detail);
    window.addEventListener("revai:ui-preferences", changed);
    return () => window.removeEventListener("revai:ui-preferences", changed);
  }, []);
  const value = useMemo(
    () => ({
      locale,
      t: (english: string) => locale === "pt-BR" ? (PT_BR[english] ?? english) : english,
    }),
    [locale],
  );
  return <UiLocaleContext.Provider value={value}>{children}</UiLocaleContext.Provider>;
}

export function useUiText() {
  return useContext(UiLocaleContext);
}
