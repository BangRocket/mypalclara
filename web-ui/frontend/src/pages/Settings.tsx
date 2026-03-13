import { useUser } from "@clerk/react";
import { AdapterLinking } from "@/components/settings/AdapterLinking";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useChatStore, type ModelTier } from "@/stores/chatStore";

const TIER_OPTIONS: { value: ModelTier; label: string; description: string }[] = [
  { value: "low", label: "Low / Fast", description: "Haiku-class. Quick responses, lower cost." },
  { value: "mid", label: "Mid / Balanced", description: "Sonnet-class. Good balance of speed and quality." },
  { value: "high", label: "High / Powerful", description: "Opus-class. Most capable, slower." },
];

export function SettingsPage() {
  const { user } = useUser();
  const selectedTier = useChatStore((s) => s.selectedTier);
  const setTier = useChatStore((s) => s.setTier);

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
              <AvatarImage src={user?.imageUrl || undefined} alt={user?.fullName || "User"} />
              <AvatarFallback className="bg-primary/20 text-primary text-xl">
                {(user?.firstName || user?.fullName || "?")?.[0]?.toUpperCase()}
              </AvatarFallback>
            </Avatar>
            <div>
              <p className="text-lg font-medium">{user?.fullName || user?.firstName || "User"}</p>
              <p className="text-sm text-muted-foreground">
                {user?.primaryEmailAddress?.emailAddress || "No email set"}
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* Model Tier */}
      <Card>
        <CardHeader>
          <CardTitle>Model</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <div className="space-y-1.5">
            <Label htmlFor="tier-select">Default tier</Label>
            <Select value={selectedTier} onValueChange={(v) => setTier(v as ModelTier)}>
              <SelectTrigger id="tier-select" className="w-full">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TIER_OPTIONS.map((t) => (
                  <SelectItem key={t.value} value={t.value}>
                    {t.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              {TIER_OPTIONS.find((t) => t.value === selectedTier)?.description}
            </p>
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
