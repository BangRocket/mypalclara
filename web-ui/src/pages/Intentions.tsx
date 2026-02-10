import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Check, X, Zap, Clock } from "lucide-react";
import { intentions as intentionsApi, type Intention } from "@/api/client";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

type FilterMode = "all" | "active" | "fired";

export function IntentionsPage() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState<FilterMode>("all");
  const [showCreate, setShowCreate] = useState(false);

  const firedParam = filter === "all" ? undefined : filter === "fired";

  const { data, isLoading } = useQuery({
    queryKey: ["intentions", filter],
    queryFn: () => intentionsApi.list({ fired: firedParam, limit: 100 }),
  });

  const deleteMutation = useMutation({
    mutationFn: intentionsApi.delete,
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["intentions"] }),
  });

  const intentions = data?.intentions || [];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="border-b border-border p-4">
        <div className="flex items-center justify-between mb-3">
          <div>
            <h1 className="text-xl font-bold">Intentions</h1>
            <p className="text-xs text-text-muted mt-0.5">
              Instructions Clara follows when conditions are met
            </p>
          </div>
          <Button onClick={() => setShowCreate(true)} className="gap-1.5">
            <Plus size={16} /> New Intention
          </Button>
        </div>

        {/* Filter tabs */}
        <Tabs value={filter} onValueChange={(v) => setFilter(v as FilterMode)} className="w-auto">
          <TabsList>
            {(["all", "active", "fired"] as FilterMode[]).map((f) => (
              <TabsTrigger key={f} value={f} className="capitalize">
                {f} {data && f === "all" ? `(${data.total})` : ""}
              </TabsTrigger>
            ))}
          </TabsList>
        </Tabs>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3">
        {isLoading && <p className="text-text-muted text-sm">Loading...</p>}

        {!isLoading && intentions.length === 0 && (
          <div className="text-center py-12 text-text-muted">
            <Zap size={32} className="mx-auto mb-2 opacity-40" />
            <p className="text-sm">No intentions yet</p>
            <p className="text-xs mt-1">Create one to give Clara standing instructions</p>
          </div>
        )}

        {intentions.map((intention) => (
          <IntentionCard
            key={intention.id}
            intention={intention}
            onDelete={() => deleteMutation.mutate(intention.id)}
          />
        ))}
      </div>

      {/* Create modal */}
      {showCreate && (
        <CreateIntentionModal
          onClose={() => setShowCreate(false)}
          onCreated={() => {
            setShowCreate(false);
            queryClient.invalidateQueries({ queryKey: ["intentions"] });
          }}
        />
      )}
    </div>
  );
}

function IntentionCard({
  intention,
  onDelete,
}: {
  intention: Intention;
  onDelete: () => void;
}) {
  const triggers = intention.trigger_conditions;
  const triggerEntries = Object.entries(triggers).filter(([, v]) => v !== null && v !== undefined);

  return (
    <Card className={cn("p-4", intention.fired && "opacity-60")}>
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm">{intention.content}</p>

          {/* Trigger conditions */}
          {triggerEntries.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {triggerEntries.map(([key, val]) => (
                <Badge key={key} variant="secondary" className="text-xs">
                  {key}: {String(val)}
                </Badge>
              ))}
            </div>
          )}

          {/* Meta row */}
          <div className="flex items-center gap-3 mt-2 text-xs text-muted-foreground">
            {intention.fired ? (
              <span className="flex items-center gap-1 text-green-400">
                <Check size={12} /> Fired
                {intention.fired_at && ` ${new Date(intention.fired_at).toLocaleDateString()}`}
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <Clock size={12} /> Active
              </span>
            )}
            {intention.fire_once && (
              <span>once only</span>
            )}
            <span>priority: {intention.priority}</span>
            {intention.expires_at && (
              <span>expires {new Date(intention.expires_at).toLocaleDateString()}</span>
            )}
          </div>
        </div>

        <Button
          variant="ghost"
          size="icon"
          onClick={onDelete}
          title="Delete intention"
          className="hover:text-destructive"
        >
          <Trash2 size={14} />
        </Button>
      </div>
    </Card>
  );
}

function CreateIntentionModal({
  onClose,
  onCreated,
}: {
  onClose: () => void;
  onCreated: () => void;
}) {
  const [content, setContent] = useState("");
  const [triggerType, setTriggerType] = useState<"keyword" | "channel" | "dm">("keyword");
  const [triggerValue, setTriggerValue] = useState("");
  const [priority, setPriority] = useState(0);
  const [fireOnce, setFireOnce] = useState(true);

  const createMutation = useMutation({
    mutationFn: intentionsApi.create,
    onSuccess: onCreated,
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!content.trim()) return;

    const trigger_conditions: Record<string, unknown> = {};
    if (triggerType === "keyword" && triggerValue.trim()) {
      trigger_conditions.keyword = triggerValue.trim();
    } else if (triggerType === "channel" && triggerValue.trim()) {
      trigger_conditions.channel_name = triggerValue.trim();
    } else if (triggerType === "dm") {
      trigger_conditions.is_dm = true;
    }

    createMutation.mutate({
      content: content.trim(),
      trigger_conditions,
      priority,
      fire_once: fireOnce,
    });
  };

  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Intention</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">

          {/* Content */}
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Instruction for Clara</label>
            <Textarea
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="When this triggers, Clara should..."
              rows={3}
            />
          </div>

          {/* Trigger */}
          <div>
            <label className="text-xs text-muted-foreground block mb-1">Trigger condition</label>
            <div className="flex gap-2 mb-2">
              {(["keyword", "channel", "dm"] as const).map((t) => (
                <Badge
                  key={t}
                  variant={t === triggerType ? "default" : "outline"}
                  className="cursor-pointer capitalize"
                  onClick={() => setTriggerType(t)}
                >
                  {t}
                </Badge>
              ))}
            </div>
            {triggerType !== "dm" && (
              <Input
                value={triggerValue}
                onChange={(e) => setTriggerValue(e.target.value)}
                placeholder={triggerType === "keyword" ? "Keyword to match..." : "Channel name..."}
              />
            )}
          </div>

          {/* Options */}
          <div className="flex items-center gap-4">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={fireOnce}
                onChange={(e) => setFireOnce(e.target.checked)}
                className="accent-primary"
              />
              Fire once only
            </label>
            <div className="flex items-center gap-2 text-sm">
              <label>Priority:</label>
              <Input
                type="number"
                value={priority}
                onChange={(e) => setPriority(Number(e.target.value))}
                className="w-16"
              />
            </div>
          </div>

          <div className="flex justify-end gap-2 pt-2">
            <Button
              type="button"
              variant="ghost"
              onClick={onClose}
            >
              Cancel
            </Button>
            <Button
              type="submit"
              disabled={!content.trim() || createMutation.isPending}
            >
              {createMutation.isPending ? "Creating..." : "Create"}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
