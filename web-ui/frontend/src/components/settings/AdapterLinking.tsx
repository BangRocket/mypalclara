import { useQuery } from "@tanstack/react-query";
import { Link2 } from "lucide-react";
import { users } from "@/api/client";

export function AdapterLinking() {
  const { data } = useQuery({ queryKey: ["user-me"], queryFn: users.me });
  const linked = data?.links || [];

  if (linked.length === 0) {
    return (
      <div className="space-y-3">
        <h3 className="text-sm font-semibold">Linked Platforms</h3>
        <p className="text-xs text-muted-foreground">
          No platform accounts linked yet. Chat with Clara on Discord, Teams, or
          other platforms to automatically link your accounts.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <h3 className="text-sm font-semibold">Linked Platforms</h3>
      <p className="text-xs text-muted-foreground">
        Platform accounts linked to your identity. These are created
        automatically when you interact with Clara on each platform.
      </p>

      <div className="space-y-2">
        {linked.map((link) => (
          <div
            key={link.id}
            className="flex items-center justify-between rounded-lg border p-3"
          >
            <div className="flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/20 text-xs font-bold text-primary">
                <Link2 size={14} />
              </div>
              <div>
                <p className="text-sm font-medium capitalize">{link.platform}</p>
                <p className="text-xs text-muted-foreground">
                  {link.display_name || link.platform_user_id}
                </p>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
