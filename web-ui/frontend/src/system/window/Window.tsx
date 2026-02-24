import { Suspense, useEffect, useMemo, useState } from 'react';
import { useWindowStore } from './store';
import { WindowHeader } from './WindowHeader';
import { ResizeHandles } from './ResizeHandles';
import { useAppRegistry } from '../apps/registry';
import { COLORS, WINDOW_BORDER_RADIUS, WINDOW_OPEN_STAGGER } from '../theme/constants';

interface WindowProps {
  windowId: string;
  onClose?: () => void;
}

function WindowLoading() {
  return (
    <div className="flex items-center justify-center h-full" style={{ color: COLORS.textMuted }}>
      Loading...
    </div>
  );
}

export function Window({ windowId, onClose }: WindowProps) {
  const win = useWindowStore((s) => s.getWindow(windowId));
  const isFocused = useWindowStore((s) => s.isFocused(windowId));
  const zIndex = useWindowStore((s) => s.getZIndex(windowId));
  const isMoving = useWindowStore((s) => s.isMoving(windowId));
  const isResizing = useWindowStore((s) => s.isResizing(windowId));
  const { getComponent } = useAppRegistry();
  const [isReady, setIsReady] = useState(false);

  useEffect(() => {
    const t1 = setTimeout(() => useWindowStore.getState().setTransformScale(windowId, 1), WINDOW_OPEN_STAGGER[0]);
    const t2 = setTimeout(() => setIsReady(true), WINDOW_OPEN_STAGGER[1]);
    const t3 = setTimeout(() => useWindowStore.getState().setContentOpacity(windowId, 1), WINDOW_OPEN_STAGGER[2]);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); };
  }, [windowId]);

  const Component = useMemo(() => {
    if (!win) return null;
    return getComponent(win.appId);
  }, [win?.appId, getComponent]);

  if (!win) return null;

  const isMaximized = win.state === 'maximized';
  const useTransition = !isMoving && !isResizing;

  return (
    <div
      className="absolute flex flex-col"
      style={{
        width: win.size.width,
        height: win.size.height,
        transform: `translate(${win.position.x}px, ${win.state === 'minimized' ? window.innerHeight : win.position.y}px) scale(${win.transformScale})`,
        transition: useTransition ? 'transform 200ms ease-out, opacity 200ms ease-out' : 'none',
        zIndex,
        borderRadius: isMaximized ? 0 : WINDOW_BORDER_RADIUS,
        overflow: 'hidden',
        boxShadow: isFocused
          ? `0 8px 32px rgba(0,0,0,0.4), 0 0 0 1px ${COLORS.surfaceLighter}, 0 0 20px ${COLORS.accentGlow}`
          : `0 4px 16px rgba(0,0,0,0.3), 0 0 0 1px ${COLORS.surfaceLighter}`,
        backgroundColor: COLORS.surface,
      }}
      onMouseDown={() => useWindowStore.getState().focusWindow(windowId)}
    >
      {!isMaximized && <ResizeHandles windowId={windowId} />}
      <WindowHeader windowId={windowId} onClose={onClose} />
      <div
        className="flex-1 overflow-auto"
        style={{
          opacity: win.contentOpacity,
          transition: useTransition ? 'opacity 200ms ease-out' : 'none',
        }}
      >
        {isReady && Component && (
          <Suspense fallback={<WindowLoading />}>
            <Component windowId={windowId} />
          </Suspense>
        )}
      </div>
    </div>
  );
}
