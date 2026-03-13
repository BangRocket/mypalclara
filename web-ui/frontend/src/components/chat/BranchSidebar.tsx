/**
 * Collapsible sidebar showing the branch tree for the active conversation.
 *
 * - Main trunk at top, child branches indented below
 * - Active branch highlighted
 * - Click to switch branch
 * - Context menu for rename, archive, merge, delete
 * - "New branch" button at bottom
 */

import { useState, useCallback } from "react";
import {
  GitBranch,
  GitMerge,
  PanelLeft,
  PanelLeftClose,
  Plus,
  Pencil,
  Archive,
  Trash2,
  MoreHorizontal,
  Check,
  X,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useBranches } from "@/hooks/useBranches";
import { useChatStore, type BranchInfo } from "@/stores/chatStore";
import { MergeDialog } from "@/components/chat/MergeDialog";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

export function BranchSidebar() {
  const [open, setOpen] = useState(false);
  const {
    branches,
    isLoading,
    fork,
    merge,
    renameBranch,
    archiveBranch,
    deleteBranch,
    switchToBranch,
  } = useBranches();
  const activeBranchId = useChatStore((s) => s.activeBranchId);

  // Merge dialog state
  const [mergeTarget, setMergeTarget] = useState<BranchInfo | null>(null);

  // Rename inline editing state
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const [renameValue, setRenameValue] = useState("");

  const mainBranch = branches.find((b) => b.parent_branch_id === null);
  const childBranches = branches.filter((b) => b.parent_branch_id !== null);

  const handleForkFromActive = useCallback(() => {
    if (!activeBranchId) return;
    fork.mutate({ parentBranchId: activeBranchId });
  }, [activeBranchId, fork]);

  const startRename = useCallback((branch: BranchInfo) => {
    setRenamingId(branch.id);
    setRenameValue(branch.name || "");
  }, []);

  const submitRename = useCallback(() => {
    if (renamingId && renameValue.trim()) {
      renameBranch.mutate({ branchId: renamingId, name: renameValue.trim() });
    }
    setRenamingId(null);
    setRenameValue("");
  }, [renamingId, renameValue, renameBranch]);

  const cancelRename = useCallback(() => {
    setRenamingId(null);
    setRenameValue("");
  }, []);

  // Toggle button (always visible)
  const toggleButton = (
    <button
      onClick={() => setOpen((v) => !v)}
      className="flex h-8 w-8 items-center justify-center rounded-md text-muted-foreground hover:bg-accent hover:text-accent-foreground transition-colors"
      aria-label={open ? "Close branch sidebar" : "Open branch sidebar"}
    >
      {open ? (
        <PanelLeftClose className="h-4 w-4" />
      ) : (
        <PanelLeft className="h-4 w-4" />
      )}
    </button>
  );

  if (!open) {
    return (
      <div className="flex flex-col items-center border-r border-border bg-background px-1 py-2">
        {toggleButton}
        {branches.length > 1 && (
          <div className="mt-2 flex h-5 w-5 items-center justify-center rounded-full bg-primary/10 text-[10px] font-medium text-primary">
            {branches.length}
          </div>
        )}
      </div>
    );
  }

  return (
    <>
      <div className="flex w-56 flex-col border-r border-border bg-background">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-3 py-2">
          <div className="flex items-center gap-1.5 text-sm font-medium text-foreground">
            <GitBranch className="h-3.5 w-3.5" />
            Branches
          </div>
          {toggleButton}
        </div>

        {/* Branch list */}
        <div className="flex-1 overflow-y-auto px-1.5 py-1.5">
          {isLoading ? (
            <div className="px-2 py-4 text-center text-xs text-muted-foreground">
              Loading...
            </div>
          ) : (
            <>
              {/* Main branch */}
              {mainBranch && (
                <BranchItem
                  branch={mainBranch}
                  isActive={activeBranchId === mainBranch.id}
                  isMain
                  indent={0}
                  renamingId={renamingId}
                  renameValue={renameValue}
                  onSwitch={() => switchToBranch(mainBranch.id)}
                  onStartRename={startRename}
                  onRenameChange={setRenameValue}
                  onSubmitRename={submitRename}
                  onCancelRename={cancelRename}
                  onArchive={() =>
                    archiveBranch.mutate({ branchId: mainBranch.id })
                  }
                  onDelete={() =>
                    deleteBranch.mutate({ branchId: mainBranch.id })
                  }
                  onMerge={() => setMergeTarget(mainBranch)}
                />
              )}

              {/* Child branches */}
              {childBranches.map((branch) => (
                <BranchItem
                  key={branch.id}
                  branch={branch}
                  isActive={activeBranchId === branch.id}
                  isMain={false}
                  indent={1}
                  renamingId={renamingId}
                  renameValue={renameValue}
                  onSwitch={() => switchToBranch(branch.id)}
                  onStartRename={startRename}
                  onRenameChange={setRenameValue}
                  onSubmitRename={submitRename}
                  onCancelRename={cancelRename}
                  onArchive={() =>
                    archiveBranch.mutate({ branchId: branch.id })
                  }
                  onDelete={() =>
                    deleteBranch.mutate({ branchId: branch.id })
                  }
                  onMerge={() => setMergeTarget(branch)}
                />
              ))}

              {branches.length === 0 && !isLoading && (
                <div className="px-2 py-4 text-center text-xs text-muted-foreground">
                  No branches yet
                </div>
              )}
            </>
          )}
        </div>

        {/* New branch button */}
        <div className="border-t border-border px-2 py-2">
          <Button
            variant="ghost"
            size="sm"
            className="w-full justify-start gap-2 text-xs"
            onClick={handleForkFromActive}
            disabled={!activeBranchId || fork.isPending}
          >
            <Plus className="h-3.5 w-3.5" />
            {fork.isPending ? "Creating..." : "New branch"}
          </Button>
        </div>
      </div>

      {/* Merge dialog */}
      <MergeDialog
        branch={mergeTarget}
        onClose={() => setMergeTarget(null)}
        onMerge={(branchId, strategy) => {
          merge.mutate(
            { branchId, strategy },
            { onSuccess: () => setMergeTarget(null) },
          );
        }}
        isPending={merge.isPending}
      />
    </>
  );
}

