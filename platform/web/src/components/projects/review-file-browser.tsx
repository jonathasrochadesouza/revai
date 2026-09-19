"use client";

import {
  ChevronDown,
  ChevronRight,
  ChevronUp,
  File,
  Files,
  FolderOpen,
  Search,
  X,
} from "lucide-react";
import { useDeferredValue, useId, useMemo, useState } from "react";

import { useUiText } from "@/components/ui-preference-bootstrap";

export type FileUniverse = "changed" | "all";
export type FileLayout = "flat" | "tree";

type FileNode = {
  kind: "file";
  name: string;
  path: string;
};

type DirectoryNode = {
  kind: "directory";
  name: string;
  path: string;
  children: TreeNode[];
};

type TreeNode = FileNode | DirectoryNode;

type MutableDirectory = DirectoryNode & {
  directories: Map<string, MutableDirectory>;
};

function uniquePaths(paths: string[]): string[] {
  const seen = new Set<string>();
  return paths.filter((path) => {
    if (!path || seen.has(path)) return false;
    seen.add(path);
    return true;
  });
}

function basename(path: string): string {
  return path.slice(path.lastIndexOf("/") + 1);
}

function filterPaths(paths: string[], query: string): string[] {
  const normalized = query.trim().toLocaleLowerCase();
  if (!normalized) return paths;
  return paths.filter((path) => {
    const normalizedPath = path.toLocaleLowerCase();
    return (
      normalizedPath.includes(normalized) ||
      basename(normalizedPath).includes(normalized)
    );
  });
}

function buildFileTree(paths: string[]): TreeNode[] {
  const root: MutableDirectory = {
    kind: "directory",
    name: "",
    path: "",
    children: [],
    directories: new Map(),
  };

  for (const path of paths) {
    const parts = path.split("/").filter(Boolean);
    if (!parts.length) continue;
    let parent = root;

    for (let index = 0; index < parts.length - 1; index += 1) {
      const name = parts[index];
      const directoryPath = parts.slice(0, index + 1).join("/");
      let directory = parent.directories.get(name);
      if (!directory) {
        directory = {
          kind: "directory",
          name,
          path: directoryPath,
          children: [],
          directories: new Map(),
        };
        parent.directories.set(name, directory);
        parent.children.push(directory);
      }
      parent = directory;
    }

    parent.children.push({
      kind: "file",
      name: parts.at(-1) ?? path,
      path,
    });
  }

  const finalize = (nodes: TreeNode[]): TreeNode[] =>
    nodes.map((node) =>
      node.kind === "file"
        ? node
        : {
            kind: "directory",
            name: node.name,
            path: node.path,
            children: finalize(node.children),
          },
    );

  return finalize(root.children);
}

function directoryPaths(nodes: TreeNode[]): string[] {
  const paths: string[] = [];
  const visit = (items: TreeNode[]) => {
    for (const item of items) {
      if (item.kind === "file") continue;
      paths.push(item.path);
      visit(item.children);
    }
  };
  visit(nodes);
  return paths;
}

function FileRow({
  path,
  label,
  depth,
  selectableMode,
  selected,
  tracked,
  onSelectionChange,
  translate,
}: {
  path: string;
  label: string;
  depth: number;
  selectableMode: boolean;
  selected: boolean;
  tracked: boolean;
  onSelectionChange: (path: string, checked: boolean) => void;
  translate: (value: string) => string;
}) {
  const reasonId = useId();
  const unavailable = selectableMode && !tracked;

  return (
    <label
      className={`file-browser-row flex min-w-0 items-center gap-2 rounded-chip py-1.5 pr-2 text-[11px] hover:bg-canvas ${
        unavailable ? "text-ink-subtle" : "text-ink-muted"
      }`}
      style={{ paddingLeft: `${8 + depth * 14}px` }}
      title={path}
    >
      {selectableMode ? (
        <input
          type="checkbox"
          checked={selected}
          disabled={unavailable}
          aria-describedby={unavailable ? reasonId : undefined}
          onChange={(event) => onSelectionChange(path, event.target.checked)}
          className="size-3.5 shrink-0 accent-ink disabled:cursor-not-allowed"
        />
      ) : null}
      <File className="size-3.5 shrink-0 text-ink-subtle" strokeWidth={1.7} aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate font-mono">{label}</span>
      {unavailable ? (
        <>
          <span className="shrink-0 text-[8.5px] font-semibold uppercase tracking-wide text-medium">
            {translate("Not at Head")}
          </span>
          <span id={reasonId} className="sr-only">
            {translate("This path is not tracked at Head. Use Branch diff to review it.")}
          </span>
        </>
      ) : null}
    </label>
  );
}

