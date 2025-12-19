"use client";

import { useState, useEffect, useCallback } from "react";
import { Trash2, Pencil, Search, X, RefreshCw, Brain } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

const BACKEND_URL = process.env.NEXT_PUBLIC_BACKEND_URL || "";

interface Memory {
  id: string;
  memory: string;
  hash?: string;
  metadata?: {
    project_id?: string;
    namespace?: string;
    category?: string;
    sensitive?: boolean;
    confidence?: number;
    source?: string;
    bootstrap?: boolean;
    [key: string]: unknown;
  };
  created_at?: string;
  updated_at?: string;
}

// Format namespace/category for display
function formatLabel(value: string): string {
  return value.replace(/[_:]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

// Get color classes for namespace badges
function getNamespaceColor(namespace: string): string {
  if (namespace.startsWith("profile")) return "bg-blue-500/20 text-blue-400";
  if (namespace.startsWith("interaction"))
    return "bg-purple-500/20 text-purple-400";
  if (namespace.startsWith("project_seed"))
    return "bg-green-500/20 text-green-400";
  if (namespace.startsWith("project_context"))
    return "bg-amber-500/20 text-amber-400";
  if (namespace.startsWith("restricted")) return "bg-red-500/20 text-red-400";
  return "bg-gray-500/20 text-gray-400";
}

export function MemoryManager({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const [memories, setMemories] = useState<Memory[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [editingMemory, setEditingMemory] = useState<Memory | null>(null);
  const [editText, setEditText] = useState("");
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const fetchMemories = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/memories`);
      if (!res.ok) {
        throw new Error(`Failed to fetch memories: ${res.status}`);
      }
      const data = await res.json();
      setMemories(data.memories || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to fetch memories");
    } finally {
      setLoading(false);
    }
  }, []);

  const searchMemories = async () => {
    if (!searchQuery.trim()) {
      fetchMemories();
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${BACKEND_URL}/api/memories/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: searchQuery }),
      });
      if (!res.ok) {
        throw new Error(`Search failed: ${res.status}`);
      }
      const data = await res.json();
      setMemories(data.memories || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Search failed");
    } finally {
      setLoading(false);
    }
  };

  const updateMemory = async () => {
    if (!editingMemory) return;
    setLoading(true);
    try {
      const res = await fetch(
        `${BACKEND_URL}/api/memories/${editingMemory.id}`,
        {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: editText }),
        },
      );
      if (!res.ok) {
        throw new Error(`Update failed: ${res.status}`);
      }
      setEditingMemory(null);
      fetchMemories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setLoading(false);
    }
  };

  const deleteMemory = async (id: string) => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/memories/${id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(`Delete failed: ${res.status}`);
      }
      setDeleteConfirm(null);
      fetchMemories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setLoading(false);
    }
  };

  const deleteAllMemories = async () => {
    setLoading(true);
    try {
      const res = await fetch(`${BACKEND_URL}/api/memories`, {
        method: "DELETE",
      });
      if (!res.ok) {
        throw new Error(`Delete all failed: ${res.status}`);
      }
      setDeleteConfirm(null);
      fetchMemories();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete all failed");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    if (open) {
      fetchMemories();
    }
  }, [open, fetchMemories]);

  const startEdit = (memory: Memory) => {
    setEditingMemory(memory);
    setEditText(memory.memory);
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="flex max-h-[80vh] max-w-2xl flex-col">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Brain className="size-5" />
            Memory Manager
          </DialogTitle>
          <DialogDescription>
            View, edit, and delete memories stored by Clara
          </DialogDescription>
        </DialogHeader>

        {/* Search bar */}
        <div className="flex gap-2">
          <div className="relative flex-1">
            <Search className="absolute top-1/2 left-3 size-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder="Search memories..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && searchMemories()}
              className="pl-9"
            />
          </div>
          <Button variant="outline" size="icon" onClick={searchMemories}>
            <Search className="size-4" />
          </Button>
          <Button variant="outline" size="icon" onClick={fetchMemories}>
            <RefreshCw className="size-4" />
          </Button>
        </div>

        {/* Error display */}
        {error && (
          <div className="rounded-md bg-destructive/10 p-3 text-sm text-destructive">
            {error}
          </div>
        )}

        {/* Memory list */}
        <div className="min-h-[300px] flex-1 space-y-2 overflow-y-auto">
          {loading ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              Loading...
            </div>
          ) : memories.length === 0 ? (
            <div className="flex h-full items-center justify-center text-muted-foreground">
              No memories found
            </div>
          ) : (
            memories.map((memory) => (
              <div
                key={memory.id}
                className="group rounded-lg border bg-card p-3 transition-colors hover:bg-accent/50"
              >
                <div className="flex items-start justify-between gap-2">
                  <p className="flex-1 text-sm">{memory.memory}</p>
                  <div className="flex gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7"
                      onClick={() => startEdit(memory)}
                    >
                      <Pencil className="size-3" />
                    </Button>
                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 text-destructive hover:text-destructive"
                      onClick={() => setDeleteConfirm(memory.id)}
                    >
                      <Trash2 className="size-3" />
                    </Button>
                  </div>
                </div>
                {/* Labels for namespace, category, and sensitive flag */}
                <div className="mt-2 flex flex-wrap gap-1.5">
                  {memory.metadata?.namespace && (
                    <span
                      className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${getNamespaceColor(memory.metadata.namespace)}`}
                    >
                      {formatLabel(memory.metadata.namespace)}
                    </span>
                  )}
                  {memory.metadata?.category && (
                    <span className="inline-flex items-center rounded-full bg-muted px-2 py-0.5 text-xs font-medium text-muted-foreground">
                      {formatLabel(memory.metadata.category)}
                    </span>
                  )}
                  {memory.metadata?.sensitive && (
                    <span className="inline-flex items-center rounded-full bg-red-500/20 px-2 py-0.5 text-xs font-medium text-red-400">
                      Sensitive
                    </span>
                  )}
                </div>
              </div>
            ))
          )}
        </div>

        {/* Footer with count and delete all */}
        <DialogFooter className="flex-row justify-between sm:justify-between">
          <span className="text-sm text-muted-foreground">
            {memories.length} memor{memories.length === 1 ? "y" : "ies"}
          </span>
          {memories.length > 0 && (
            <Button
              variant="destructive"
              size="sm"
              onClick={() => setDeleteConfirm("all")}
            >
              Delete All
            </Button>
          )}
        </DialogFooter>

        {/* Edit dialog */}
        <Dialog
          open={!!editingMemory}
          onOpenChange={() => setEditingMemory(null)}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Edit Memory</DialogTitle>
            </DialogHeader>
            <textarea
              className="min-h-[100px] w-full resize-none rounded-md border bg-background p-3 text-sm focus:ring-2 focus:ring-ring focus:outline-none"
              value={editText}
              onChange={(e) => setEditText(e.target.value)}
            />
            <DialogFooter>
              <Button variant="outline" onClick={() => setEditingMemory(null)}>
                Cancel
              </Button>
              <Button onClick={updateMemory}>Save</Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>

        {/* Delete confirmation dialog */}
        <Dialog
          open={!!deleteConfirm}
          onOpenChange={() => setDeleteConfirm(null)}
        >
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Confirm Delete</DialogTitle>
              <DialogDescription>
                {deleteConfirm === "all"
                  ? "Are you sure you want to delete ALL memories? This cannot be undone."
                  : "Are you sure you want to delete this memory? This cannot be undone."}
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteConfirm(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={() =>
                  deleteConfirm === "all"
                    ? deleteAllMemories()
                    : deleteMemory(deleteConfirm!)
                }
              >
                Delete
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </DialogContent>
    </Dialog>
  );
}
