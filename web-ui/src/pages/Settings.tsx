import { useAuth } from "@/auth/AuthProvider";
import { AdapterLinking } from "@/components/settings/AdapterLinking";

export function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      <h1 className="text-xl font-bold">Settings</h1>

      {/* Profile */}
      <section className="bg-surface-raised border border-border rounded-xl p-5 space-y-4">
        <h2 className="text-base font-semibold">Profile</h2>
        <div className="flex items-center gap-4">
          {user?.avatar_url ? (
            <img src={user.avatar_url} alt="" className="w-16 h-16 rounded-full" />
          ) : (
            <div className="w-16 h-16 rounded-full bg-accent/20 flex items-center justify-center text-xl font-bold text-accent">
              {user?.display_name?.[0]?.toUpperCase() || "?"}
            </div>
          )}
          <div>
            <p className="text-lg font-medium">{user?.display_name}</p>
            <p className="text-sm text-text-muted">{user?.email || "No email set"}</p>
          </div>
        </div>
      </section>

      {/* Linked Accounts */}
      <section className="bg-surface-raised border border-border rounded-xl p-5">
        <AdapterLinking />
      </section>
    </div>
  );
}