function TreeRows({
  nodes,
  depth,
  collapsed,
  forceExpanded,
  selectedPaths,
  trackedPaths,
  selectableMode,
  onToggle,
  onSelectionChange,
  translate,
}: {
  nodes: TreeNode[];
  depth: number;
  collapsed: Set<string>;
  forceExpanded: boolean;
  selectedPaths: Set<string>;
  trackedPaths: Set<string>;
  selectableMode: boolean;
  onToggle: (path: string) => void;
  onSelectionChange: (path: string, checked: boolean) => void;
  translate: (value: string) => string;
}) {
  return nodes.map((node) => {
    if (node.kind === "file") {
      return (
        <FileRow
          key={node.path}
          path={node.path}
          label={node.name}
          depth={depth}
          selectableMode={selectableMode}
          selected={selectedPaths.has(node.path)}
          tracked={trackedPaths.has(node.path)}
          onSelectionChange={onSelectionChange}
          translate={translate}
        />
      );
    }

    const isCollapsed = !forceExpanded && collapsed.has(node.path);
    return (
      <div key={node.path}>
        <button
          type="button"
          aria-expanded={!isCollapsed}
          disabled={forceExpanded}
          onClick={() => onToggle(node.path)}
          className="flex w-full min-w-0 items-center gap-1.5 rounded-chip py-1.5 pr-2 text-left text-[11px] font-medium text-ink-muted hover:bg-canvas disabled:cursor-default"
          style={{ paddingLeft: `${8 + depth * 14}px` }}
        >
          {isCollapsed ? (
            <ChevronRight className="size-3.5 shrink-0 text-ink-subtle" aria-hidden="true" />
          ) : (
            <ChevronDown className="size-3.5 shrink-0 text-ink-subtle" aria-hidden="true" />
          )}
          <FolderOpen className="size-3.5 shrink-0 text-ink-subtle" aria-hidden="true" />
          <span className="truncate font-mono">{node.name}</span>
        </button>
        {!isCollapsed ? (
          <TreeRows
            nodes={node.children}
            depth={depth + 1}
            collapsed={collapsed}
            forceExpanded={forceExpanded}
            selectedPaths={selectedPaths}
            trackedPaths={trackedPaths}
            selectableMode={selectableMode}
            onToggle={onToggle}
            onSelectionChange={onSelectionChange}
            translate={translate}
          />
        ) : null}
      </div>
    );
  });
}

function LoadingFileRows() {
  return (
    <div className="space-y-2 p-2" aria-hidden="true">
      {Array.from({ length: 7 }, (_, index) => (
        <div key={index} className="h-6 animate-pulse rounded-chip bg-canvas" />
      ))}
    </div>
  );
}

