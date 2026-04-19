import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { BookMarked, CheckCircle2, AlertCircle, Trash2 } from "lucide-react";

import { obsidian, type ObsidianSettings as ObsidianSettingsData } from "@/api/client";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export function ObsidianSettings() {
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["obsidian-settings"],
    queryFn: obsidian.get,
  });

  const [baseUrl, setBaseUrl] = useState("");
  const [port, setPort] = useState<string>("");
  const [apiToken, setApiToken] = useState("");
  const [verifyTls, setVerifyTls] = useState(true);
  const [enabled, setEnabled] = useState(true);
  const [dirty, setDirty] = useState(false);

  useEffect(() => {
    if (!data) return;
    setBaseUrl(data.base_url ?? "");
    setPort(data.port != null ? String(data.port) : "");
    setVerifyTls(data.verify_tls);
    setEnabled(data.enabled);
    setApiToken(""); // never pre-fill token
    setDirty(false);
  }, [data]);

  const save = useMutation({
    mutationFn: (payload: Parameters<typeof obsidian.update>[0]) => obsidian.update(payload),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["obsidian-settings"] }),
  });

  const test = useMutation({
    mutationFn: () => obsidian.test(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["obsidian-settings"] }),
  });

  const remove = useMutation({
    mutationFn: () => obsidian.remove(),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["obsidian-settings"] }),
  });

  const onSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (!baseUrl) return;
    const payload = {
      base_url: baseUrl,
      port: port ? Number(port) : null,
      verify_tls: verifyTls,
      enabled,
      ...(apiToken ? { api_token: apiToken } : {}),
    };
    save.mutate(payload);
  };

  const onDelete = () => {
    if (!confirm("Remove Obsidian integration? You'll lose vault tools until reconfigured.")) return;
    remove.mutate();
  };

  const saveError = save.error instanceof Error ? save.error.message : null;
  const testResult = test.data;
  const testError = test.error instanceof Error ? test.error.message : null;

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-2">
        <BookMarked className="w-4 h-4" />
        <h3 className="text-sm font-semibold">Obsidian Vault</h3>
      </div>
      <p className="text-xs text-muted-foreground">
        Connect an Obsidian vault via the{" "}
        <a
          href="https://github.com/coddingtonbear/obsidian-local-rest-api"
          target="_blank"
          rel="noreferrer"
          className="underline"
        >
          Local REST API plugin
        </a>
        . Clara will be able to search, read, and edit notes on your behalf.
      </p>

      {isLoading ? (
        <p className="text-xs text-muted-foreground">Loading…</p>
      ) : (
        <form onSubmit={onSave} className="space-y-3">
          <div>
            <Label htmlFor="obs-base">Base URL</Label>
            <Input
              id="obs-base"
              placeholder="https://obsidian.example.com"
              value={baseUrl}
              onChange={(e) => {
                setBaseUrl(e.target.value);
                setDirty(true);
              }}
              required
            />
          </div>

          <div>
            <Label htmlFor="obs-port">Port (optional)</Label>
            <Input
              id="obs-port"
              type="number"
              min={1}
              max={65535}
              placeholder="27124"
              value={port}
              onChange={(e) => {
                setPort(e.target.value);
                setDirty(true);
              }}
            />
          </div>

          <div>
            <Label htmlFor="obs-token">API Token</Label>
            <Input
              id="obs-token"
              type="password"
              autoComplete="off"
              placeholder={data?.configured ? "••••••••  (leave blank to keep existing)" : "Bearer token from the plugin"}
              value={apiToken}
              onChange={(e) => {
                setApiToken(e.target.value);
                setDirty(true);
              }}
            />
          </div>

          <div className="flex gap-4 items-center">
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => {
                  setEnabled(e.target.checked);
                  setDirty(true);
                }}
              />
              Enabled
            </label>
            <label className="flex items-center gap-2 text-sm">
              <input
                type="checkbox"
                checked={verifyTls}
                onChange={(e) => {
                  setVerifyTls(e.target.checked);
                  setDirty(true);
                }}
              />
              Verify TLS
            </label>
          </div>

          {saveError && (
            <p className="text-xs text-destructive flex items-center gap-1">
              <AlertCircle className="w-3 h-3" /> {saveError}
            </p>
          )}

          <div className="flex gap-2 flex-wrap">
            <Button type="submit" disabled={!dirty || save.isPending}>
              {save.isPending ? "Saving…" : "Save"}
            </Button>
            <Button
              type="button"
              variant="outline"
              disabled={!data?.configured || test.isPending}
              onClick={() => test.mutate()}
            >
              {test.isPending ? "Testing…" : "Test Connection"}
            </Button>
            {data?.configured && (
              <Button
                type="button"
                variant="ghost"
                className="ml-auto text-destructive"
                onClick={onDelete}
                disabled={remove.isPending}
              >
                <Trash2 className="w-4 h-4 mr-1" /> Remove
              </Button>
            )}
          </div>
        </form>
      )}

      <div className="text-xs space-y-1 pt-2 border-t border-border">
        {data?.configured ? (
          <>
            <StatusLine
              ok={!!data.verified_at}
              label={
                data.verified_at
                  ? `Verified at ${new Date(data.verified_at).toLocaleString()}`
                  : "Not yet verified — run Test Connection"
              }
            />
            {data.last_error && (
              <p className="text-destructive flex items-center gap-1">
                <AlertCircle className="w-3 h-3" /> Last error: {data.last_error}
              </p>
            )}
          </>
        ) : (
          <p className="text-muted-foreground">Not configured.</p>
        )}
        {testResult && (
          <StatusLine
            ok={testResult.ok}
            label={`${testResult.ok ? "Connected" : "Failed"}: ${testResult.detail}`}
          />
        )}
        {testError && (
          <p className="text-destructive flex items-center gap-1">
            <AlertCircle className="w-3 h-3" /> {testError}
          </p>
        )}
      </div>
    </div>
  );
}

function StatusLine({ ok, label }: { ok: boolean; label: string }) {
  return (
    <p className={`flex items-center gap-1 ${ok ? "text-emerald-500" : "text-muted-foreground"}`}>
      {ok ? <CheckCircle2 className="w-3 h-3" /> : <AlertCircle className="w-3 h-3" />}
      {label}
    </p>
  );
}

// Keep types exported for convenience
export type { ObsidianSettingsData };
