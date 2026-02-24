import { useCallback, useEffect, useRef } from 'react';
import { useContextMenuStore } from './store';
import {
  COLORS,
  CONTEXT_MENU_WIDTH,
  CONTEXT_MENU_ITEM_HEIGHT,
} from '../theme/constants';

export function ContextMenu() {
  const visible = useContextMenuStore((s) => s.visible);
  const items = useContextMenuStore((s) => s.items);
  const position = useContextMenuStore((s) => s.position);
  const menuRef = useRef<HTMLDivElement>(null);

  const hide = useCallback(() => {
    useContextMenuStore.getState().hide();
  }, []);

  // Dismiss on click anywhere or right-click
  useEffect(() => {
    if (!visible) return;

    const handleDismiss = () => hide();
    const handleContextMenu = (e: MouseEvent) => {
      // Only dismiss if clicking outside the menu
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        hide();
      }
    };

    // Delay listener attachment so the opening click doesn't immediately dismiss
    const timer = setTimeout(() => {
      window.addEventListener('click', handleDismiss);
      window.addEventListener('contextmenu', handleContextMenu);
    }, 0);

    return () => {
      clearTimeout(timer);
      window.removeEventListener('click', handleDismiss);
      window.removeEventListener('contextmenu', handleContextMenu);
    };
  }, [visible, hide]);

  if (!visible || items.length === 0) return null;

  // Clamp position to viewport bounds
  const menuHeight = items.reduce(
    (h, item) => h + CONTEXT_MENU_ITEM_HEIGHT + (item.dividerAfter ? 1 : 0),
    8, // padding
  );
  const clampedX = Math.min(position.x, window.innerWidth - CONTEXT_MENU_WIDTH - 8);
  const clampedY = Math.min(position.y, window.innerHeight - menuHeight - 8);

  return (
    <div
      ref={menuRef}
      className="fixed py-1 rounded-lg shadow-xl"
      style={{
        left: Math.max(0, clampedX),
        top: Math.max(0, clampedY),
        width: CONTEXT_MENU_WIDTH,
        backgroundColor: COLORS.surfaceLight,
        border: `1px solid ${COLORS.surfaceLighter}`,
        zIndex: 99999,
      }}
    >
      {items.map((item, i) => (
        <div key={i}>
          <button
            className="w-full text-left px-3 text-sm rounded-none"
            style={{
              height: CONTEXT_MENU_ITEM_HEIGHT,
              color: item.disabled ? COLORS.textDim : COLORS.text,
              cursor: item.disabled ? 'default' : 'pointer',
              backgroundColor: 'transparent',
              border: 'none',
              outline: 'none',
            }}
            disabled={item.disabled}
            onClick={(e) => {
              e.stopPropagation();
              if (!item.disabled) {
                item.action();
                hide();
              }
            }}
            onMouseEnter={(e) => {
              if (!item.disabled) {
                (e.currentTarget as HTMLButtonElement).style.backgroundColor =
                  `${COLORS.primary}33`;
              }
            }}
            onMouseLeave={(e) => {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor =
                'transparent';
            }}
          >
            {item.label}
          </button>
          {item.dividerAfter && (
            <div
              className="mx-2 my-0.5"
              style={{
                height: 1,
                backgroundColor: COLORS.surfaceLighter,
              }}
            />
          )}
        </div>
      ))}
    </div>
  );
}
