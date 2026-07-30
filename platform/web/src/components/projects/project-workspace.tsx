"use client";

import {
  ArrowRight,
  Boxes,
  Check,
  CircleAlert,
  CircleCheck,
  CircleDollarSign,
  CircleX,
  Code2,
  Copy,
  File,
  Files,
  FolderOpen,
  FolderGit2,
  GitBranch,
  GitCompareArrows,
  HardDrive,
  LoaderCircle,
  ScanSearch,
  Search,
  X,
} from "lucide-react";
import {
  type FormEvent,
  type KeyboardEvent as ReactKeyboardEvent,
  type ReactElement,
  type ReactNode,
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import {
  ApiError,
  api,
  type AnalyzerRun,
  type DeterministicReview,
  type DiffPreview,
  type Finding,
  type Project,
  type ProjectTree,
  type Severity,
} from "@/lib/api";

type ProjectFilter = "all" | "active" | "archived";
type DialogMode = "open" | "clone" | null;

const AVATAR_TONES = [
  "bg-low-surface text-low border-low-line",
  "bg-success-surface text-success border-success-line",
  "bg-medium-surface text-medium border-medium-line",
  "bg-critical-surface text-critical border-critical-line",
] as const;

function initials(name: string): string {
  return name
    .split(/[-_\s]+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0])
    .join("")
    .toUpperCase();
}