// ── Individual branch item ────────────────────────────────────────────

interface BranchItemProps {
  branch: BranchInfo;
  isActive: boolean;
  isMain: boolean;
  indent: number;
  renamingId: string | null;
  renameValue: string;
  onSwitch: () => void;
  onStartRename: (branch: BranchInfo) => void;
  onRenameChange: (value: string) => void;
  onSubmitRename: () => void;
  onCancelRename: () => void;
  onArchive: () => void;
  onDelete: () => void;
  onMerge: () => void;
}

function BranchItem({
  branch,
  isActive,
  isMain,
  indent,
  renamingId,
  renameValue,
  onSwitch,
  onStartRename,
  onRenameChange,
  onSubmitRename,
  onCancelRename,
  onArchive,
  onDelete,
  onMerge,
}: BranchItemProps) {
  const isRenaming = renamingId === branch.id;
  const isMerged = branch.status === "merged";
  const isArchived = branch.status === "archived";

  const displayName = branch.name || (isMain ? "main" : "unnamed branch");

  return (
    <div
      className={cn(
        "group relative flex items-center gap-1.5 rounded-md px-2 py-1.5 text-sm transition-colors",
        isActive
          ? "bg-accent text-accent-foreground"
          : "text-muted-foreground hover:bg-accent/50 hover:text-foreground",
        isArchived && "opacity-60",
      )}
      style={{ paddingLeft: `${0.5 + indent * 0.75}rem` }}
    >
      {/* Status icon */}
      {isMerged ? (
        <GitMerge className="h-3.5 w-3.5 shrink-0 text-green-500" />
      ) : (
        <GitBranch className="h-3.5 w-3.5 shrink-0" />
      )}

      {/* Name / rename input */}
      {isRenaming ? (
        <div className="flex flex-1 items-center gap-1">
          <input
            type="text"
            value={renameValue}
            onChange={(e) => onRenameChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") onSubmitRename();
              if (e.key === "Escape") onCancelRename();
            }}
            className="h-5 flex-1 rounded border border-input bg-background px-1 text-xs outline-none focus:ring-1 focus:ring-ring"
            autoFocus
          />
          <button
            onClick={onSubmitRename}
            className="text-green-500 hover:text-green-600"
          >
            <Check className="h-3 w-3" />
          </button>
          <button
            onClick={onCancelRename}
            className="text-muted-foreground hover:text-foreground"
          >
            <X className="h-3 w-3" />
          </button>
        </div>
      ) : (
        <>
          <button
            onClick={onSwitch}
            className="flex-1 truncate text-left text-xs"
            title={displayName}
          >
            {displayName}
          </button>

          {/* Context menu */}
          <DropdownMenu>
            <DropdownMenuTrigger asChild>
              <button className="shrink-0 rounded p-0.5 opacity-0 transition-opacity group-hover:opacity-100 hover:bg-accent">
                <MoreHorizontal className="h-3.5 w-3.5" />
              </button>
            </DropdownMenuTrigger>
            <DropdownMenuContent align="end" className="w-36">
              <DropdownMenuItem onClick={() => onStartRename(branch)}>
                <Pencil className="mr-2 h-3.5 w-3.5" />
                Rename
              </DropdownMenuItem>
              {!isMain && !isMerged && (
                <DropdownMenuItem onClick={onMerge}>
                  <GitMerge className="mr-2 h-3.5 w-3.5" />
                  Merge
                </DropdownMenuItem>
              )}
              {!isMain && (
                <>
                  <DropdownMenuSeparator />
                  <DropdownMenuItem onClick={onArchive}>
                    <Archive className="mr-2 h-3.5 w-3.5" />
                    Archive
                  </DropdownMenuItem>
                  <DropdownMenuItem
                    onClick={onDelete}
                    variant="destructive"
                  >
                    <Trash2 className="mr-2 h-3.5 w-3.5" />
                    Delete
                  </DropdownMenuItem>
                </>
              )}
            </DropdownMenuContent>
          </DropdownMenu>
        </>
      )}
    </div>
  );
}
