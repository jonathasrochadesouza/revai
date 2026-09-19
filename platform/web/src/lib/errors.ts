/**
 * Error catalog — the frontend half of the `{ error_key, params }` contract.
 *
 * The backend raises a stable, dot-namespaced `error_key` plus raw `params`
 * (numbers, strings, paths — never pre-formatted text). This module owns all
 * phrasing: one entry per key, both locales side by side, `{param}`
 * placeholders interpolated here with locale-aware number/currency formatting.
 *
 * An unmapped key (a backend hotfix the frontend hasn't caught up to yet)
 * resolves to a generic per-locale sentence carrying the raw key, so nothing
 * degrades into a blank screen or a raw traceback.
 */

import type { Locale } from "@/lib/i18n";

/** The structured `detail` body the API renders for every application error. */
export interface ApiErrorDetail {
  error_key: string;
  params: Record<string, string | number | boolean | null>;
}

/** Parameters whose value is a USD amount and must be formatted as currency. */
const CURRENCY_PARAMS = new Set([
  "estimated_cost_usd",
  "max_spend_usd",
  "warn_above_usd",
  "cost_usd",
]);

/**
 * Every `error_key` the backend can raise. Kept alphabetically by domain so a
 * new key lands in the right place and a missing one is visible at a glance.
 */