function relativeDate(value: string): string {
  const elapsed = Date.now() - new Date(value).getTime();
  const minutes = Math.floor(elapsed / 60_000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

function formatTokens(tokens: number): string {
  if (tokens < 1_000) return String(tokens);
  return `${(tokens / 1_000).toFixed(tokens < 10_000 ? 1 : 0)}k`;
}

function displayError(error: unknown): string {
  if (error instanceof ApiError || error instanceof Error) return error.message;
  return "Something went wrong while talking to the local API.";
}

export function ProjectWorkspace({
  initialProjects,
  initialError,
}: {
  initialProjects: Project[];
  initialError?: string;
}) {
  const [projects, setProjects] = useState(initialProjects);
  const [query, setQuery] = useState("");
  const [filter, setFilter] = useState<ProjectFilter>("all");
  const [selectedId, setSelectedId] = useState<string | null>(
    initialProjects[0]?.id ?? null,
  );
  const [dialog, setDialog] = useState<DialogMode>(null);
  const [notice, setNotice] = useState<string | null>(initialError ?? null);
  const searchRef = useRef<HTMLInputElement>(null);

  const selected =
    projects.find((project) => project.id === selectedId) ?? null;

  const visibleProjects = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    return projects.filter((project) => {
      if (filter === "active" && project.archived) return false;
      if (filter === "archived" && !project.archived) return false;
      return (
        !normalized ||
        project.name.toLowerCase().includes(normalized) ||
        project.path.toLowerCase().includes(normalized) ||
        project.current_branch?.toLowerCase().includes(normalized)
      );
    });
  }, [filter, projects, query]);

  useEffect(() => {
    const focusSearch = (event: globalThis.KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        searchRef.current?.focus();
      }
    };
    window.addEventListener("keydown", focusSearch);
    return () => window.removeEventListener("keydown", focusSearch);
  }, []);

  const refresh = useCallback(async (project?: Project) => {
    const response = await api.getProjects();
    setProjects(response.projects);
    if (project) setSelectedId(project.id);
  }, []);

  return (
    <main className="mx-auto w-full max-w-[1280px] px-5 pb-20 pt-9 sm:px-7">
      <section className="mb-8 flex flex-col justify-between gap-5 lg:flex-row lg:items-start">
        <div>
          <h1 className="mb-1.5 text-[29px] font-bold leading-tight">
            Projects
          </h1>
          <p className="max-w-[64ch] text-[14px] leading-relaxed text-ink-muted">
            Open a repository to inspect its branches and changes. Source stays
            on this machine.
          </p>
        </div>
        <label className="flex h-10 w-full items-center gap-2.5 rounded-control border border-line-strong bg-paper px-3 text-ink-subtle lg:w-[310px]">
          <Search aria-hidden className="size-4 shrink-0" strokeWidth={1.8} />
          <span className="sr-only">Search projects</span>
          <input
            ref={searchRef}
            value={query}
            onChange={(event) => setQuery(event.target.value)}
            placeholder="Search projects"
            className="min-w-0 flex-1 bg-transparent text-[13px] text-ink outline-none placeholder:text-ink-subtle"
          />
          <kbd className="rounded-chip border border-line px-1.5 py-0.5 text-[10px]">
            Ctrl K
          </kbd>
        </label>
      </section>

      {notice && (
        <div
          role="status"
          className="mb-5 flex items-start gap-3 rounded-control border border-critical-line bg-critical-surface px-4 py-3 text-[12.5px] text-critical"
        >
          <span className="flex-1">{notice}</span>
          <button
            type="button"
            onClick={() => setNotice(null)}
            aria-label="Dismiss message"
            className="rounded-chip p-0.5 hover:bg-paper"
          >
            <X className="size-3.5" />
          </button>
        </div>
      )}

      <section aria-label="Add a repository" className="mb-8 grid gap-3 md:grid-cols-2">
        <EntryAction
          icon={<HardDrive className="size-5" strokeWidth={1.8} />}
          title="Open local folder"
          description="Point RevAI at a Git repository already on this machine."
          action="Browse or enter path"
          onClick={() => setDialog("open")}
        />
        <EntryAction
          icon={<Copy className="size-5" strokeWidth={1.8} />}
          title="Clone from remote"
          description="Clone an HTTPS, SSH, or local Git remote into a folder you choose."
          action="Choose URL and folder"
          onClick={() => setDialog("clone")}
        />
      </section>

      <section className="surface overflow-hidden">
        <div className="flex min-h-14 flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-3">
          <h2 className="flex items-center gap-2 text-[14px] font-semibold">
            Your projects
            <span className="numeric rounded-chip bg-canvas px-2 py-0.5 text-[10.5px] font-medium text-ink-muted">
              {projects.length}
            </span>
          </h2>
          <div className="flex rounded-control bg-canvas p-0.5">
            {(["all", "active", "archived"] as const).map((value) => (
              <button
                key={value}
                type="button"
                onClick={() => setFilter(value)}
                aria-pressed={filter === value}
                className={`rounded-chip px-3 py-1.5 text-[11.5px] font-medium capitalize transition-colors ${
                  filter === value
                    ? "border border-line bg-paper text-ink"
                    : "border border-transparent text-ink-subtle hover:text-ink"
                }`}
              >
                {value}
              </button>
            ))}
          </div>
        </div>

        <div className="hidden grid-cols-[minmax(260px,1fr)_180px_170px_90px] gap-4 border-b border-line bg-sunken px-5 py-2.5 text-[10px] font-semibold uppercase text-ink-subtle md:grid">
          <span>Repository</span>
          <span>Branch</span>
          <span>Languages</span>
          <span className="text-right">Added</span>
        </div>

        {visibleProjects.length ? (
          visibleProjects.map((project, index) => (
            <button
              key={project.id}
              type="button"
              onClick={() => setSelectedId(project.id)}
              className={`grid w-full gap-3 border-b border-line px-5 py-4 text-left transition-colors last:border-b-0 hover:bg-canvas md:grid-cols-[minmax(260px,1fr)_180px_170px_90px] md:items-center md:gap-4 ${
                selectedId === project.id ? "bg-low-surface/50" : "bg-paper"
              }`}
            >
              <span className="flex min-w-0 items-center gap-3">
                <span
                  className={`grid size-9 shrink-0 place-items-center rounded-control border text-[11px] font-bold ${AVATAR_TONES[index % AVATAR_TONES.length]}`}
                >
                  {initials(project.name)}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-[13.5px] font-semibold">
                    {project.name}
                  </span>
                  <span className="numeric block truncate text-[10.5px] text-ink-subtle">
                    {project.path}
                  </span>
                </span>
              </span>
              <span className="flex min-w-0 items-center gap-1.5 font-mono text-[11.5px] text-ink-muted">
                <GitBranch className="size-3.5 shrink-0 text-low" />
                <span className="truncate">
                  {project.current_branch ?? "detached HEAD"}
                </span>
              </span>
              <span className="truncate text-[11.5px] text-ink-muted">
                {project.languages.join(", ") || "Not detected"}
              </span>
              <span className="numeric text-[11px] text-ink-subtle md:text-right">
                {relativeDate(project.created_at)}
              </span>
            </button>
          ))
        ) : (
          <EmptyProjects
            hasProjects={projects.length > 0}
            onOpen={() => setDialog("open")}
          />
        )}
      </section>

      {selected && (
        <RepositoryInspector
          key={selected.id}
          project={selected}
          onError={setNotice}
        />
      )}

      {dialog && (
        <RepositoryDialog
          mode={dialog}
          onClose={() => setDialog(null)}
          onCreated={async (project) => {
            setDialog(null);
            setNotice(null);
            try {
              await refresh(project);
            } catch (error) {
              setNotice(displayError(error));
            }
          }}
        />
      )}
    </main>
  );
}

