import { useCallback, useState } from 'react';
import { Clock } from '../taskbar/Clock';
import { AppMenu } from './AppMenu';
import { COLORS, TOP_PANEL_HEIGHT } from '../theme/constants';

export function TopPanel() {
  const [menuOpen, setMenuOpen] = useState(false);

  const toggleMenu = useCallback(() => {
    setMenuOpen((prev) => !prev);
  }, []);

  const closeMenu = useCallback(() => {
    setMenuOpen(false);
  }, []);

  return (
    <>
      <header
        className="fixed top-0 left-0 right-0 flex items-center px-1"
        style={{
          height: TOP_PANEL_HEIGHT,
          backgroundColor: COLORS.taskbar,
          borderBottom: `1px solid ${COLORS.surfaceLighter}`,
          zIndex: 10000,
        }}
      >
        {/* App menu button */}
        <button
          className="flex items-center gap-1.5 px-2.5 rounded text-xs font-semibold transition-colors"
          style={{
            height: TOP_PANEL_HEIGHT - 4,
            color: menuOpen ? COLORS.text : COLORS.textMuted,
            backgroundColor: menuOpen ? 'rgba(255,255,255,0.12)' : 'transparent',
            border: 'none',
          }}
          onClick={toggleMenu}
          onMouseEnter={(e) => {
            if (!menuOpen) {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor =
                'rgba(255,255,255,0.08)';
            }
          }}
          onMouseLeave={(e) => {
            if (!menuOpen) {
              (e.currentTarget as HTMLButtonElement).style.backgroundColor = 'transparent';
            }
          }}
        >
          <span style={{ color: COLORS.primary, fontSize: 14, fontWeight: 700 }}>C</span>
          <span>Applications</span>
        </button>

        {/* Spacer */}
        <div className="flex-1" />

        {/* System tray area */}
        <Clock />
      </header>

      <AppMenu open={menuOpen} onClose={closeMenu} />
    </>
  );
}
