import { useAuth } from "@/auth/AuthProvider";
import { AdapterLinking } from "@/components/settings/AdapterLinking";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";

export function SettingsPage() {
  const { user } = useAuth();

  return (
    <div className="max-w-2xl mx-auto p-6 space-y-8">
      <h1 className="text-xl font-bold">Settings</h1>

      {/* Profile */}
      <Card>
        <CardHeader>
          <CardTitle>Profile</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex items-center gap-4">
            <Avatar className="w-16 h-16">
              <AvatarImage src={user?.avatar_url || undefined} alt={user?.display_name} />
              <AvatarFallback className="bg-primary/20 text-primary text-xl">
                {user?.display_name?.[0]?.toUpperCase() || "?"}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="text-lg font-medium">{user?.display_name}</p>
              <p className="text-sm text-muted-foreground">{user?.email || "No email set"}</p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Linked Accounts */}
      <Card>
        <CardContent className="pt-6">
          <AdapterLinking />
        </CardContent>
      </Card>
    </div>
  );
}