export const ERROR_CATALOG: Record<string, { en: string; pt: string }> = {
  // --- ai pipeline -----------------------------------------------------------
  "ai_pipeline.invalid_findings": {
    en: "The model returned findings that failed validation ({detail}).",
    pt: "A resposta do modelo falhou na validação dos achados ({detail}).",
  },
  "ai_pipeline.no_json_findings_object": {
    en: "The model response contained no findings object.",
    pt: "A resposta do modelo não contém o objeto de achados esperado.",
  },
  "ai_pipeline.provider_failed": {
    en: "The AI provider request failed ({detail}).",
    pt: "A chamada ao provedor de IA falhou ({detail}).",
  },
  "ai_pipeline.stream_ended_without_response": {
    en: "The provider stream ended before returning a response.",
    pt: "O stream do provedor terminou sem responder.",
  },

  // --- budget ----------------------------------------------------------------
  "budget.context_exceeds_max": {
    en: "Estimated context of {estimated_tokens} tokens exceeds the context budget of {max_context_tokens}.",
    pt: "O contexto estimado de {estimated_tokens} tokens excede o orçamento de contexto de {max_context_tokens}.",
  },
  "budget.estimated_cost_exceeds_max": {
    en: "Estimated cost of {estimated_cost_usd} exceeds the maximum spend of {max_spend_usd}.",
    pt: "O custo estimado de {estimated_cost_usd} excede o gasto máximo de {max_spend_usd}.",
  },
  "budget.warn_above_exceeds_max": {
    en: "The warning threshold ({warn_above_usd}) cannot exceed the maximum spend ({max_spend_usd}).",
    pt: "O limite de aviso ({warn_above_usd}) não pode ser maior que o gasto máximo ({max_spend_usd}).",
  },

  // --- credentials -----------------------------------------------------------
  "credential.not_found": {
    en: "No stored credential for provider \"{provider_id}\".",
    pt: "Nenhuma credencial armazenada para o provedor \"{provider_id}\".",
  },

  // --- export ----------------------------------------------------------------
  "export.invalid_legacy_lines": {
    en: "Invalid legacy finding range: \"{lines}\".",
    pt: "Intervalo de linhas inválido no formato legado: \"{lines}\".",
  },
  "export.legacy_json_only": {
    en: "The {format} export is only available for the current format.",
    pt: "A exportação em {format} só está disponível no formato atual.",
  },

  // --- fix ---------------------------------------------------------------------
  "fix.already_applied": {
    en: "A fix for this finding was already applied to the working tree.",
    pt: "Uma correção para este achado já foi aplicada à árvore de trabalho.",
  },
  "fix.branch_mismatch": {
    en: "The review ran on branch \"{review_head}\", but the working tree is on \"{current_branch}\". Switch branches and try again.",
    pt: "A revisão rodou na branch \"{review_head}\", mas a árvore de trabalho está em \"{current_branch}\". Troque de branch e tente novamente.",
  },
  "fix.file_changed": {
    en: "\"{file}\" changed since the review ran. Re-run the review before applying a fix.",
    pt: "\"{file}\" mudou desde a revisão. Rode a revisão novamente antes de aplicar uma correção.",
  },
  "fix.file_missing": {
    en: "\"{file}\" does not exist in the working tree.",
    pt: "\"{file}\" não existe na árvore de trabalho.",
  },
  "fix.generation_failed": {
    en: "The AI provider request failed ({detail}).",
    pt: "A chamada ao provedor de IA falhou ({detail}).",
  },
  "fix.invalid_generation": {
    en: "The model returned a fix that failed validation ({detail}).",
    pt: "A correção retornada pelo modelo falhou na validação ({detail}).",
  },
  "fix.no_change_generated": {
    en: "The generated fix did not change \"{file}\".",
    pt: "A correção gerada não alterou \"{file}\".",
  },
  "fix.no_patch_available": {
    en: "This finding has no applicable patch. Generate one first.",
    pt: "Este achado não tem um patch aplicável. Gere um antes.",
  },
  "fix.patch_apply_failed": {
    en: "Applying the patch failed ({detail}).",
    pt: "Falha ao aplicar o patch ({detail}).",
  },
  "fix.patch_file_mismatch": {
    en: "The patch targets {patch_files}, not \"{finding_file}\".",
    pt: "O patch altera {patch_files}, e não \"{finding_file}\".",
  },
  "fix.patch_stale": {
    en: "The patch no longer applies to \"{file}\" ({detail}). Generate a new fix.",
    pt: "O patch não é mais aplicável a \"{file}\" ({detail}). Gere uma nova correção.",
  },
  "fix.patch_too_large": {
    en: "The generated patch for \"{file}\" is too large to apply.",
    pt: "O patch gerado para \"{file}\" é grande demais para aplicar.",
  },
  "fix.revert_failed": {
    en: "Applying the fix failed AND reverting it failed. Inspect \"{file}\" manually.",
    pt: "Aplicar a correção falhou E reverter falhou. Inspecione \"{file}\" manualmente.",
  },
  "fix.search_block_not_found": {
    en: "The generated fix does not match the current content of \"{file}\".",
    pt: "A correção gerada não corresponde ao conteúdo atual de \"{file}\".",
  },
  "fix.validation_failed": {
    en: "The fix was applied but failed re-validation and was reverted ({detail}).",
    pt: "A correção foi aplicada, mas falhou na revalidação e foi revertida ({detail}).",
  },

  // --- folder picker ---------------------------------------------------------
  "folder_picker.tk_not_installed": {
    en: "The system folder picker needs tkinter, which is not installed.",
    pt: "O seletor de pastas do sistema precisa do tkinter, que não está instalado.",
  },
  "folder_picker.unavailable_in_session": {
    en: "No desktop session is available for the folder picker.",
    pt: "Não há sessão gráfica disponível para o seletor de pastas.",
  },

  // --- git -------------------------------------------------------------------
  "git.cannot_derive_repository_name": {
    en: "Could not derive a repository name from \"{remote}\".",
    pt: "Não foi possível derivar o nome do repositório a partir de \"{remote}\".",
  },
  "git.command_failed": {
    en: "A Git command failed.",
    pt: "Um comando Git falhou.",
  },
  "git.destination_already_exists": {
    en: "Destination folder already exists: {destination}.",
    pt: "A pasta de destino já existe: {destination}.",
  },
  "git.files_not_tracked": {
    en: "These files are not tracked at ref \"{ref}\": {files}.",
    pt: "Estes arquivos não são rastreados no ref \"{ref}\": {files}.",
  },
  "git.folder_does_not_exist": {
    en: "Folder does not exist: {path}.",
    pt: "A pasta não existe: {path}.",
  },
  "git.materialize_ref_failed": {
    en: "Could not materialize ref \"{ref}\".",
    pt: "Não foi possível materializar o ref \"{ref}\".",
  },
  "git.no_commits_or_branches": {
    en: "The repository has no commits or branches yet: {path}.",
    pt: "O repositório ainda não tem commits ou branches: {path}.",
  },
  "git.not_a_repository": {
    en: "\"{path}\" is not inside a Git repository.",
    pt: "\"{path}\" não está dentro de um repositório Git.",
  },
  "git.not_installed": {
    en: "Git is not installed or is not on PATH.",
    pt: "O Git não está instalado ou não está no PATH.",
  },
  "git.timed_out": {
    en: "A Git command timed out after {timeout_s} s.",
    pt: "Um comando Git excedeu o tempo limite de {timeout_s} s.",
  },
  "git.unknown_ref": {
    en: "Unknown ref \"{ref}\".",
    pt: "Ref desconhecido \"{ref}\".",
  },

  // --- internal --------------------------------------------------------------
  "internal.unexpected_error": {
    en: "Something unexpected went wrong. Check the API logs.",
    pt: "Algo inesperado falhou. Verifique os logs da API.",
  },

  // --- project ---------------------------------------------------------------
  "project.command_has_empty_argument": {
    en: "The {command_name} command contains an empty argument.",
    pt: "O comando {command_name} contém um argumento vazio.",
  },
  "project.name_contains_path_separators": {
    en: "The project name must not contain path separators.",
    pt: "O nome do projeto não pode conter separadores de caminho.",
  },
  "project.not_found": {
    en: "Project \"{project_id}\" does not exist.",
    pt: "O projeto \"{project_id}\" não existe.",
  },
  "project.unknown_base_branch": {
    en: "Unknown base branch \"{base_branch}\".",
    pt: "Branch base desconhecida \"{base_branch}\".",
  },

  // --- prompt scenarios --------------------------------------------------------
  "prompt_scenario.duplicate_name": {
    en: "A scenario with this name already exists.",
    pt: "Já existe um cenário com esse nome.",
  },
  "prompt_scenario.not_found": {
    en: "Prompt scenario \"{scenario_id}\" does not exist.",
    pt: "O cenário de prompt \"{scenario_id}\" não existe.",
  },

  // --- providers ----------------------------------------------------------------
  "provider.no_probe_implemented": {
    en: "No readiness probe is implemented for provider \"{provider_id}\".",
    pt: "Não há verificação de disponibilidade implementada para o provedor \"{provider_id}\".",
  },
  "provider.not_ready": {
    en: "Provider \"{provider_id}\" is not usable right now.",
    pt: "O provedor \"{provider_id}\" não está utilizável agora.",
  },
  "provider.unavailable": {
    en: "No AI provider is configured or usable.",
    pt: "Nenhum provedor de IA está configurado ou utilizável.",
  },

  // --- reviews -------------------------------------------------------------------
  "review.finding_not_found": {
    en: "Finding \"{finding_id}\" does not exist in this review.",
    pt: "O achado \"{finding_id}\" não existe nesta revisão.",
  },
  "review.not_active": {
    en: "Review {review_id} is not running anymore.",
    pt: "A revisão {review_id} não está mais em execução.",
  },
  "review.not_found": {
    en: "Review \"{review_id}\" does not exist.",
    pt: "A revisão \"{review_id}\" não existe.",
  },
  "review.retry_static_endpoint": {
    en: "Static-only reviews cannot be retried through the AI endpoint.",
    pt: "Revisões apenas estáticas não podem ser reexecutadas pelo endpoint de IA.",
  },
  "review.selected_files_required": {
    en: "Select at least one file for the selected-files scope.",
    pt: "Selecione ao menos um arquivo para o escopo de arquivos selecionados.",
  },
  "review.static_only_endpoint": {
    en: "This endpoint runs AI reviews; static-only mode belongs to the static endpoint.",
    pt: "Este endpoint executa revisões com IA; o modo estático pertence ao endpoint estático.",
  },

  // --- sonarqube -----------------------------------------------------------------
  "sonarqube.admin_password_unknown": {
    en: "Could not recover the SonarQube admin password for {server_url}.",
    pt: "Não foi possível recuperar a senha de administrador do SonarQube em {server_url}.",
  },
  "sonarqube.boot_timeout": {
    en: "SonarQube did not finish booting in time ({server_url}).",
    pt: "O SonarQube não terminou de iniciar a tempo ({server_url}).",
  },
  "sonarqube.container_start_failed": {
    en: "Could not start the SonarQube container.",
    pt: "Não foi possível iniciar o contêiner do SonarQube.",
  },
  "sonarqube.docker_not_found": {
    en: "Docker was not found. Install Docker Desktop to run SonarQube locally.",
    pt: "O Docker não foi encontrado. Instale o Docker Desktop para rodar o SonarQube localmente.",
  },
  "sonarqube.docker_unavailable": {
    en: "The Docker daemon is not responding ({detail}).",
    pt: "O daemon do Docker não está respondendo ({detail}).",
  },
  "sonarqube.no_credentials": {
    en: "SonarQube credentials are not provisioned yet.",
    pt: "As credenciais do SonarQube ainda não foram provisionadas.",
  },
  "sonarqube.password_change_failed": {
    en: "Could not change the SonarQube admin password ({server_url}).",
    pt: "Não foi possível alterar a senha de administrador do SonarQube ({server_url}).",
  },
  "sonarqube.port_conflict": {
    en: "Another service already answers on {server_url}.",
    pt: "Outro serviço já responde em {server_url}.",
  },
  "sonarqube.project_create_failed": {
    en: "Could not create SonarQube project \"{project_key}\".",
    pt: "Não foi possível criar o projeto SonarQube \"{project_key}\".",
  },
  "sonarqube.pull_failed": {
    en: "Could not pull the SonarQube image.",
    pt: "Não foi possível baixar a imagem do SonarQube.",
  },
  "sonarqube.server_unreachable": {
    en: "SonarQube at {server_url} is unreachable ({detail}).",
    pt: "O SonarQube em {server_url} está inacessível ({detail}).",
  },
  "sonarqube.start_in_progress": {
    en: "A SonarQube start flow is already running.",
    pt: "Um fluxo de inicialização do SonarQube já está em andamento.",
  },
  "sonarqube.token_failed": {
    en: "Could not generate the SonarQube token for {server_url}.",
    pt: "Não foi possível gerar o token do SonarQube em {server_url}.",
  },

  // --- storage ---------------------------------------------------------------------
  "storage.empty_identifier": {
    en: "An empty identifier cannot name a stored document.",
    pt: "Um identificador vazio não pode nomear um documento armazenado.",
  },
  "storage.invalid_identifier_characters": {
    en: "Identifier \"{identifier}\" contains characters that are not allowed.",
    pt: "O identificador \"{identifier}\" contém caracteres não permitidos.",
  },
  "storage.invalid_schema_version": {
    en: "{filename} has a schema_version that cannot be read.",
    pt: "O arquivo {filename} tem um schema_version ilegível.",
  },
  "storage.invalid_yaml": {
    en: "{filename} is not valid YAML.",
    pt: "O arquivo {filename} não é um YAML válido.",
  },
  "storage.lock_timeout": {
    en: "{filename} stayed locked for more than {timeout_s} s.",
    pt: "O arquivo {filename} ficou bloqueado por mais de {timeout_s} s.",
  },
  "storage.not_a_mapping": {
    en: "{filename} must contain a YAML mapping, not {found_type}.",
    pt: "O arquivo {filename} deve conter um mapeamento YAML, não {found_type}.",
  },
  "storage.read_failed": {
    en: "Could not read {path}.",
    pt: "Não foi possível ler {path}.",
  },
  "storage.schema_mismatch": {
    en: "{filename} no longer matches the expected shape.",
    pt: "O arquivo {filename} não corresponde mais ao formato esperado.",
  },
  "storage.schema_version_from_the_future": {
    en: "{filename} was written by a newer RevAI build (schema {found}); update the app.",
    pt: "O arquivo {filename} foi gravado por um RevAI mais novo (schema {found}); atualize o app.",
  },
  "storage.serialize_failed": {
    en: "Could not serialize {filename}.",
    pt: "Não foi possível serializar o arquivo {filename}.",
  },
  "storage.unsupported_schema_version": {
    en: "{filename} uses schema {found}, which has no migration to schema {target}.",
    pt: "O arquivo {filename} usa o schema {found}, sem migração para o schema {target}.",
  },
  "storage.write_failed": {
    en: "Could not write {path}.",
    pt: "Não foi possível gravar {path}.",
  },
  "storage.write_unencodable_character": {
    en: "{path} contains a character that cannot be encoded as UTF-8 ({character}).",
    pt: "O arquivo {path} contém um caractere que não pode ser codificado em UTF-8 ({character}).",
  },

  // --- validation ---------------------------------------------------------------------
  "validation.invalid_field": {
    en: "The field {field} is invalid.",
    pt: "O campo {field} é inválido.",
  },
};

