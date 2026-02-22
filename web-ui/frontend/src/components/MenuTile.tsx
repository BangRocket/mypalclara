import { Link } from "react-router-dom";

interface MenuTileProps {
  to: string;
  label: string;
  icon: string;
  accentColor: string;
  badge?: number;
}

export function MenuTile({ to, label, icon, accentColor, badge }: MenuTileProps) {
  return (
    <Link
      to={to}
      className="snes-container group relative flex flex-col items-center justify-center gap-3 p-6 transition-transform hover:scale-105 active:scale-95"
      style={{ "--tile-accent": accentColor } as React.CSSProperties}
    >
      <img
        src={icon}
        alt={label}
        className="h-16 w-16"
        draggable={false}
        style={{
          imageRendering: "pixelated",
          filter: `brightness(0) saturate(100%) drop-shadow(0 0 1px ${accentColor})`,
        }}
      />
      <span className="text-sm font-medium text-foreground">{label}</span>
      {badge !== undefined && badge > 0 && (
        <span className="absolute right-2 top-2 flex h-5 min-w-5 items-center justify-center rounded-full bg-amber-500 px-1 text-[10px] font-bold text-white">
          {badge}
        </span>
      )}
    </Link>
  );
}
