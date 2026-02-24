import { useWindowStore } from '../window/store';
import { COLORS, TASKBAR_ENTRY_WIDTH, TASKBAR_ENTRY_HEIGHT } from '../theme/constants';

interface TaskbarEntryProps {
  windowId: string;
}

export function TaskbarEntry({ windowId }: TaskbarEntryProps) {
  const win = useWindowStore((s) => s.getWindow(windowId));
  const isFocused = useWindowStore((s) => s.isFocused(windowId));
  const windowState = useWindowStore((s) => s.getWindowState(windowId));

  if (!win) return null;

  const isMinimized = windowState === 'minimized';

  const handleClick = () => {
    if (isFocused && !isMinimized) {
      useWindowStore.getState().minimizeWindow(windowId);
    } else {
      useWindowStore.getState().toggleMinimize(windowId);
      useWindowStore.getState().focusWindow(windowId);
    }
  };

  return (
    <button
      className="flex items-center gap-1.5 px-2 rounded text-xs transition-colors truncate"
      style={{
        width: TASKBAR_ENTRY_WIDTH,
        height: TASKBAR_ENTRY_HEIGHT,
        backgroundColor: isFocused
          ? 'rgba(255,255,255,0.15)'
          : isMinimized
            ? 'rgba(255,255,255,0.05)'
            : 'rgba(255,255,255,0.08)',
        color: isFocused ? COLORS.text : COLORS.textMuted,
        borderBottom: isFocused ? `2px solid ${COLORS.primary}` : '2px solid transparent',
      }}
      onClick={handleClick}
      title={win.title}
    >
      {win.icon && <span>{win.icon}</span>}
      <span className="truncate">{win.title}</span>
    </button>
  );
}
