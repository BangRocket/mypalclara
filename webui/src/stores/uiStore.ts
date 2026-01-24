import { create } from 'zustand';

interface UiState {
  // Selection state
  selectedNoteId: number | null;
  selectedFolderId: number | null;

  // UI state
  sidebarCollapsed: boolean;

  // Actions
  selectNote: (id: number | null) => void;
  selectFolder: (id: number | null) => void;
  toggleSidebar: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  selectedNoteId: null,
  selectedFolderId: null,
  sidebarCollapsed: false,

  selectNote: (id) => set({ selectedNoteId: id }),
  selectFolder: (id) => set({ selectedFolderId: id }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
}));
