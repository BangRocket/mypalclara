import { create } from 'zustand';
import type { ContextMenuItem } from './types';

interface ContextMenuState {
  items: ContextMenuItem[];
  position: { x: number; y: number };
  visible: boolean;

  show: (items: ContextMenuItem[], position: { x: number; y: number }) => void;
  hide: () => void;
}

export const useContextMenuStore = create<ContextMenuState>()((set) => ({
  items: [],
  position: { x: 0, y: 0 },
  visible: false,

  show: (items, position) => set({ items, position, visible: true }),
  hide: () => set({ visible: false }),
}));