function EntryAction({
  icon,
  title,
  description,
  action,
  onClick,
}: {
  icon: ReactNode;
  title: string;
  description: string;
  action: string;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="group surface flex min-h-[126px] items-start gap-4 p-5 text-left transition-[border-color,background-color] hover:border-line-strong hover:bg-sunken"
    >
      <span className="grid size-10 shrink-0 place-items-center rounded-control border border-line bg-canvas text-ink-muted">
        {icon}
      </span>
      <span className="min-w-0">
        <span className="mb-1 block text-[14px] font-semibold">{title}</span>
        <span className="mb-3 block text-[12.5px] leading-relaxed text-ink-muted">
          {description}
        </span>
        <span className="flex items-center gap-1.5 text-[11.5px] font-semibold text-low">
          {action}
          <ArrowRight
            className="size-3.5 transition-transform group-hover:translate-x-0.5"
            strokeWidth={2}
          />
        </span>
      </span>
    </button>
  );
}

function EmptyProjects({
  hasProjects,
  onOpen,
}: {
  hasProjects: boolean;
  onOpen: () => void;
}) {
  return (
    <div className="grid min-h-48 place-items-center px-5 py-10 text-center">
      <div>
        <FolderGit2 className="mx-auto mb-3 size-7 text-ink-subtle" strokeWidth={1.5} />
        <p className="mb-1 text-[13px] font-semibold">
          {hasProjects ? "No projects match this view" : "No repositories yet"}
        </p>
        <p className="mb-4 text-[12px] text-ink-muted">
          {hasProjects
            ? "Try a different search or project filter."
            : "Open a local Git folder to start inspecting changes."}
        </p>
        {!hasProjects && (
          <button
            type="button"
            onClick={onOpen}
            className="rounded-control bg-ink px-3.5 py-2 text-[11.5px] font-semibold text-white hover:bg-zinc-800"
          >
            Open repository
          </button>
        )}
      </div>
    </div>
  );
}

