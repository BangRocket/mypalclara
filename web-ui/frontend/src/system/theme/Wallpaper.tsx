import type { ReactNode } from 'react';
import { COLORS, TASKBAR_HEIGHT } from './constants';

export function Wallpaper({ children }: { children: ReactNode }) {
  return (
    <div
      className="fixed inset-0 overflow-hidden"
      style={{
        background: `linear-gradient(135deg, ${COLORS.surface} 0%, #1a1145 40%, ${COLORS.surface} 100%)`,
        paddingBottom: TASKBAR_HEIGHT,
      }}
    >
      {children}
    </div>
  );
}
