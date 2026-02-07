import { useQuery } from "@tanstack/react-query";
import { Link2, Unlink, ExternalLink } from "lucide-react";
import { users, auth } from "@/api/client";

const PROVIDERS = [
  { id: "discord", name: "Discord", color: "#5865f2" },
  { id: "google", name: "Google", color: "#4285f4" },
];

export function AdapterLinking() {
  const { data, refetch } = useQuery({ queryKey: ["user-me"], queryFn: users.me });
  const linked = data?.links || [];

  const handleLink = async (provider: string) => {
    const { url } = await auth.loginUrl(provider);
    // Store current path to return after linking
    sessionStorage.setItem("link_return", "/settings");
    window.location.href = url;
  };

  const handleUnlink = async (provider: string) => {
    if (!confirm(`Unlink your ${provider} account?`)) return;
    try {
      await fetch(`/auth/link/${provider}`, { method: "DELETE", credentials: "include" });
      refetch();
    } catch (e) {
      alert("Failed to unlink. You must keep at least one account linked.");
    }
  };

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold text-text-primary">Linked Accounts</h3>
      <p className="text-xs text-text-muted">
        Link accounts from different platforms to unify your memories and identity.
      </p>

      <div className="space-y-2">
        {PROVIDERS.map((p) => {
          const link = linked.find((l) => l.platform === p.id);
          return (
            <div
              key={p.id}
              className="flex items-center justify-between p-3 bg-surface-overlay border border-border rounded-lg"
            >
              <div className="flex items-center gap-3">
                <div
                  className="w-8 h-8 rounded-full flex items-center justify-center text-white text-xs font-bold"
                  style={{ backgroundColor: p.color }}
                >
                  {p.name[0]}
                </div>
                <div>
                  <p className="text-sm font-medium text-text-primary">{p.name}</p>
                  {link && (
                    <p className="text-xs text-text-muted">
                      {link.display_name || link.platform_user_id}
                    </p>
                  )}
                </div>
              </div>

              {link ? (
                <button
                  onClick={() => handleUnlink(p.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-danger hover:bg-danger/10 rounded-lg transition"
                >
                  <Unlink size={14} />
                  Unlink
                </button>
              ) : (
                <button
                  onClick={() => handleLink(p.id)}
                  className="flex items-center gap-1.5 px-3 py-1.5 text-xs text-accent hover:bg-accent/10 rounded-lg transition"
                >
                  <Link2 size={14} />
                  Link
                </button>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
