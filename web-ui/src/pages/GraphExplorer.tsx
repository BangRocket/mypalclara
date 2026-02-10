import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Search } from "lucide-react";
import { graph } from "@/api/client";
import { GraphCanvas } from "@/components/graph/GraphCanvas";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";

export function GraphExplorerPage() {
  const [center, setCenter] = useState<string | undefined>(undefined);
  const [searchInput, setSearchInput] = useState("");

  const subgraphQuery = useQuery({
    queryKey: ["subgraph", center],
    queryFn: () => graph.subgraph({ center, depth: 2, limit: 150 }),
  });

  const searchQuery = useQuery({
    queryKey: ["graph-search", searchInput],
    queryFn: () => graph.search(searchInput, 10),
    enabled: searchInput.length > 1,
  });

  const handleNodeClick = (name: string) => {
    setCenter(name);
  };

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.data?.results?.[0]) {
      setCenter(searchQuery.data.results[0].name);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Toolbar */}
      <div className="border-b border-border p-4 flex items-center gap-4">
        <h1 className="text-xl font-bold">Graph Explorer</h1>

        <form onSubmit={handleSearch} className="relative flex-1 max-w-sm">
          <Search size={16} className="absolute left-3 top-1/2 -translate-y-1/2 text-muted-foreground z-10" />
          <Input
            type="text"
            value={searchInput}
            onChange={(e) => setSearchInput(e.target.value)}
            placeholder="Search entities..."
            className="pl-9"
          />
          {searchInput && searchQuery.data?.results && (
            <div className="absolute top-full mt-1 left-0 right-0 bg-card border border-border rounded-lg shadow-lg z-10 max-h-48 overflow-y-auto">
              {searchQuery.data.results.map((r) => (
                <button
                  key={r.name}
                  onClick={() => {
                    setCenter(r.name);
                    setSearchInput("");
                  }}
                  className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition flex items-center gap-2"
                >
                  <span>{r.name}</span>
                  {r.type && <span className="text-xs text-muted-foreground">({r.type})</span>}
                </button>
              ))}
            </div>
          )}
        </form>

        {center && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => setCenter(undefined)}
          >
            Show all
          </Button>
        )}
      </div>

      {/* Graph */}
      <div className="flex-1">
        {subgraphQuery.isLoading ? (
          <div className="flex items-center justify-center h-full text-text-muted">Loading graph...</div>
        ) : subgraphQuery.data ? (
          <GraphCanvas
            graphNodes={subgraphQuery.data.nodes}
            graphEdges={subgraphQuery.data.edges}
            onNodeClick={handleNodeClick}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-text-muted">
            No graph data available. Enable graph memory to populate entities.
          </div>
        )}
      </div>
    </div>
  );
}
