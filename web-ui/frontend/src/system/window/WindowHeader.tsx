import { useWindowStore } from './store';
import { useWindowMove } from './hooks/useWindowMove';
import { COLORS, WINDOW_HEADER_HEIGHT, CLOSE_ANIMATION_DURATION } from '../theme/constants';

interface WindowHeaderProps {
  windowId: string;
  onClose?: () => void;
}

export function WindowHeader({ windowId, onClose }: WindowHeaderProps) {
  const { handleMoveStart } = useWindowMove(windowId);
  const title = useWindowStore((s) => s.getWindow(windowId)?.title ?? '');
  const icon = useWindowStore((s) => s.getWindow(windowId)?.icon);
  const isFocused = useWindowStore((s) => s.isFocused(windowId));
  const windowState = useWindowStore((s) => s.getWindowState(windowId));

  const handleMinimize = () => {
    useWindowStore.getState().minimizeWindow(windowId);
  };

  const handleMaximize = () => {
    useWindowStore.getState().toggleMaximize(windowId);
  };

  const handleClose = () => {
    if (onClose) {
      onClose();
    } else {
      useWindowStore.getState().setTransformScale(windowId, 0);
      setTimeout(() => {
        useWindowStore.getState().closeWindow(windowId);
      }, CLOSE_ANIMATION_DURATION);
    }
  };

  const handleDoubleClick = () => {
    handleMaximize();
  };

  return (
    <div
      className="flex items-center select-none shrink-0"
      style={{
        height: WINDOW_HEADER_HEIGHT,
        backgroundColor: isFocused ? COLORS.windowChromeActive : COLORS.windowChrome,
        borderTopLeftRadius: windowState === 'maximized' ? 0 : 8,
        borderTopRightRadius: windowState === 'maximized' ? 0 : 8,
        borderBottom: `1px solid ${COLORS.surfaceLighter}`,
      }}
      onMouseDown={handleMoveStart}
      onDoubleClick={handleDoubleClick}
    >
      <div className="flex items-center gap-2 flex-1 min-w-0 pl-3">
        {icon && <span className="text-sm">{icon}</span>}
        <span
          className="text-sm truncate"
          style={{ color: isFocused ? COLORS.text : COLORS.textMuted }}
        >
          {title}
        </span>
      </div>

      <div className="flex items-center h-full" onMouseDown={(e) => e.stopPropagation()}>
        <button
          className="flex items-center justify-center h-full px-3 transition-colors hover:bg-white/10"
          onClick={handleMinimize}
          title="Minimize"
        >
          <svg width="10" height="1" viewBox="0 0 10 1">
            <rect width="10" height="1" fill={COLORS.textMuted} />
          </svg>
        </button>

        <button
          className="flex items-center justify-center h-full px-3 transition-colors hover:bg-white/10"
          onClick={handleMaximize}
          title={windowState === 'maximized' ? 'Restore' : 'Maximize'}
        >
          {windowState === 'maximized' ? (
            <svg width="10" height="10" viewBox="0 0 10 10">
              <rect x="2" y="0" width="8" height="8" rx="1" fill="none" stroke={COLORS.textMuted} strokeWidth="1" />
              <rect x="0" y="2" width="8" height="8" rx="1" fill={COLORS.windowChromeActive} stroke={COLORS.textMuted} strokeWidth="1" />
            </svg>
          ) : (
            <svg width="10" height="10" viewBox="0 0 10 10">
              <rect x="0" y="0" width="10" height="10" rx="1" fill="none" stroke={COLORS.textMuted} strokeWidth="1" />
            </svg>
          )}
        </button>

        <button
          className="flex items-center justify-center h-full px-3 transition-colors"
          style={{ borderTopRightRadius: windowState === 'maximized' ? 0 : 8 }}
          onClick={handleClose}
          title="Close"
          onMouseEnter={(e) => {
            (e.currentTarget as HTMLElement).style.backgroundColor = COLORS.closeBtn;
          }}
          onMouseLeave={(e) => {
            (e.currentTarget as HTMLElement).style.backgroundColor = 'transparent';
          }}
        >
          <svg width="10" height="10" viewBox="0 0 10 10">
            <line x1="0" y1="0" x2="10" y2="10" stroke={COLORS.textMuted} strokeWidth="1.5" />
            <line x1="10" y1="0" x2="0" y2="10" stroke={COLORS.textMuted} strokeWidth="1.5" />
          </svg>
        </button>
      </div>
    </div>
  );
}
