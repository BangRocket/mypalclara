// ClaraOS theme constants
// Reference: bogdan-os themes/index.ts with Clara customizations

// Layout
export const TASKBAR_HEIGHT = 44;
export const TASKBAR_ENTRY_WIDTH = 140;
export const TASKBAR_ENTRY_HEIGHT = 32;
export const WINDOW_HEADER_HEIGHT = 36;
export const WINDOW_BORDER_RADIUS = 8;
export const GRID_CELL_SIZE = 100;
export const ICON_SIZE = { width: 80, height: 88 };
export const CONTEXT_MENU_WIDTH = 180;
export const CONTEXT_MENU_ITEM_HEIGHT = 32;
export const DEFAULT_WINDOW_SIZE = { width: 600, height: 450 };

// Animation
export const CLOSE_ANIMATION_DURATION = 200;
export const ICON_ANIMATION_DURATION = 100;
export const WINDOW_OPEN_STAGGER = [1, 200, 300]; // scale, ready, opacity delays

// Colors (Clara palette — indigo/violet on dark slate)
export const COLORS = {
  primary: '#6366f1',        // Indigo-500
  primaryHover: '#818cf8',   // Indigo-400
  accent: '#8b5cf6',         // Violet-500
  accentGlow: 'rgba(139, 92, 246, 0.3)',
  surface: '#0f172a',        // Slate-900
  surfaceLight: '#1e293b',   // Slate-800
  surfaceLighter: '#334155',  // Slate-700
  windowChrome: '#1e293b',
  windowChromeActive: '#283548',
  taskbar: 'rgba(15, 23, 42, 0.85)',
  text: '#f8fafc',           // Slate-50
  textMuted: '#94a3b8',      // Slate-400
  textDim: '#64748b',        // Slate-500
  closeBtn: '#ef4444',       // Red-500
  minimizeBtn: '#f59e0b',    // Amber-500
  maximizeBtn: '#22c55e',    // Green-500
} as const;
