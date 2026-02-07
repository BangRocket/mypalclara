import { create } from "zustand";
import { persist } from "zustand/middleware";

export interface SavedSet {
  id: string;
  name: string;
  filters: {
    category?: string;
    is_key?: boolean;
    sort?: string;
    order?: string;
    searchQuery?: string;
  };
  createdAt: string;
}

interface SavedSetsStore {
  sets: SavedSet[];
  addSet: (name: string, filters: SavedSet["filters"]) => void;
  removeSet: (id: string) => void;
  updateSet: (id: string, updates: Partial<SavedSet>) => void;
}

export const useSavedSets = create<SavedSetsStore>()(
  persist(
    (set) => ({
      sets: [],
      addSet: (name, filters) =>
        set((state) => ({
          sets: [
            ...state.sets,
            {
              id: crypto.randomUUID(),
              name,
              filters,
              createdAt: new Date().toISOString(),
            },
          ],
        })),
      removeSet: (id) =>
        set((state) => ({ sets: state.sets.filter((s) => s.id !== id) })),
      updateSet: (id, updates) =>
        set((state) => ({
          sets: state.sets.map((s) => (s.id === id ? { ...s, ...updates } : s)),
        })),
    }),
    { name: "clara-saved-sets" },
  ),
);
