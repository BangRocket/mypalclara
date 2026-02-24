export interface Position {
  x: number;
  y: number;
}

export interface Size {
  width: number;
  height: number;
}

export type WindowState = 'normal' | 'minimized' | 'maximized';

export interface WindowInstance {
  id: string;
  appId: string;
  position: Position;
  size: Size;
  defaultSize: Size;
  state: WindowState;
  previousPosition?: Position;   // For restore from maximize
  previousSize?: Size;           // For restore from maximize
  isMoving: boolean;
  isResizing: boolean;
  transformScale: number;        // 0=hidden, 1=normal (for open/close animation)
  contentOpacity: number;        // 0=hidden, 1=visible (staggered reveal)
  title: string;
  icon?: string;
}
