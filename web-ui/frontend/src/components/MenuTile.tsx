import { forwardRef } from "react";

interface MenuTileProps {
  label: string;
  icon: string;
  accentColor: string;
  selected: boolean;
  offset: number; // distance from center: 0 = selected, ±1 = adjacent, etc.
  badge?: number;
  onClick: () => void;
}

export const MenuTile = forwardRef<HTMLButtonElement, MenuTileProps>(
  function MenuTile({ label, icon, accentColor, selected, offset, badge, onClick }, ref) {
    const absOffset = Math.abs(offset);
    const scale = selected ? 1 : Math.max(0.5, 1 - absOffset * 0.18);
    const opacity = selected ? 1 : Math.max(0.3, 1 - absOffset * 0.25);

    return (
      <button
        ref={ref}
        onClick={onClick}
        className="relative flex shrink-0 flex-col items-center justify-center outline-none transition-all duration-300 ease-out"
        style={{
          transform: `scale(${scale})`,
          opacity,
          width: 120,
        }}
      >
        <div
          className="flex items-center justify-center rounded-2xl p-5 transition-all duration-300"
          style={{
            background: selected
              ? `radial-gradient(circle, ${accentColor}18 0%, transparent 70%)`
              : "transparent",
            boxShadow: selected ? `0 0 40px ${accentColor}30, 0 0 80px ${accentColor}10` : "none",
          }}
        >
          <img
            src={icon}
            alt={label}
            className="h-16 w-16"
            draggable={false}
            style={{
              imageRendering: "pixelated",
              filter: selected
                ? `drop-shadow(0 0 8px ${accentColor}) drop-shadow(0 0 3px ${accentColor})`
                : "brightness(0.6)",
              transition: "filter 0.3s ease-out",
            }}
          />
        </div>
        {badge !== undefined && badge > 0 && (
          <span className="absolute -right-1 top-0 flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-white">
            {badge}
          </span>
        )}
      </button>
    );
  },
);
