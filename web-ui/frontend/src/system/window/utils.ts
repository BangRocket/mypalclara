import type { Position, Size } from './types';
import { TASKBAR_HEIGHT, TOP_PANEL_HEIGHT, WINDOW_HEADER_HEIGHT } from '../theme/constants';

export function clampToBounds(pos: Position, size: Size): Position {
  const maxX = window.innerWidth - 50;
  const maxY = window.innerHeight - TASKBAR_HEIGHT - WINDOW_HEADER_HEIGHT;
  return {
    x: Math.max(-size.width + 50, Math.min(pos.x, maxX)),
    y: Math.max(TOP_PANEL_HEIGHT, Math.min(pos.y, maxY)),
  };
}
