import { Navigate } from "react-router-dom";
import { useAuth } from "@/auth/AuthProvider";
import { useCharacterProfiles } from "@/hooks/useCharacterProfiles";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { CharacterBuilder } from "@/components/admin/CharacterBuilder";

const PERSONALITIES = ["clara", "flo", "clarissa", "dealer"] as const;

export function AdminCharactersPage() {
  const { user } = useAuth();
  const { data: profiles, isLoading } = useCharacterProfiles();

  if (user && !user.is_admin) {
    return <Navigate to="/" replace />;
  }

  if (isLoading) {
    return <div className="p-6 text-muted-foreground">Loading...</div>;
  }

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <div>
        <h2 className="text-lg font-semibold text-foreground">Character Profiles</h2>
        <p className="text-sm text-muted-foreground">
          Compose pixel-art appearances for each AI personality.
        </p>
      </div>

      <Tabs defaultValue="clara">
        <TabsList>
          {PERSONALITIES.map((p) => (
            <TabsTrigger key={p} value={p} className="capitalize">
              {p}
            </TabsTrigger>
          ))}
        </TabsList>

        {PERSONALITIES.map((p) => (
          <TabsContent key={p} value={p}>
            <CharacterBuilder
              personality={p}
              profile={profiles?.get(p)}
            />
          </TabsContent>
        ))}
      </Tabs>
    </div>
  );
}
