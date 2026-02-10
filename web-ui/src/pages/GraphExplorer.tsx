import { useState, useMemo, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search, Network, ChevronRight } from "lucide-react";
import { graph, type GraphNode, type GraphEdge } from "@/api/client";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { GraphLegend } from "@/components/graph/GraphLegend";
import { EntityDetail } from "@/components/graph/EntityDetail";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TYPE_COLORS } from "@/components/graph/EntityNode";

// ── Filter logic ─────────────────────────────────────────────────────────

function applyFilters(
  nodes: GraphNode[],
  edges: GraphEdge[],
  hiddenTypes: Set<string>,
): { nodes: GraphNode[]; edges: GraphEdge[] } {
  if (hiddenTypes.size === 0) return { nodes, edges };

  const filteredNodes = nodes.filter((n) => !hiddenTypes.has(n.type || "default"));
  const nodeIds = new Set(filteredNodes.map((n) => n.id));
  const filteredEdges = edges.filter((e) => nodeIds.has(e.source) && nodeIds.has(e.target));

  return { nodes: filteredNodes, edges: filteredEdges };
}

function computeTypeCounts(nodes: GraphNode[]): Record<string, number> {
  const counts: Record<string, number> = {};
  for (const n of nodes) {
    const t = n.type || "default";
    counts[t] = (counts[t] || 0) + 1;
  }
  return counts;
}

// ── Page ─────────────────────────────────────────────────────────────────