function RepositoryDialog({
  mode,
  onClose,
  onCreated,
}: {
  mode: Exclude<DialogMode, null>;
  onClose: () => void;
  onCreated: (project: Project) => void;
}) {
  const [value, setValue] = useState("");
  const [destination, setDestination] = useState("");
  const [pending, setPending] = useState(false);
  const [browsing, setBrowsing] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => inputRef.current?.focus(), []);

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (!value.trim() || (mode === "clone" && !destination.trim())) return;
    setPending(true);
    setError(null);
    try {
      const project =
        mode === "open"
          ? await api.openProject(value.trim())
          : await api.cloneProject(value.trim(), destination.trim());
      onCreated(project);
    } catch (cause) {
      setError(displayError(cause));
      setPending(false);
    }
  };

  const closeOnEscape = (event: ReactKeyboardEvent) => {
    if (event.key === "Escape" && !pending && !browsing) onClose();
  };

  const isOpen = mode === "open";
  const busy = pending || browsing;
  const canSubmit = Boolean(
    value.trim() && (isOpen || destination.trim()),
  );

  const browse = async () => {
    setBrowsing(true);
    setError(null);
    try {
      const result = await api.pickProjectFolder();
      if (result.path) {
        if (isOpen) setValue(result.path);
        else setDestination(result.path);
      }
    } catch (cause) {
      setError(displayError(cause));
    } finally {
      setBrowsing(false);
    }
  };

  return (
    <div
      role="presentation"
      className="fixed inset-0 z-50 grid place-items-center bg-black/25 p-4"
      onMouseDown={(event) => {
        if (event.target === event.currentTarget && !busy) onClose();
      }}
      onKeyDown={closeOnEscape}
    >
      <section
        role="dialog"
        aria-modal="true"
        aria-labelledby="repository-dialog-title"
        className="w-full max-w-[500px] rounded-panel border border-line bg-paper shadow-2xl"
      >
        <div className="flex items-start justify-between gap-4 border-b border-line px-5 py-4">
          <div>
            <h2 id="repository-dialog-title" className="text-[15px] font-semibold">
              {isOpen ? "Open local folder" : "Clone from remote"}
            </h2>
            <p className="mt-1 text-[12px] text-ink-muted">
              {isOpen
                ? "Browse for a Git repository or enter its absolute path."
                : "Choose a remote repository and where to save its local checkout."}
            </p>
          </div>
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            aria-label="Close dialog"
            className="rounded-control p-1.5 text-ink-subtle hover:bg-canvas hover:text-ink disabled:opacity-40"
          >
            <X className="size-4" />
          </button>
        </div>
        <form onSubmit={submit} className="p-5">
          <label className="mb-1.5 block text-[11.5px] font-semibold" htmlFor="repository-source">
            {isOpen ? "Folder path" : "Repository URL"}
          </label>
          <div className="flex gap-2">
            <input
              ref={inputRef}
              id="repository-source"
              value={value}
              onChange={(event) => setValue(event.target.value)}
              placeholder={
                isOpen
                  ? "C:\\Dev\\Repositories\\my-project"
                  : "https://github.com/company/repository.git"
              }
              disabled={busy}
              required
              className="h-10 min-w-0 flex-1 rounded-control border border-line-strong bg-paper px-3 font-mono text-[12px] outline-none placeholder:text-ink-subtle focus:border-ink disabled:bg-canvas"
            />
            {isOpen && (
              <button
                type="button"
                onClick={() => void browse()}
                disabled={busy}
                className="flex h-10 shrink-0 items-center gap-2 rounded-control border border-line-strong px-3 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink disabled:opacity-40"
              >
                {browsing ? (
                  <LoaderCircle className="size-3.5 animate-spin" />
                ) : (
                  <FolderOpen className="size-3.5" />
                )}
                {browsing ? "Selecting" : "Browse"}
              </button>
            )}
          </div>
          {!isOpen && (
            <>
              <label
                className="mb-1.5 mt-4 block text-[11.5px] font-semibold"
                htmlFor="repository-destination"
              >
                Save in
              </label>
              <div className="flex gap-2">
                <input
                  id="repository-destination"
                  value={destination}
                  onChange={(event) => setDestination(event.target.value)}
                  placeholder={"C:\\Dev\\Repositories"}
                  disabled={busy}
                  required
                  className="h-10 min-w-0 flex-1 rounded-control border border-line-strong bg-paper px-3 font-mono text-[12px] outline-none placeholder:text-ink-subtle focus:border-ink disabled:bg-canvas"
                />
                <button
                  type="button"
                  onClick={() => void browse()}
                  disabled={busy}
                  className="flex h-10 shrink-0 items-center gap-2 rounded-control border border-line-strong px-3 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink disabled:opacity-40"
                >
                  {browsing ? (
                    <LoaderCircle className="size-3.5 animate-spin" />
                  ) : (
                    <FolderOpen className="size-3.5" />
                  )}
                  {browsing ? "Selecting" : "Browse"}
                </button>
              </div>
            </>
          )}
          {error && (
            <p role="alert" className="mt-2 text-[11.5px] text-critical">
              {error}
            </p>
          )}
          <div className="mt-5 flex justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              disabled={busy}
              className="rounded-control border border-line-strong px-3.5 py-2 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={busy || !canSubmit}
              className="flex min-w-[88px] items-center justify-center gap-2 rounded-control bg-ink px-3.5 py-2 text-[11.5px] font-semibold text-white hover:bg-zinc-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {pending && <LoaderCircle className="size-3.5 animate-spin" />}
              {pending ? (isOpen ? "Opening" : "Cloning") : isOpen ? "Open" : "Clone"}
            </button>
          </div>
        </form>
      </section>
    </div>
  );
}

