import { useRef, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Grid3x3, List, Bookmark, BookmarkPlus, X, Download, Upload } from "lucide-react";
import { memories as memoriesApi, type Memory } from "@/api/client";
import { cn } from "@/lib/utils";
import { SearchBar } from "@/components/knowledge/SearchBar";
import { MemoryGrid } from "@/components/knowledge/MemoryGrid";
import { MemoryList } from "@/components/knowledge/MemoryList";
import { MemoryEditor } from "@/components/knowledge/MemoryEditor";
import { useSavedSets } from "@/stores/savedSets";

type ViewMode = "grid" | "list";

export function KnowledgeBasePage() {
  const [view, setView] = useState<ViewMode>("grid");
  const [category, setCategory] = useState<string>("");
  const [isKeyFilter, setIsKeyFilter] = useState<boolean | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedMemory, setSelectedMemory] = useState<Memory | null>(null);
  const [showSaveSet, setShowSaveSet] = useState(false);
  const [newSetName, setNewSetName] = useState("");
  const { sets: savedSets, addSet, removeSet } = useSavedSets();
  const queryClient = useQueryClient();
  const importRef = useRef<HTMLInputElement>(null);

  const importMutation = useMutation({
    mutationFn: memoriesApi.importMemories,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["memories"] });
      queryClient.invalidateQueries({ queryKey: ["memory-stats"] });
    },
  });

  // List query
  const listQuery = useQuery({
    queryKey: ["memories", category, isKeyFilter],
    queryFn: () =>
      memoriesApi.list({
        category: category || undefined,
        is_key: isKeyFilter,
        limit: 200,
      }),
    enabled: !searchQuery,
  });

  // Search query
  const searchQueryResult = useQuery({
    queryKey: ["memories-search", searchQuery],
    queryFn: () => memoriesApi.search({ query: searchQuery, limit: 50 }),
    enabled: !!searchQuery,
  });

  // Stats
  const statsQuery = useQuery({ queryKey: ["memory-stats"], queryFn: memoriesApi.stats });

  const displayMemories: Memory[] = searchQuery
    ? (searchQueryResult.data?.results || []).map((r) => ({
        id: r.id,
        content: r.content,
        metadata: r.metadata,
        created_at: null,
        updated_at: null,
        user_id: null,
        dynamics: r.dynamics
          ? { ...r.dynamics, difficulty: null, retrieval_strength: null, storage_strength: null, access_count: 0, last_accessed_at: null }
          : null,
      }))
    : listQuery.data?.memories || [];

  const handleSearch = (query: string) => {
    setSearchQuery(query);
  };

  const handleClearSearch = () => {
    setSearchQuery("");
  };

  const categories = statsQuery.data?.by_category || {};

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="border-b border-border p-4 space-y-3">
        <div className="flex items-center justify-between">
          <h1 className="text-xl font-bold">Knowledge Base</h1>
          <div className="flex items-center gap-2">
            {/* Stats summary */}
            {statsQuery.data && (
              <span className="text-xs text-text-muted mr-3">
                {statsQuery.data.total} memories, {statsQuery.data.key_count} key
              </span>
            )}

            {/* Export / Import */}
            <a
              href={memoriesApi.exportAll()}
              download
              className="p-2 rounded-lg text-text-muted hover:text-text-primary transition"
              title="Export memories"
            >
              <Download size={16} />
            </a>
            <button
              onClick={() => importRef.current?.click()}
              className="p-2 rounded-lg text-text-muted hover:text-text-primary transition"
              title="Import memories"
            >
              <Upload size={16} />
            </button>
            <input
              ref={importRef}
              type="file"
              accept=".json"
              className="hidden"
              onChange={async (e) => {
                const file = e.target.files?.[0];
                if (!file) return;
                const text = await file.text();
                try {
                  const data = JSON.parse(text);
                  if (data.memories) importMutation.mutate({ memories: data.memories });
                } catch { /* ignore bad JSON */ }
                if (importRef.current) importRef.current.value = "";
              }}
            />

            {/* View toggle */}
            <button
              onClick={() => setView("grid")}
              className={cn("p-2 rounded-lg transition", view === "grid" ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text-primary")}
            >
              <Grid3x3 size={16} />
            </button>
            <button
              onClick={() => setView("list")}
              className={cn("p-2 rounded-lg transition", view === "list" ? "bg-accent/15 text-accent" : "text-text-muted hover:text-text-primary")}
            >
              <List size={16} />
            </button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex-1">
            <SearchBar onSearch={handleSearch} />
          </div>
          {searchQuery && (
            <button onClick={handleClearSearch} className="text-xs text-accent hover:underline">
              Clear search
            </button>
          )}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <button
            onClick={() => { setCategory(""); setIsKeyFilter(undefined); }}
            className={cn(
              "px-3 py-1 rounded-full text-xs transition",
              !category && isKeyFilter === undefined ? "bg-accent/15 text-accent" : "bg-surface-overlay text-text-muted hover:text-text-primary",
            )}
          >
            All
          </button>
          {Object.entries(categories).map(([cat, count]) => (
            <button
              key={cat}
              onClick={() => setCategory(cat === category ? "" : cat)}
              className={cn(
                "px-3 py-1 rounded-full text-xs transition",
                cat === category ? "bg-accent/15 text-accent" : "bg-surface-overlay text-text-muted hover:text-text-primary",
              )}
            >
              {cat} ({count})
            </button>
          ))}
          <button
            onClick={() => setIsKeyFilter(isKeyFilter === true ? undefined : true)}
            className={cn(
              "px-3 py-1 rounded-full text-xs transition",
              isKeyFilter === true ? "bg-key/15 text-key" : "bg-surface-overlay text-text-muted hover:text-text-primary",
            )}
          >
            Key Only
          </button>

          {/* Save current filters */}
          <div className="ml-auto flex items-center gap-1">
            {showSaveSet ? (
              <form
                onSubmit={(e) => {
                  e.preventDefault();
                  if (!newSetName.trim()) return;
                  addSet(newSetName.trim(), { category, is_key: isKeyFilter, searchQuery });
                  setNewSetName("");
                  setShowSaveSet(false);
                }}
                className="flex items-center gap-1"
              >
                <input
                  autoFocus
                  value={newSetName}
                  onChange={(e) => setNewSetName(e.target.value)}
                  placeholder="Set name..."
                  className="px-2 py-1 rounded text-xs bg-surface-overlay border border-border text-text-primary focus:outline-none focus:border-accent w-28"
                />
                <button type="submit" className="px-2 py-1 rounded text-xs bg-accent/15 text-accent hover:bg-accent/25">Save</button>
                <button type="button" onClick={() => setShowSaveSet(false)} className="text-text-muted hover:text-text-primary"><X size={14} /></button>
              </form>
            ) : (
              <button onClick={() => setShowSaveSet(true)} className="p-1 text-text-muted hover:text-accent transition" title="Save current filters">
                <BookmarkPlus size={16} />
              </button>
            )}
          </div>
        </div>

        {/* Saved Sets */}
        {savedSets.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-text-muted flex items-center gap-1"><Bookmark size={12} /> Sets:</span>
            {savedSets.map((s) => (
              <div key={s.id} className="flex items-center gap-1 bg-surface-overlay rounded-full px-2 py-0.5">
                <button
                  onClick={() => {
                    setCategory(s.filters.category || "");
                    setIsKeyFilter(s.filters.is_key);
                    setSearchQuery(s.filters.searchQuery || "");
                  }}
                  className="text-xs text-text-secondary hover:text-accent transition"
                >
                  {s.name}
                </button>
                <button onClick={() => removeSet(s.id)} className="text-text-muted hover:text-danger"><X size={10} /></button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto">
        {view === "grid" ? (
          <MemoryGrid memories={displayMemories} onSelect={setSelectedMemory} />
        ) : (
          <MemoryList memories={displayMemories} onSelect={setSelectedMemory} />
        )}
      </div>

      {/* Editor slide-over */}
      {selectedMemory && (
        <MemoryEditor
          memory={selectedMemory}
          onClose={() => setSelectedMemory(null)}
          onSaved={() => {
            setSelectedMemory(null);
            listQuery.refetch();
          }}
          onDeleted={() => {
            setSelectedMemory(null);
            listQuery.refetch();
            statsQuery.refetch();
          }}
        />
      )}
    </div>
  );
}