export function GraphExplorerPage() {
  const [center, setCenter] = useState<string | undefined>(undefined);
  const [searchInput, setSearchInput] = useState("");
  const [hiddenTypes, setHiddenTypes] = useState<Set<string>>(new Set());
  const [selectedEntity, setSelectedEntity] = useState<string | null>(null);
  const [depth, setDepth] = useState("2");
  const [limit, setLimit] = useState("150");
  const [breadcrumbs, setBreadcrumbs] = useState<string[]>([]);

  const subgraphQuery = useQuery({
    queryKey: ["subgraph", center, depth, limit],
    queryFn: () => graph.subgraph({ center, depth: Number(depth), limit: Number(limit) }),
  });

  const searchQuery = useQuery({
    queryKey: ["graph-search", searchInput],
    queryFn: () => graph.search(searchInput, 10),
    enabled: searchInput.length > 1,
  });

  // Raw counts (before filtering)
  const rawTypeCounts = useMemo(
    () => computeTypeCounts(subgraphQuery.data?.nodes || []),
    [subgraphQuery.data],
  );

  // Filtered data
  const filtered = useMemo(
    () => applyFilters(subgraphQuery.data?.nodes || [], subgraphQuery.data?.edges || [], hiddenTypes),
    [subgraphQuery.data, hiddenTypes],
  );

  // Counts for legend (after filtering)
  const filteredTypeCounts = useMemo(() => computeTypeCounts(filtered.nodes), [filtered.nodes]);

  const navigateTo = useCallback(
    (name: string) => {
      setCenter(name);
      setBreadcrumbs((prev) => {
        if (prev[prev.length - 1] === name) return prev;
        return [...prev.slice(-4), name];
      });
    },
    [],
  );

  const handleNodeClick = useCallback(
    (name: string) => {
      setSelectedEntity(name);
    },
    [],
  );

  const handleNodeDoubleClick = useCallback(
    (name: string) => {
      navigateTo(name);
    },
    [navigateTo],
  );

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.data?.results?.[0]) {
      navigateTo(searchQuery.data.results[0].name);
    }
  };

  const toggleType = (type: string) => {
    setHiddenTypes((prev) => {
      const next = new Set(prev);
      if (next.has(type)) next.delete(type);
      else next.add(type);
      return next;
    });
  };

  const allTypes = Object.keys(rawTypeCounts).sort();

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="border-b border-border p-3 flex items-center gap-3 flex-wrap">
        <h1 className="text-lg font-bold flex items-center gap-2">
          <Network className="h-5 w-5" />
          Graph Explorer
        </h1>

        <form onSubmit={handleSearch} className="relative flex-1 max-w-sm min-w-[200px]">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground z-10" />
          <Input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search entities..."
            className="pl-9"
          />
          {searchInput && searchQuery.data?.results && (
            <div className="absolute top-full mt-1 left-0 right-0 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
              {searchQuery.data.results.map((r) => (
                <button
                  key={r.name}
                  onClick={() => {
                    navigateTo(r.name);
                    setSearchInput("");
                  }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition flex items-center gap-2"
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: TYPE_COLORS[r.type] || TYPE_COLORS.default }}
                  />
                  <span>{r.name}</span>
                  {r.type && <span className="text-xs text-muted-foreground">({r.type})</span>}
                </button>
              ))}
            </div>
          )}
        </form>

        {/* Depth / limit controls */}
        <div className="flex items-center gap-2 text-sm">
          <span className="text-muted-foreground">Depth</span>
          <Select value={depth} onValueChange={setDepth}>
            <SelectTrigger size="sm" className="w-16">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="1">1</SelectItem>
              <SelectItem value="2">2</SelectItem>
              <SelectItem value="3">3</SelectItem>
              <SelectItem value="4">4</SelectItem>
            </SelectContent>
          </Select>
          <span className="text-muted-foreground">Limit</span>
          <Select value={limit} onValueChange={setLimit}>
            <SelectTrigger size="sm" className="w-20">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="50">50</SelectItem>
              <SelectItem value="100">100</SelectItem>
              <SelectItem value="150">150</SelectItem>
              <SelectItem value="300">300</SelectItem>
              <SelectItem value="500">500</SelectItem>
            </SelectContent>
          </Select>
        </div>

        {center && (
          <Button variant="ghost" size="sm" onClick={() => { setCenter(undefined); setBreadcrumbs([]); }}>
            Show all
          </Button>
        )}
      </div>

      {/* Stats bar + breadcrumbs */}
      <div className="border-b border-border px-3 py-1.5 flex items-center gap-3 text-xs text-muted-foreground">
        <span>{filtered.nodes.length} nodes</span>
        <span className="text-border">|</span>
        <span>{filtered.edges.length} edges</span>
        {breadcrumbs.length > 0 && (
          <>
            <span className="text-border">|</span>
            <div className="flex items-center gap-1 overflow-x-auto">
              {breadcrumbs.map((name, i) => (
                <span key={i} className="flex items-center gap-1 shrink-0">
                  {i > 0 && <ChevronRight className="h-3 w-3" />}
                  <button
                    onClick={() => navigateTo(name)}
                    className={`hover:text-foreground transition-colors ${
                      i === breadcrumbs.length - 1 ? "text-foreground font-medium" : ""
                    }`}
                  >
                    {name}
                  </button>
                </span>
              ))}
            </div>
          </>
        )}
      </div>

      {/* Filter bar */}
      {allTypes.length > 0 && (
        <div className="border-b border-border px-3 py-2 flex items-center gap-2 flex-wrap">
          <span className="text-xs text-muted-foreground mr-1">Filter:</span>
          {allTypes.map((type) => {
            const hidden = hiddenTypes.has(type);
            return (
              <button key={type} onClick={() => toggleType(type)}>
                <Badge
                  variant={hidden ? "outline" : "secondary"}
                  className={`cursor-pointer text-xs gap-1.5 ${hidden ? "opacity-50" : ""}`}
                >
                  <span
                    className="w-2 h-2 rounded-full shrink-0"
                    style={{ backgroundColor: TYPE_COLORS[type] || TYPE_COLORS.default }}
                  />
                  <span className="capitalize">{type}</span>
                  <span className="text-muted-foreground">{rawTypeCounts[type]}</span>
                </Badge>
              </button>
            );
          })}
        </div>
      )}

      {/* Graph */}
      <div className="flex-1 relative">
        {subgraphQuery.isLoading ? (
          <div className="flex items-center justify-center h-full text-muted-foreground">Loading graph...</div>
        ) : filtered.nodes.length > 0 ? (
          <>
            <GraphCanvas
              graphNodes={filtered.nodes}
              graphEdges={filtered.edges}
              onNodeClick={handleNodeClick}
              onNodeDoubleClick={handleNodeDoubleClick}
              selectedNode={selectedEntity}
            />
            <GraphLegend typeCounts={filteredTypeCounts} />
          </>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-muted-foreground gap-2">
            <Network className="h-10 w-10 opacity-30" />
            <p>No graph data available.</p>
            <p className="text-xs">Enable graph memory to populate entities.</p>
          </div>
        )}
      </div>

      {/* Entity detail panel */}
      <EntityDetail
        entityName={selectedEntity}
        onClose={() => setSelectedEntity(null)}
        onNavigate={(name) => {
          navigateTo(name);
          setSelectedEntity(name);
        }}
      />
    </div>
  );
}
