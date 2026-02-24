import { useState, useMemo, useCallback } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { SpritePreview } from "./SpritePreview";
import { LayerPicker } from "./LayerPicker";
import { SPRITE_LAYERS, resolveSheetUrl } from "@/lib/spriteManifest";
import { characterProfiles, type CharacterProfile, type LayerRef } from "@/api/client";
import type { SpriteLayer } from "@/lib/spriteCompositor";

interface LayerSelection {
  sheet: string;
  row: number;
  col: number;
}

type LayerState = Record<string, LayerSelection | null>;

function profileToState(profile: CharacterProfile | undefined): LayerState {
  const state: LayerState = {};
  for (const layerDef of SPRITE_LAYERS) {
    const val = profile?.[layerDef.id as keyof CharacterProfile] as LayerRef | Record<string, never> | undefined;
    if (val && "row" in val && "col" in val) {
      state[layerDef.id] = {
        sheet: val.sheet || layerDef.sheets[0]?.filename || "",
        row: val.row,
        col: val.col,
      };
    } else {
      state[layerDef.id] = null;
    }
  }
  return state;
}

interface CharacterBuilderProps {
  personality: string;
  profile?: CharacterProfile;
}

export function CharacterBuilder({ personality, profile }: CharacterBuilderProps) {
  const queryClient = useQueryClient();
  const [displayName, setDisplayName] = useState(profile?.display_name || personality.charAt(0).toUpperCase() + personality.slice(1));
  const [layers, setLayers] = useState<LayerState>(() => profileToState(profile));

  const handleLayerChange = useCallback((layerId: string, value: LayerSelection | null) => {
    setLayers((prev) => ({ ...prev, [layerId]: value }));
  }, []);

  const previewLayers = useMemo<SpriteLayer[]>(() => {
    const result: SpriteLayer[] = [];
    for (const layerDef of SPRITE_LAYERS) {
      const sel = layers[layerDef.id];
      if (!sel) continue;
      const url = resolveSheetUrl(layerDef.category, sel.sheet);
      if (!url) continue;
      result.push({ imageSrc: url, row: sel.row, col: sel.col });
    }
    return result;
  }, [layers]);

  const buildPayload = () => {
    const payload: Record<string, unknown> = {
      personality,
      display_name: displayName,
    };
    for (const layerDef of SPRITE_LAYERS) {
      const sel = layers[layerDef.id];
      if (sel) {
        const ref: Record<string, unknown> = { row: sel.row, col: sel.col };
        if (layerDef.sheets.length > 1) ref.sheet = sel.sheet;
        payload[layerDef.id] = ref;
      } else {
        payload[layerDef.id] = {};
      }
    }
    return payload;
  };

  const saveMutation = useMutation({
    mutationFn: async () => {
      const payload = buildPayload();
      if (profile) {
        return characterProfiles.update(personality, payload as Parameters<typeof characterProfiles.update>[1]);
      } else {
        return characterProfiles.create(payload as Parameters<typeof characterProfiles.create>[0]);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["characterProfiles"] });
    },
  });

  const hasBase = layers.base_layer !== null;

  return (
    <div className="flex flex-col lg:flex-row gap-6">
      {/* Left panel — preview */}
      <div className="flex flex-col items-center gap-4 lg:sticky lg:top-4 lg:self-start">
        <SpritePreview layers={previewLayers} size={120} />
        <div className="text-sm text-muted-foreground font-mono">
          {displayName || personality}
        </div>
      </div>

      {/* Right panel — editors */}
      <div className="flex-1 space-y-6 min-w-0">
        <div className="space-y-2">
          <Label htmlFor={`name-${personality}`}>Display Name</Label>
          <Input
            id={`name-${personality}`}
            value={displayName}
            onChange={(e) => setDisplayName(e.target.value)}
            placeholder="Enter display name"
          />
        </div>

        {SPRITE_LAYERS.map((layerDef) => (
          <LayerPicker
            key={layerDef.id}
            layer={layerDef}
            value={layers[layerDef.id]}
            onChange={(v) => handleLayerChange(layerDef.id, v)}
          />
        ))}

        <div className="flex items-center gap-3 pt-4">
          <Button
            onClick={() => saveMutation.mutate()}
            disabled={saveMutation.isPending || !hasBase || !displayName.trim()}
          >
            {saveMutation.isPending ? "Saving..." : profile ? "Update" : "Create"}
          </Button>
          {saveMutation.isSuccess && (
            <span className="text-sm text-green-500">Saved</span>
          )}
          {saveMutation.isError && (
            <span className="text-sm text-destructive">
              {(saveMutation.error as Error).message}
            </span>
          )}
        </div>
      </div>
    </div>
  );
}
