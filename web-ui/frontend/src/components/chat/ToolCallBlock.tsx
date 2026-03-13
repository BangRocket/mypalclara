/**
 * Standalone collapsible tool call display (Claude.ai style).
 *
 * This renders tool events from our ChatMessage.toolEvents[] array.
 * It is separate from assistant-ui's ToolFallback which renders tool-call
 * content parts inside MessagePrimitive.Parts. This component can be used
 * outside the assistant-ui message rendering pipeline (e.g., in custom
 * message layouts or summaries).
 */

import { useState, type FC } from "react";
import {
  CheckCircle2Icon,
  ChevronDownIcon,
  LoaderIcon,
  XCircleIcon,
} from "lucide-react";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import { cn } from "@/lib/utils";

export interface ToolCallBlockProps {
  toolName: string;
  step?: number;
  success?: boolean;
  output?: string;
  running?: boolean;
}

export const ToolCallBlock: FC<ToolCallBlockProps> = ({
  toolName,
  step,
  success,
  output,
  running = false,
}) => {
  const [open, setOpen] = useState(false);

  const isComplete = success !== undefined;
  const hasOutput = !!output;

  const Icon = running
    ? LoaderIcon
    : success === false
      ? XCircleIcon
      : CheckCircle2Icon;

  const iconColor = running
    ? "text-muted-foreground"
    : success === false
      ? "text-destructive"
      : "text-green-600 dark:text-green-500";

  const label = running
    ? "Running"
    : success === false
      ? "Failed"
      : "Used tool";

  return (
    <Collapsible
      open={open}
      onOpenChange={setOpen}
      className="my-1 w-full rounded-lg border bg-muted/30"
    >
      <CollapsibleTrigger
        className="flex w-full items-center gap-2 px-3 py-2 text-sm transition-colors hover:bg-muted/50"
        disabled={!hasOutput && isComplete}
      >
        <Icon
          className={cn(
            "size-4 shrink-0",
            iconColor,
            running && "animate-spin",
          )}
        />
        <span className="grow text-left">
          {label}: <span className="font-medium">{toolName}</span>
          {step !== undefined && (
            <span className="ml-1 text-muted-foreground">(step {step})</span>
          )}
        </span>
        {hasOutput && (
          <ChevronDownIcon
            className={cn(
              "size-4 shrink-0 text-muted-foreground transition-transform duration-200",
              open && "rotate-180",
            )}
          />
        )}
      </CollapsibleTrigger>
      {hasOutput && (
        <CollapsibleContent className="border-t">
          <pre className="max-h-48 overflow-auto whitespace-pre-wrap p-3 text-xs text-muted-foreground">
            {output}
          </pre>
        </CollapsibleContent>
      )}
    </Collapsible>
  );
};
