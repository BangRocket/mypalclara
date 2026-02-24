import { useCallback, useRef } from 'react';
import { useWindowStore } from '../store';
import { clampToBounds } from '../utils';

export function useWindowMove(windowId: string) {
  const offsetRef = useRef({ x: 0, y: 0 });

  const handleMoveStart = useCallback(
    (event: React.MouseEvent) => {
      event.preventDefault();
      const pos = useWindowStore.getState().getPosition(windowId);
      offsetRef.current = {
        x: event.clientX - pos.x,
        y: event.clientY - pos.y,
      };
      useWindowStore.getState().setMoving(windowId, true);
      useWindowStore.getState().focusWindow(windowId);

      const handleMouseMove = (e: MouseEvent) => {
        const x = e.clientX - offsetRef.current.x;
        const y = e.clientY - offsetRef.current.y;
        useWindowStore.getState().setPosition(windowId, { x, y });
      };

      const handleMouseUp = () => {
        window.removeEventListener('mousemove', handleMouseMove);
        window.removeEventListener('mouseup', handleMouseUp);
        useWindowStore.getState().setMoving(windowId, false);
        const pos = useWindowStore.getState().getPosition(windowId);
        const size = useWindowStore.getState().getSize(windowId);
        const clamped = clampToBounds(pos, size);
        if (clamped.x !== pos.x || clamped.y !== pos.y) {
          useWindowStore.getState().setPosition(windowId, clamped);
        }
      };

      window.addEventListener('mousemove', handleMouseMove);
      window.addEventListener('mouseup', handleMouseUp);
    },
    [windowId],
  );

  return { handleMoveStart };
}