function RepositoryInspector({
  project,
  onError,
}: {
  project: Project;
  onError: (message: string) => void;
}) {
  const defaultHead = project.current_branch ?? project.base_branch;
  const [base, setBase] = useState(project.base_branch);
  const [head, setHead] = useState(defaultHead);
  const [tree, setTree] = useState<ProjectTree | null>(null);
  const [preview, setPreview] = useState<DiffPreview | null>(null);
  const [loading, setLoading] = useState(true);
  const [reviewing, setReviewing] = useState(false);
  const [result, setResult] = useState<DeterministicReview | null>(null);

  const fetchData = useCallback(
    () =>
      Promise.all([
        api.getProjectTree(project.id, head),
        api.getProjectDiff(project.id, base, head),
      ]),
    [base, head, project.id],
  );

  const load = useCallback(async () => {
    try {
      const [nextTree, nextPreview] = await fetchData();
      setTree(nextTree);
      setPreview(nextPreview);
    } catch (error) {
      onError(displayError(error));
    } finally {
      setLoading(false);
    }
  }, [fetchData, onError]);

  useEffect(() => {
    let active = true;
    void fetchData()
      .then(([nextTree, nextPreview]) => {
        if (!active) return;
        setTree(nextTree);
        setPreview(nextPreview);
      })
      .catch((error: unknown) => {
        if (active) onError(displayError(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });

    return () => {
      active = false;
    };
  }, [fetchData, onError]);

  const runReview = async () => {
    setReviewing(true);
    try {
      setResult(await api.runDeterministicReview(project.id, base, head));
    } catch (error) {
      onError(displayError(error));
    } finally {
      setReviewing(false);
    }
  };

  return (
    <>
      <section className="mt-5 overflow-hidden rounded-panel border border-line bg-paper">
        <div className="flex flex-col justify-between gap-4 border-b border-line px-5 py-4 lg:flex-row lg:items-center">
          <div className="min-w-0">
            <p className="mb-0.5 flex items-center gap-2 text-[13.5px] font-semibold">
              <FolderGit2 className="size-4 text-low" strokeWidth={1.8} />
              <span className="truncate">{project.name}</span>
            </p>
            <p className="numeric truncate text-[10.5px] text-ink-subtle">
              {project.path}
            </p>
          </div>
          <div className="flex flex-wrap items-end gap-2">
            <BranchSelect
              label="Base"
              value={base}
              branches={project.branches}
              onChange={(value) => {
                setResult(null);
                setLoading(true);
                setBase(value);
              }}
            />
            <GitCompareArrows className="mb-2 size-4 text-ink-subtle" />
            <BranchSelect
              label="Head"
              value={head}
              branches={project.branches}
              onChange={(value) => {
                setResult(null);
                setLoading(true);
                setHead(value);
              }}
            />
            <button
              type="button"
              onClick={() => {
                setLoading(true);
                void load();
              }}
              disabled={loading || reviewing}
              className="ml-1 flex h-9 items-center gap-2 rounded-control border border-line-strong px-3 text-[11.5px] font-semibold text-ink-muted hover:bg-canvas hover:text-ink disabled:opacity-50"
            >
              {loading ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <GitCompareArrows className="size-3.5" />
              )}
              Preview
            </button>
            <button
              type="button"
              onClick={() => void runReview()}
              disabled={loading || reviewing}
              className="flex h-9 min-w-[112px] items-center justify-center gap-2 rounded-control bg-ink px-3.5 text-[11.5px] font-semibold text-white hover:bg-zinc-800 disabled:opacity-50"
            >
              {reviewing ? (
                <LoaderCircle className="size-3.5 animate-spin" />
              ) : (
                <ScanSearch className="size-3.5" />
              )}
              {reviewing ? "Running" : "Run checks"}
            </button>
          </div>
        </div>

        <div className="grid min-h-[410px] lg:grid-cols-[270px_minmax(0,1fr)]">
          <aside className="border-b border-line lg:border-b-0 lg:border-r">
            <div className="flex h-11 items-center justify-between border-b border-line bg-sunken px-4">
              <h3 className="flex items-center gap-2 text-[11.5px] font-semibold">
                <Files className="size-3.5 text-ink-subtle" />
                Tracked files
              </h3>
              <span className="numeric text-[10.5px] text-ink-subtle">
                {tree?.files.length ?? 0}
              </span>
            </div>
            <div className="max-h-[360px] overflow-auto p-2">
              {loading && !tree ? (
                <LoadingRows />
              ) : tree?.files.length ? (
                tree.files.map((path) => (
                  <div
                    key={path}
                    className="flex min-w-0 items-center gap-2 rounded-chip px-2 py-1.5 text-[11px] text-ink-muted hover:bg-canvas"
                    title={path}
                  >
                    <File className="size-3.5 shrink-0 text-ink-subtle" strokeWidth={1.7} />
                    <span className="truncate font-mono">{path}</span>
                  </div>
                ))
              ) : (
                <p className="px-2 py-3 text-[11px] text-ink-subtle">No tracked files.</p>
              )}
            </div>
          </aside>

          <div className="min-w-0">
            <div className="flex min-h-11 flex-wrap items-center gap-x-5 gap-y-2 border-b border-line bg-sunken px-4 py-2">
              <Metric
                icon={<Code2 className="size-3" />}
                label="Files"
                value={String(preview?.files.length ?? 0)}
              />
              <Metric
                icon={<GitBranch className="size-3" />}
                label="Lines"
                value={
                  preview
                    ? `+${preview.additions} / -${preview.deletions}`
                    : "0"
                }
              />
              <Metric
                icon={<Boxes className="size-3" />}
                label="Est. tokens"
                value={formatTokens(preview?.estimated_tokens ?? 0)}
              />
              <Metric
                icon={<CircleDollarSign className="size-3" />}
                label="Est. input"
                value={`$${(preview?.estimated_cost_usd ?? 0).toFixed(4)}`}
              />
            </div>
            <DiffViewer preview={preview} loading={loading} />
          </div>
        </div>
      </section>

      {result && <DeterministicReviewPanel result={result} />}
    </>
  );
}

const SEVERITY_STYLES: Record<Severity, string> = {
  critical: "border-critical-line bg-critical-surface text-critical",
  medium: "border-medium-line bg-medium-surface text-medium",
  low: "border-low-line bg-low-surface text-low",
};

function DeterministicReviewPanel({
  result,
}: {
  result: DeterministicReview;
}) {
  const { review } = result;
  return (
    <section
      aria-label="Deterministic review results"
      className="mt-4 overflow-hidden rounded-panel border border-line bg-paper"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-line px-5 py-4">
        <div>
          <h3 className="text-[14px] font-semibold">Deterministic review</h3>
          <p className="mt-0.5 font-mono text-[10.5px] text-ink-subtle">
            {review.base_branch} → {review.head_branch}
          </p>
        </div>
        <span className="flex items-center gap-1.5 rounded-control border border-success-line bg-success-surface px-2.5 py-1 text-[10.5px] font-semibold text-success">
          <CircleCheck className="size-3.5" />
          Completed · 0 tokens
        </span>
      </div>

      <div className="grid grid-cols-2 border-b border-line bg-sunken sm:grid-cols-4">
        <ReviewMetric label="Findings" value={String(review.findings.length)} />
        <ReviewMetric label="Files checked" value={String(review.stats.files_analysed)} />
        <ReviewMetric label="Chunks" value={String(review.stats.chunks_prepared)} />
        <ReviewMetric label="Duration" value={`${review.stats.duration_ms} ms`} />
      </div>

      <div className="border-b border-line px-5 py-4">
        <div className="grid gap-2 sm:grid-cols-5">
          {result.stages.map((stage, index) => (
            <div
              key={stage.name}
              className="flex min-w-0 items-center gap-2 rounded-control border border-line px-2.5 py-2"
              title={stage.detail ?? undefined}
            >
              <span className="grid size-5 shrink-0 place-items-center rounded-full bg-success-surface font-mono text-[9px] font-semibold text-success">
                {index + 1}
              </span>
              <span className="truncate text-[10.5px] font-semibold capitalize">
                {stage.name}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid lg:grid-cols-[260px_minmax(0,1fr)]">
        <aside className="border-b border-line p-4 lg:border-b-0 lg:border-r">
          <h4 className="mb-2.5 text-[11px] font-semibold uppercase text-ink-subtle">
            Analyzers
          </h4>
          <div className="space-y-1">
            {result.analyzers.map((analyzer) => (
              <AnalyzerRow key={analyzer.name} analyzer={analyzer} />
            ))}
          </div>
        </aside>

        <div className="min-w-0">
          <div className="flex h-11 items-center justify-between border-b border-line bg-sunken px-4">
            <h4 className="flex items-center gap-2 text-[11.5px] font-semibold">
              <CircleAlert className="size-3.5 text-ink-subtle" />
              Findings
            </h4>
            <span className="font-mono text-[10.5px] text-ink-subtle">
              {review.findings.length}
            </span>
          </div>
          {review.findings.length ? (
            <div className="divide-y divide-line">
              {review.findings.map((finding) => (
                <FindingRow key={finding.id} finding={finding} />
              ))}
            </div>
          ) : (
            <div className="grid min-h-44 place-items-center px-5 py-8 text-center">
              <div>
                <CircleCheck className="mx-auto mb-2.5 size-6 text-success" />
                <p className="text-[12.5px] font-semibold">No deterministic findings</p>
                <p className="mt-1 text-[11px] text-ink-muted">
                  Available analyzers reported no issues on changed lines.
                </p>
              </div>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function ReviewMetric({ label, value }: { label: string; value: string }) {
  return (
    <div className="border-r border-line px-4 py-3 last:border-r-0">
      <p className="font-mono text-[14px] font-semibold">{value}</p>
      <p className="mt-0.5 text-[9.5px] font-semibold uppercase text-ink-subtle">
        {label}
      </p>
    </div>
  );
}

function AnalyzerRow({ analyzer }: { analyzer: AnalyzerRun }) {
  const Icon =
    analyzer.status === "completed"
      ? CircleCheck
      : analyzer.status === "failed"
        ? CircleX
        : CircleAlert;
  const tone =
    analyzer.status === "completed"
      ? "text-success"
      : analyzer.status === "failed"
        ? "text-critical"
        : "text-ink-subtle";
  return (
    <div
      className="flex items-center gap-2 rounded-control px-2 py-2 hover:bg-canvas"
      title={analyzer.detail ?? undefined}
    >
      <Icon className={`size-3.5 shrink-0 ${tone}`} />
      <span className="min-w-0 flex-1 truncate text-[11px] font-medium capitalize">
        {analyzer.name}
      </span>
      <span className="font-mono text-[10px] text-ink-subtle">
        {analyzer.status === "completed" ? analyzer.findings : "—"}
      </span>
    </div>
  );
}

function FindingRow({ finding }: { finding: Finding }) {
  return (
    <article className="px-4 py-4">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <span
          className={`rounded-chip border px-2 py-0.5 text-[9.5px] font-semibold capitalize ${SEVERITY_STYLES[finding.severity]}`}
        >
          {finding.severity}
        </span>
        <span className="font-mono text-[10px] text-ink-subtle">
          {finding.file}:{finding.line_start}
        </span>
        <span className="ml-auto text-[9.5px] font-semibold uppercase text-ink-subtle">
          {finding.source}
        </span>
      </div>
      <h5 className="text-[12.5px] font-semibold leading-snug">{finding.title}</h5>
    </article>
  );
}

function BranchSelect({
  label,
  value,
  branches,
  onChange,
}: {
  label: string;
  value: string;
  branches: string[];
  onChange: (value: string) => void;
}) {
  return (
    <label>
      <span className="mb-1 block text-[9.5px] font-semibold uppercase text-ink-subtle">
        {label}
      </span>
      <select
        value={value}
        onChange={(event) => onChange(event.target.value)}
        className="h-9 min-w-[150px] rounded-control border border-line-strong bg-paper px-2.5 font-mono text-[11px] outline-none focus:border-ink"
      >
        {branches.map((branch) => (
          <option key={branch}>{branch}</option>
        ))}
      </select>
    </label>
  );
}

function Metric({
  icon,
  label,
  value,
}: {
  icon: ReactElement;
  label: string;
  value: string;
}) {
  return (
    <span className="flex items-center gap-1.5 text-[10.5px] text-ink-subtle">
      {icon}
      <span>{label}</span>
      <strong className="numeric font-medium text-ink-muted">{value}</strong>
    </span>
  );
}

function DiffViewer({
  preview,
  loading,
}: {
  preview: DiffPreview | null;
  loading: boolean;
}) {
  if (loading && !preview) {
    return <div className="p-4"><LoadingRows /></div>;
  }

  if (!preview?.patch) {
    return (
      <div className="grid min-h-[360px] place-items-center p-8 text-center">
        <div>
          <Check className="mx-auto mb-3 size-7 text-success" strokeWidth={1.7} />
          <p className="mb-1 text-[12.5px] font-semibold">No changes in this comparison</p>
          <p className="text-[11px] text-ink-muted">
            When base and head match, RevAI previews uncommitted working-tree changes.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="max-h-[360px] overflow-auto bg-[#fcfcfc]">
      <pre className="min-w-max py-2 text-[11px] leading-[1.65]">
        {preview.patch.split("\n").map((line, index) => {
          const tone = line.startsWith("+")
            ? "bg-success-surface text-[#047857]"
            : line.startsWith("-")
              ? "bg-critical-surface text-[#b91c1c]"
              : line.startsWith("@@")
                ? "bg-low-surface text-low"
                : line.startsWith("diff ") || line.startsWith("index ")
                  ? "font-semibold text-ink"
                  : "text-ink-muted";
          return (
            <code
              key={`${index}-${line}`}
              className={`block min-h-[18px] px-4 ${tone}`}
            >
              {line || " "}
            </code>
          );
        })}
      </pre>
      {preview.truncated && (
        <p className="sticky bottom-0 border-t border-medium-line bg-medium-surface px-4 py-2 text-[10.5px] text-medium">
          Preview capped at 1 MB. The full diff remains unchanged in Git.
        </p>
      )}
    </div>
  );
}

function LoadingRows() {
  return (
    <div className="space-y-2" aria-label="Loading repository data">
      {[70, 92, 58, 80].map((width) => (
        <div
          key={width}
          className="h-5 animate-pulse rounded-chip bg-canvas"
          style={{ width: `${width}%` }}
        />
      ))}
    </div>
  );
}