export function ReviewFileBrowser({
  trackedFiles,
  changedFiles,
  selectedFiles,
  selectableMode,
  universe,
  layout,
  query,
  loadingTracked,
  loadingChanged,
  onUniverseChange,
  onLayoutChange,
  onQueryChange,
  onSelectionChange,
}: {
  trackedFiles: string[];
  changedFiles: string[];
  selectedFiles: string[];
  selectableMode: boolean;
  universe: FileUniverse;
  layout: FileLayout;
  query: string;
  loadingTracked: boolean;
  loadingChanged: boolean;
  onUniverseChange: (universe: FileUniverse) => void;
  onLayoutChange: (layout: FileLayout) => void;
  onQueryChange: (query: string) => void;
  onSelectionChange: (path: string, checked: boolean) => void;
}) {
  const { t } = useUiText();
  const deferredQuery = useDeferredValue(query);
  const isStale = query !== deferredQuery;
  const [collapsed, setCollapsed] = useState<Set<string>>(() => new Set());

  const normalizedTracked = useMemo(() => uniquePaths(trackedFiles), [trackedFiles]);
  const normalizedChanged = useMemo(() => uniquePaths(changedFiles), [changedFiles]);
  const trackedSet = useMemo(() => new Set(normalizedTracked), [normalizedTracked]);
  const selectedSet = useMemo(() => new Set(selectedFiles), [selectedFiles]);
  const sourceFiles = universe === "changed" ? normalizedChanged : normalizedTracked;
  const visibleFiles = useMemo(
    () => filterPaths(sourceFiles, deferredQuery),
    [deferredQuery, sourceFiles],
  );
  const tree = useMemo(() => buildFileTree(visibleFiles), [visibleFiles]);
  const folders = useMemo(() => directoryPaths(tree), [tree]);
  const normalizedQuery = deferredQuery.trim();
  const loading = universe === "changed" ? loadingChanged : loadingTracked;

  const toggleFolder = (path: string) => {
    setCollapsed((current) => {
      const next = new Set(current);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  return (
    <aside className="border-b border-line lg:border-b-0 lg:border-r">
      <div className="flex min-h-11 items-center justify-between border-b border-line bg-sunken px-4 py-2">
        <h3 className="flex items-center gap-2 text-[11.5px] font-semibold">
          <Files className="size-3.5 text-ink-subtle" aria-hidden="true" />
          {t("Tracked files")}
        </h3>
        <span className="numeric text-[10.5px] text-ink-subtle" aria-live="polite">
          {visibleFiles.length}/{sourceFiles.length}
          {selectableMode ? ` · ${selectedFiles.length} ${t("selected")}` : ""}
        </span>
      </div>

      <div className="space-y-2 border-b border-line p-3">
        <div className="grid grid-cols-2 rounded-control border border-line bg-sunken p-0.5">
          {([
            ["changed", "Changed", normalizedChanged.length],
            ["all", "All", normalizedTracked.length],
          ] as const).map(([value, label, count]) => (
            <button
              key={value}
              type="button"
              aria-pressed={universe === value}
              onClick={() => onUniverseChange(value)}
              className={`rounded-chip px-2 py-1.5 text-[10.5px] font-semibold transition-colors ${
                universe === value
                  ? "bg-paper text-ink shadow-sm"
                  : "text-ink-subtle hover:text-ink"
              }`}
            >
              {t(label)} <span className="numeric font-normal">{count}</span>
            </button>
          ))}
        </div>

        <div className="relative">
          <Search
            className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-ink-subtle"
            aria-hidden="true"
          />
          <input
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            placeholder={t("Search files")}
            aria-label={t("Search files")}
            className="h-8 w-full rounded-control border border-line-strong bg-paper pl-8 pr-8 font-mono text-[10.5px] text-ink outline-none placeholder:text-ink-subtle focus:border-ink"
          />
          {query ? (
            <button
              type="button"
              onClick={() => onQueryChange("")}
              aria-label={t("Clear file search")}
              className="absolute right-1.5 top-1/2 -translate-y-1/2 rounded-chip p-1 text-ink-subtle hover:bg-canvas hover:text-ink"
            >
              <X className="size-3" aria-hidden="true" />
            </button>
          ) : null}
        </div>

        <div className="flex items-center justify-between gap-2">
          <div className="flex rounded-control border border-line bg-sunken p-0.5">
            <button
              type="button"
              aria-pressed={layout === "flat"}
              aria-label={t("Show flat list")}
              onClick={() => onLayoutChange("flat")}
              className={`rounded-chip p-1.5 ${layout === "flat" ? "bg-paper text-ink shadow-sm" : "text-ink-subtle hover:text-ink"}`}
            >
              <File className="size-3.5" aria-hidden="true" />
            </button>
            <button
              type="button"
              aria-pressed={layout === "tree"}
              aria-label={t("Show folder tree")}
              onClick={() => onLayoutChange("tree")}
              className={`rounded-chip p-1.5 ${layout === "tree" ? "bg-paper text-ink shadow-sm" : "text-ink-subtle hover:text-ink"}`}
            >
              <FolderOpen className="size-3.5" aria-hidden="true" />
            </button>
          </div>
          {layout === "tree" ? (
            <div className="flex items-center gap-0.5">
              <button
                type="button"
                disabled={!folders.length || Boolean(normalizedQuery)}
                onClick={() => setCollapsed(new Set())}
                aria-label={t("Expand all folders")}
                className="rounded-chip p-1.5 text-ink-subtle hover:bg-canvas hover:text-ink disabled:opacity-35"
              >
                <ChevronDown className="size-3.5" aria-hidden="true" />
              </button>
              <button
                type="button"
                disabled={!folders.length || Boolean(normalizedQuery)}
                onClick={() => setCollapsed(new Set(folders))}
                aria-label={t("Collapse all folders")}
                className="rounded-chip p-1.5 text-ink-subtle hover:bg-canvas hover:text-ink disabled:opacity-35"
              >
                <ChevronUp className="size-3.5" aria-hidden="true" />
              </button>
            </div>
          ) : (
            <span className="text-[9.5px] text-ink-subtle">{t("Flat list")}</span>
          )}
        </div>
      </div>

      <div
        className={`max-h-[360px] overflow-auto p-2 transition-opacity ${isStale ? "opacity-60" : "opacity-100"}`}
        aria-busy={loading || isStale}
      >
        {loading && !sourceFiles.length ? (
          <LoadingFileRows />
        ) : visibleFiles.length ? (
          layout === "flat" ? (
            visibleFiles.map((path) => (
              <FileRow
                key={path}
                path={path}
                label={path}
                depth={0}
                selectableMode={selectableMode}
                selected={selectedSet.has(path)}
                tracked={trackedSet.has(path)}
                onSelectionChange={onSelectionChange}
                translate={t}
              />
            ))
          ) : (
            <TreeRows
              nodes={tree}
              depth={0}
              collapsed={collapsed}
              forceExpanded={Boolean(normalizedQuery)}
              selectedPaths={selectedSet}
              trackedPaths={trackedSet}
              selectableMode={selectableMode}
              onToggle={toggleFolder}
              onSelectionChange={onSelectionChange}
              translate={t}
            />
          )
        ) : (
          <p role="status" className="px-2 py-6 text-center text-[11px] text-ink-subtle">
            {normalizedQuery
              ? t("No files match your search.")
              : universe === "changed"
                ? t("No changed files.")
                : t("No tracked files.")}
          </p>
        )}
      </div>
    </aside>
  );
}
