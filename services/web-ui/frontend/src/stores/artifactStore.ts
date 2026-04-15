import { create } from "zustand";

export interface Artifact {
  id: string;
  title: string;
  type: "code" | "markdown" | "text";
  content: string;
  language?: string;
}

interface ArtifactStore {
  artifacts: Artifact[];
  activeId: string | null;
  panelOpen: boolean;

  addArtifact: (artifact: Artifact) => void;
  removeArtifact: (id: string) => void;
  setActive: (id: string) => void;
  openPanel: () => void;
  closePanel: () => void;
  togglePanel: () => void;
}

let artifactCounter = 0;

export function createArtifactId(): string {
  return `artifact-${++artifactCounter}`;
}

export const useArtifactStore = create<ArtifactStore>((set, get) => ({
  artifacts: [],
  activeId: null,
  panelOpen: false,

  addArtifact: (artifact) => {
    const { artifacts } = get();
    // Replace if same id, otherwise append
    const existing = artifacts.findIndex((a) => a.id === artifact.id);
    const updated = existing >= 0
      ? artifacts.map((a, i) => (i === existing ? artifact : a))
      : [...artifacts, artifact];
    set({ artifacts: updated, activeId: artifact.id, panelOpen: true });
  },

  removeArtifact: (id) => {
    const { artifacts, activeId } = get();
    const updated = artifacts.filter((a) => a.id !== id);
    const newActive = activeId === id
      ? (updated[0]?.id ?? null)
      : activeId;
    set({
      artifacts: updated,
      activeId: newActive,
      panelOpen: updated.length > 0,
    });
  },

  setActive: (id) => set({ activeId: id }),
  openPanel: () => set({ panelOpen: true }),
  closePanel: () => set({ panelOpen: false }),
  togglePanel: () => set((s) => ({ panelOpen: !s.panelOpen })),
}));
