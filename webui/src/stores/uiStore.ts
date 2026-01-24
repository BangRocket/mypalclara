import { create } from 'zustand';

interface UiState {
  // Selection state
  selectedNoteId: number | null;
  selectedFolderId: number | null;

  // Daily note state
  selectedDate: string | null; // YYYY-MM-DD format
  viewingDailyNote: boolean;

  // UI state
  sidebarCollapsed: boolean;

  // Actions
  selectNote: (id: number | null) => void;
  selectFolder: (id: number | null) => void;
  selectDate: (date: string | null) => void;
  setViewingDailyNote: (viewing: boolean) => void;
  toggleSidebar: () => void;
}

export const useUiStore = create<UiState>((set) => ({
  selectedNoteId: null,
  selectedFolderId: null,
  selectedDate: null,
  viewingDailyNote: false,
  sidebarCollapsed: false,

  selectNote: (id) => set({ selectedNoteId: id, viewingDailyNote: false }),
  selectFolder: (id) => set({ selectedFolderId: id }),
  selectDate: (date) => set({ selectedDate: date, viewingDailyNote: true }),
  setViewingDailyNote: (viewing) => set({ viewingDailyNote: viewing }),
  toggleSidebar: () => set((state) => ({ sidebarCollapsed: !state.sidebarCollapsed })),
}));