/** Human sentences shown when a key is not in the catalog yet. */
const FALLBACK: Record<Locale, string> = {
  "en-US": "Something went wrong.",
  "pt-BR": "Algo deu errado.",
};

/**
 * Locale-aware parameter rendering: numbers via `Intl.NumberFormat`, known
 * USD params as currency, booleans/null as plain strings. Unknown params are
 * dropped from the sentence rather than leaking `{placeholders}`.
 */
function formatParam(
  name: string,
  value: string | number | boolean | null,
  locale: Locale,
): string {
  if (value === null || value === false) return "";
  if (value === true) return name;
  if (typeof value === "number") {
    if (CURRENCY_PARAMS.has(name)) {
      return new Intl.NumberFormat(locale === "pt-BR" ? "pt-BR" : "en-US", {
        style: "currency",
        currency: "USD",
      }).format(value);
    }
    return new Intl.NumberFormat(locale === "pt-BR" ? "pt-BR" : "en-US").format(value);
  }
  return value;
}

function interpolate(template: string, params: Record<string, string | number | boolean | null>, locale: Locale): string {
  return template
    .replace(/\{(\w+)\}/g, (token, name: string) =>
      Object.prototype.hasOwnProperty.call(params, name) && params[name] !== undefined
        ? formatParam(name, params[name], locale)
        : "",
    )
    .replace(/  +/g, " ")
    .trim();
}

