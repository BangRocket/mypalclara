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
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";

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
              <span className="text-xs text-muted-foreground mr-3">
                {statsQuery.data.total} memories, {statsQuery.data.key_count} key
              </span>
            )}

            {/* Export / Import */}
            <Button variant="ghost" size="icon" asChild title="Export memories">
              <a href={memoriesApi.exportAll()} download>
                <Download size={16} />
              </a>
            </Button>
            <Button
              variant="ghost"
              size="icon"
              onClick={() => importRef.current?.click()}
              title="Import memories"
            >
              <Upload size={16} />
            </Button>
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
            <Button
              variant={view === "grid" ? "secondary" : "ghost"}
              size="icon"
              onClick={() => setView("grid")}
            >
              <Grid3x3 size={16} />
            </Button>
            <Button
              variant={view === "list" ? "secondary" : "ghost"}
              size="icon"
              onClick={() => setView("list")}
            >
              <List size={16} />
            </Button>
          </div>
        </div>

        <div className="flex items-center gap-3">
          <div className="flex-1">
            <SearchBar onSearch={handleSearch} />
          </div>
          {searchQuery && (
            <Button variant="ghost" size="sm" onClick={handleClearSearch}>
              Clear search
            </Button>
          )}
        </div>

        {/* Filters */}
        <div className="flex items-center gap-2 flex-wrap">
          <Badge
            variant={!category && isKeyFilter === undefined ? "default" : "outline"}
            className="cursor-pointer"
            onClick={() => { setCategory(""); setIsKeyFilter(undefined); }}
          >
            All
          </Badge>
          {Object.entries(categories).map(([cat, count]) => (
            <Badge
              key={cat}
              variant={cat === category ? "default" : "outline"}
              className="cursor-pointer"
              onClick={() => setCategory(cat === category ? "" : cat)}
            >
              {cat} ({count})
            </Badge>
          ))}
          <Badge
            variant={isKeyFilter === true ? "default" : "outline"}
            className={cn(
              "cursor-pointer",
              isKeyFilter === true && "bg-key/80 hover:bg-key/70 border-key text-white"
            )}
            onClick={() => setIsKeyFilter(isKeyFilter === true ? undefined : true)}
          >
            Key Only
          </Badge>

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
                <Input
                  autoFocus
                  value={newSetName}
                  onChange={(e) => setNewSetName(e.target.value)}
                  placeholder="Set name..."
                  className="h-7 text-xs w-28"
                />
                <Button type="submit" size="sm" variant="secondary" className="h-7 px-2">
                  Save
                </Button>
                <Button
                  type="button"
                  size="icon"
                  variant="ghost"
                  onClick={() => setShowSaveSet(false)}
                  className="h-7 w-7"
                >
                  <X size={14} />
                </Button>
              </form>
            ) : (
              <Button
                variant="ghost"
                size="icon"
                onClick={() => setShowSaveSet(true)}
                title="Save current filters"
                className="h-8 w-8"
              >
                <BookmarkPlus size={16} />
              </Button>
            )}
          </div>
        </div>

        {/* Saved Sets */}
        {savedSets.length > 0 && (
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-xs text-muted-foreground flex items-center gap-1"><Bookmark size={12} /> Sets:</span>
            {savedSets.map((s) => (
              <Badge key={s.id} variant="secondary" className="gap-1 pr-1">
                <button
                  onClick={() => {
                    setCategory(s.filters.category || "");
                    setIsKeyFilter(s.filters.is_key);
                    setSearchQuery(s.filters.searchQuery || "");
                  }}
                  className="hover:text-primary transition"
                >
                  {s.name}
                </button>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={() => removeSet(s.id)}
                  className="h-4 w-4 p-0 hover:bg-transparent hover:text-destructive"
                >
                  <X size={10} />
                </Button>
              </Badge>
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
