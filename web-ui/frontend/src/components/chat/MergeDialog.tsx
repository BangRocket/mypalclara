/**
 * Modal dialog for merging a branch back into main.
 *
 * Offers two strategies:
 * - Squash: keep memories, messages stay in the branch
 * - Full: keep memories and append all messages to the main conversation
 */

import { useState } from "react";
import { GitMerge } from "lucide-react";
import type { BranchInfo } from "@/stores/chatStore";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface MergeDialogProps {
  branch: BranchInfo | null;
  onClose: () => void;
  onMerge: (branchId: string, strategy: "squash" | "full") => void;
  isPending: boolean;
}

export function MergeDialog({
  branch,
  onClose,
  onMerge,
  isPending,
}: MergeDialogProps) {
  const [strategy, setStrategy] = useState<"squash" | "full">("squash");

  const isOpen = branch !== null;

  const handleMerge = () => {
    if (!branch) return;
    onMerge(branch.id, strategy);
  };

  return (
    <Dialog
      open={isOpen}
      onOpenChange={(open) => {
        if (!open) onClose();
      }}
    >
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <GitMerge className="h-5 w-5 text-primary" />
            Merge Branch
          </DialogTitle>
          <DialogDescription>
            Merge{" "}
            <span className="font-medium text-foreground">
              {branch?.name || "unnamed branch"}
            </span>{" "}
            back into the main conversation.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3 py-2">
          {/* Squash merge option */}
          <label
            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
              strategy === "squash"
                ? "border-primary bg-primary/5"
                : "border-border hover:border-border/80"
            }`}
          >
            <input
              type="radio"
              name="merge-strategy"
              value="squash"
              checked={strategy === "squash"}
              onChange={() => setStrategy("squash")}
              className="mt-0.5"
            />
            <div>
              <div className="text-sm font-medium">Squash merge</div>
              <div className="text-xs text-muted-foreground">
                Keep memories learned during this branch. Messages stay in the
                branch.
              </div>
            </div>
          </label>

          {/* Full merge option */}
          <label
            className={`flex cursor-pointer items-start gap-3 rounded-lg border p-3 transition-colors ${
              strategy === "full"
                ? "border-primary bg-primary/5"
                : "border-border hover:border-border/80"
            }`}
          >
            <input
              type="radio"
              name="merge-strategy"
              value="full"
              checked={strategy === "full"}
              onChange={() => setStrategy("full")}
              className="mt-0.5"
            />
            <div>
              <div className="text-sm font-medium">Full merge</div>
              <div className="text-xs text-muted-foreground">
                Keep memories and append all messages to the main conversation.
              </div>
            </div>
          </label>
        </div>

        <DialogFooter>
          <Button variant="ghost" onClick={onClose} disabled={isPending}>
            Cancel
          </Button>
          <Button onClick={handleMerge} disabled={isPending}>
            {isPending ? "Merging..." : "Merge"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
