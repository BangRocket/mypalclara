import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Plus, Trash2, Check, X, Zap, Clock } from "lucide-react";
import { intentions as intentionsApi, type Intention } from "@/api/client";
import { cn } from "@/lib/utils";

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
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-1.5 px-3 py-2 bg-accent hover:bg-accent-hover text-white rounded-lg text-sm transition"
          >
            <Plus size={16} /> New Intention
          </button>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-2">
          {(["all", "active", "fired"] as FilterMode[]).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={cn(
                "px-3 py-1 rounded-full text-xs transition capitalize",
                f === filter
                  ? "bg-accent/15 text-accent"
                  : "bg-surface-overlay text-text-muted hover:text-text-primary",
              )}
            >
              {f} {data && f === "all" ? `(${data.total})` : ""}
            </button>
          ))}
        </div>
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
    <div
      className={cn(
        "bg-surface-raised border border-border rounded-xl p-4",
        intention.fired && "opacity-60",
      )}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex-1 min-w-0">
          <p className="text-sm text-text-primary">{intention.content}</p>

          {/* Trigger conditions */}
          {triggerEntries.length > 0 && (
            <div className="flex flex-wrap gap-1.5 mt-2">
              {triggerEntries.map(([key, val]) => (
                <span
                  key={key}
                  className="px-2 py-0.5 bg-surface-overlay rounded text-xs text-text-muted"
                >
                  {key}: {String(val)}
                </span>
              ))}
            </div>
          )}

          {/* Meta row */}
          <div className="flex items-center gap-3 mt-2 text-xs text-text-muted">
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
              <span className="text-text-muted">once only</span>
            )}
            <span>priority: {intention.priority}</span>
            {intention.expires_at && (
              <span>expires {new Date(intention.expires_at).toLocaleDateString()}</span>
            )}
          </div>
        </div>

        <button
          onClick={onDelete}
          className="p-1.5 text-text-muted hover:text-danger transition rounded"
          title="Delete intention"
        >
          <Trash2 size={14} />
        </button>
      </div>
    </div>
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
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <form
        onSubmit={handleSubmit}
        className="bg-surface-raised border border-border rounded-xl p-6 w-full max-w-md space-y-4"
      >
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-bold">New Intention</h2>
          <button type="button" onClick={onClose} className="text-text-muted hover:text-text-primary">
            <X size={18} />
          </button>
        </div>

        {/* Content */}
        <div>
          <label className="text-xs text-text-muted block mb-1">Instruction for Clara</label>
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder="When this triggers, Clara should..."
            rows={3}
            className="w-full resize-none bg-surface-overlay border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
          />
        </div>

        {/* Trigger */}
        <div>
          <label className="text-xs text-text-muted block mb-1">Trigger condition</label>
          <div className="flex gap-2 mb-2">
            {(["keyword", "channel", "dm"] as const).map((t) => (
              <button
                key={t}
                type="button"
                onClick={() => setTriggerType(t)}
                className={cn(
                  "px-2 py-1 rounded text-xs transition capitalize",
                  t === triggerType
                    ? "bg-accent/15 text-accent"
                    : "bg-surface-overlay text-text-muted hover:text-text-primary",
                )}
              >
                {t}
              </button>
            ))}
          </div>
          {triggerType !== "dm" && (
            <input
              value={triggerValue}
              onChange={(e) => setTriggerValue(e.target.value)}
              placeholder={triggerType === "keyword" ? "Keyword to match..." : "Channel name..."}
              className="w-full bg-surface-overlay border border-border rounded-lg px-3 py-2 text-sm text-text-primary placeholder-text-muted focus:outline-none focus:border-accent"
            />
          )}
        </div>

        {/* Options */}
        <div className="flex items-center gap-4">
          <label className="flex items-center gap-2 text-sm text-text-secondary">
            <input
              type="checkbox"
              checked={fireOnce}
              onChange={(e) => setFireOnce(e.target.checked)}
              className="accent-accent"
            />
            Fire once only
          </label>
          <div className="flex items-center gap-2 text-sm text-text-secondary">
            <label>Priority:</label>
            <input
              type="number"
              value={priority}
              onChange={(e) => setPriority(Number(e.target.value))}
              className="w-16 bg-surface-overlay border border-border rounded px-2 py-1 text-sm text-text-primary focus:outline-none focus:border-accent"
            />
          </div>
        </div>

        <div className="flex justify-end gap-2 pt-2">
          <button
            type="button"
            onClick={onClose}
            className="px-4 py-2 text-sm text-text-secondary hover:text-text-primary transition"
          >
            Cancel
          </button>
          <button
            type="submit"
            disabled={!content.trim() || createMutation.isPending}
            className="px-4 py-2 bg-accent hover:bg-accent-hover disabled:opacity-30 text-white rounded-lg text-sm transition"
          >
            {createMutation.isPending ? "Creating..." : "Create"}
          </button>
        </div>
      </form>
    </div>
  );
}
