import { useCallback, useRef } from 'react';
import { useWindowStore } from '../store';
import { TASKBAR_HEIGHT } from '../../theme/constants';

export type ResizeDirection =
  | 'left' | 'right' | 'top' | 'bottom'
  | 'top-left' | 'top-right' | 'bottom-left' | 'bottom-right';

export function useWindowResize(windowId: string) {
  const directionRef = useRef<ResizeDirection | null>(null);

  const handleResizeStart = useCallback(
    (event: React.MouseEvent, direction: ResizeDirection) => {
      event.preventDefault();
      event.stopPropagation();
      directionRef.current = direction;
      useWindowStore.getState().setResizing(windowId, true);
      useWindowStore.getState().focusWindow(windowId);

      const handleMouseMove = (e: MouseEvent) => {
        const dir = directionRef.current;
        if (!dir) return;

        const state = useWindowStore.getState();
        const { x: posX, y: posY } = state.getPosition(windowId);
        const { width: curW, height: curH } = state.getSize(windowId);
        const win = state.getWindow(windowId);
        const minW = win?.defaultSize.width ?? 200;
        const minH = win?.defaultSize.height ?? 150;

        let newX = posX, newY = posY, newW = curW, newH = curH;

        if (dir.includes('right')) {
          newW = Math.max(e.clientX - posX, minW);
        }
        if (dir.includes('bottom')) {
          newH = Math.max(e.clientY - posY, minH);
        }
        if (dir.includes('left')) {
          newX = Math.min(e.clientX, posX + curW - minW);
          newX = Math.max(0, newX);
          newW = curW + posX - newX;
        }
        if (dir.includes('top')) {
          newY = Math.min(e.clientY, posY + curH - minH);
          newY = Math.max(0, newY);
          newH = curH + posY - newY;
        }

        newW = Math.min(newW, window.innerWidth - newX);
        newH = Math.min(newH, window.innerHeight - TASKBAR_HEIGHT - newY);

        state.setSize(windowId, { width: newW, height: newH });
        state.setPosition(windowId, { x: newX, y: newY });
      };

      const handleMouseUp = () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        directionRef.current = null;
        useWindowStore.getState().setResizing(windowId, false);
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [windowId],
  );

  return { handleResizeStart };
}
