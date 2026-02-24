import { useCallback, useEffect, useRef, useState } from 'react';
import { useAppRegistry } from '../apps/registry';
import { useWindowStore } from '../window/store';
import { COLORS, TOP_PANEL_HEIGHT } from '../theme/constants';

interface AppMenuProps {
  open: boolean;
  onClose: () => void;
}

export function AppMenu({ open, onClose }: AppMenuProps) {
  const { apps } = useAppRegistry();
  const [search, setSearch] = useState('');
  const menuRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Focus search on open
  useEffect(() => {
    if (open) {
      setSearch('');
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  // Dismiss on click outside
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        onClose();
      }
    };
    const timer = setTimeout(() => {
      window.addEventListener('mousedown', handleClick);
    }, 0);
    return () => {
      clearTimeout(timer);
      window.removeEventListener('mousedown', handleClick);
    };
  }, [open, onClose]);

  // Dismiss on Escape
  useEffect(() => {
    if (!open) return;
    const handleKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKey);
    return () => window.removeEventListener('keydown', handleKey);
  }, [open, onClose]);

  const handleLaunch = useCallback(
    (appId: string) => {
      const app = apps.get(appId);
      if (!app) return;
      useWindowStore
        .getState()
        .openWindow(appId, appId, app.name, app.defaultWindowSize, app.icon);
      onClose();
    },
    [apps, onClose],
  );

  if (!open) return null;

  const filtered = Array.from(apps.values()).filter((app) =>
    app.name.toLowerCase().includes(search.toLowerCase()),
  );

  return (
    <div
      ref={menuRef}
      className="fixed rounded-b-lg shadow-2xl flex flex-col"
      style={{
        top: TOP_PANEL_HEIGHT,
        left: 0,
        width: 280,
        maxHeight: 420,
        backgroundColor: COLORS.surfaceLight,
        border: `1px solid ${COLORS.surfaceLighter}`,
        borderTop: 'none',
        zIndex: 100000,
      }}
    >
      {/* Search */}
      <div className="p-2">
        <input
          ref={inputRef}
          type="text"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          placeholder="Search apps..."
          className="w-full rounded px-2.5 py-1.5 text-xs outline-none"
          style={{
            backgroundColor: COLORS.surface,
            color: COLORS.text,
            border: `1px solid ${COLORS.surfaceLighter}`,
          }}
        />
      </div>

      {/* App list */}
      <div className="flex-1 overflow-y-auto px-1 pb-2">
        {filtered.map((app) => (
          <button
            key={app.id}
            className="w-full flex items-center gap-2.5 px-2.5 py-1.5 rounded text-left transition-colors"
            style={{
              color: COLORS.text,
              backgroundColor: 'transparent',
              border: 'none',
            }}
            onClick={() => handleLaunch(app.id)}
            onMouseEnter={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = `${COLORS.primary}33`;
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
            }}
          >
            <span className="text-base w-6 text-center">{app.icon}</span>
            <span className="text-xs">{app.name}</span>
          </button>
        ))}
        {filtered.length === 0 && (
          <div className="text-xs px-3 py-4 text-center" style={{ color: COLORS.textDim }}>
            No apps found
          </div>
        )}
      </div>
    </div>
  );
}
