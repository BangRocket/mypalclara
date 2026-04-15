import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Loader2 } from "lucide-react";
import { graph } from "@/api/client";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetDescription,
} from "@/components/ui/sheet";
import { ScrollArea } from "@/components/ui/scroll-area";
import { TYPE_COLORS } from "./EntityNode";

interface EntityDetailProps {
  entityName: string | null;
  onClose: () => void;
  onNavigate: (name: string) => void;
}

export function EntityDetail({ entityName, onClose, onNavigate }: EntityDetailProps) {
  const entityQuery = useQuery({
    queryKey: ["entity-detail", entityName],
    queryFn: () => graph.entity(entityName!),
    enabled: !!entityName,
  });

  const data = entityQuery.data;

  return (
    <Sheet open={!!entityName} onOpenChange={(open) => !open && onClose()}>
      <SheetContent side="right" className="w-[360px] sm:max-w-[400px] p-0">
        <SheetHeader className="border-b border-border p-4">
          <SheetTitle className="flex items-center gap-2">
            {entityName}
          </SheetTitle>
          <SheetDescription>Entity details and relationships</SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1 h-[calc(100vh-80px)]">
          <div className="p-4 space-y-4">
            {entityQuery.isLoading && (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
              </div>
            )}

            {data && (
              <>
                {/* Relationships */}
                <div>
                  <h3 className="text-sm font-medium text-muted-foreground mb-2">
                    Relationships ({data.relationships.length})
                  </h3>
                  {data.relationships.length === 0 ? (
                    <p className="text-sm text-muted-foreground">No relationships found.</p>
                  ) : (
                    <div className="space-y-1.5">
                      {data.relationships.map((rel, i) => (
                        <button
                          key={i}
                          onClick={() => onNavigate(rel.target)}
                          className="w-full text-left group rounded-lg border border-border p-2.5 hover:bg-muted/50 transition-colors"
                        >
                          <div className="flex items-center gap-2 text-sm">
                            <Badge variant="outline" className="text-[10px] px-1.5 py-0 shrink-0">
                              {rel.relationship}
                            </Badge>
                            <ArrowRight className="h-3 w-3 text-muted-foreground shrink-0" />
                            <span className="font-medium truncate group-hover:text-primary transition-colors">
                              {rel.target}
                            </span>
                            {rel.target_type && (
                              <span
                                className="w-2 h-2 rounded-full shrink-0 ml-auto"
                                style={{
                                  backgroundColor: TYPE_COLORS[rel.target_type] || TYPE_COLORS.default,
                                }}
                              />
                            )}
                          </div>
                          {rel.description && (
                            <p className="text-xs text-muted-foreground mt-1 line-clamp-2">
                              {rel.description}
                            </p>
                          )}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              </>
            )}
          </div>
        </ScrollArea>
      </SheetContent>
    </Sheet>
  );
}