/** Resolve one structured detail into a human sentence. */
export function resolveErrorDetail(
  detail: ApiErrorDetail,
  locale: Locale,
): string {
  const entry = ERROR_CATALOG[detail.error_key];
  if (!entry) {
    // Unmapped future key: degrade to a generic sentence + the raw key so a
    // bug report still names the failure.
    const generic = FALLBACK[locale];
    return locale === "pt-BR" ? `${generic} (${detail.error_key})` : `${generic} (${detail.error_key})`;
  }
  return interpolate(entry[locale === "pt-BR" ? "pt" : "en"], detail.params, locale);
}

/**
 * Resolve an array detail (multi-field validation failures), each entry
 * individually, joined with "; ".
 */
export function resolveErrorDetails(
  detail: ApiErrorDetail | ApiErrorDetail[],
  locale: Locale,
): string {
  const list = Array.isArray(detail) ? detail : [detail];
  return list.map((item) => resolveErrorDetail(item, locale)).join("; ");
}

/**
 * Resolve any thrown value into a human sentence.
 *
 * `ApiError` instances carrying the structured contract are resolved through
 * the catalog; plain `Error`s (network failures, SSE quirks) surface their
 * message as-is; anything else gets the generic fallback. Structural check on
 * `errorKey` keeps this module independent of `lib/api.ts` (no import cycle).
 */
export function resolveApiError(error: unknown, locale: Locale): string {
  if (
    error &&
    typeof error === "object" &&
    typeof (error as { message?: unknown }).message === "string"
  ) {
    const candidate = error as {
      message: string;
      errorKey?: unknown;
      params?: Record<string, string | number | boolean | null>;
    };
    if (typeof candidate.errorKey === "string") {
      return resolveErrorDetail(
        { error_key: candidate.errorKey, params: candidate.params ?? {} },
        locale,
      );
    }
    return candidate.message;
  }
  return FALLBACK[locale];
}
