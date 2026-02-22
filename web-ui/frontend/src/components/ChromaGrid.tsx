import { useRef, useEffect } from "react";
import { gsap } from "gsap";

export interface GridItem {
  icon: string;
  label: string;
  description: string;
  detail: string;
  accentColor: string;
  badge?: number;
  onClick: () => void;
}

interface ChromaGridProps {
  items: GridItem[];
  radius?: number;
  damping?: number;
  onItemHover?: (index: number | null) => void;
  theme?: "light" | "dark";
}

type SetterFn = (v: number | string) => void;

export function ChromaGrid({
  items,
  radius = 250,
  damping = 0.45,
  onItemHover,
  theme = "dark",
}: ChromaGridProps) {
  const rootRef = useRef<HTMLDivElement>(null);
  const fadeRef = useRef<HTMLDivElement>(null);
  const setX = useRef<SetterFn | null>(null);
  const setY = useRef<SetterFn | null>(null);
  const pos = useRef({ x: 0, y: 0 });

  const light = theme === "light";

  useEffect(() => {
    const el = rootRef.current;
    if (!el) return;
    setX.current = gsap.quickSetter(el, "--x", "px") as SetterFn;
    setY.current = gsap.quickSetter(el, "--y", "px") as SetterFn;
    const { width, height } = el.getBoundingClientRect();
    pos.current = { x: width / 2, y: height / 2 };
    setX.current(pos.current.x);
    setY.current(pos.current.y);
  }, []);

  const moveTo = (x: number, y: number) => {
    gsap.to(pos.current, {
      x,
      y,
      duration: damping,
      ease: "power3.out",
      onUpdate: () => {
        setX.current?.(pos.current.x);
        setY.current?.(pos.current.y);
      },
      overwrite: true,
    });
  };

  const handleMove = (e: React.PointerEvent) => {
    const r = rootRef.current!.getBoundingClientRect();
    moveTo(e.clientX - r.left, e.clientY - r.top);
    gsap.to(fadeRef.current, { opacity: 0, duration: 0.25, overwrite: true });
  };

  const handleLeave = () => {
    gsap.to(fadeRef.current, {
      opacity: 1,
      duration: 0.6,
      overwrite: true,
    });
  };

  const handleCardMove: React.MouseEventHandler<HTMLElement> = (e) => {
    const c = e.currentTarget;
    const rect = c.getBoundingClientRect();
    c.style.setProperty("--mouse-x", `${e.clientX - rect.left}px`);
    c.style.setProperty("--mouse-y", `${e.clientY - rect.top}px`);
  };

  const overlayFilter = light
    ? "grayscale(0.85) brightness(1.08)"
    : "grayscale(1) brightness(0.78)";

  const spotlightColor = light
    ? "rgba(0,0,0,0.06)"
    : "rgba(255,255,255,0.15)";

  return (
    <div
      ref={rootRef}
      onPointerMove={handleMove}
      onPointerLeave={handleLeave}
      className="relative grid grid-cols-4 gap-4 w-full max-w-[960px] p-4"
      style={
        {
          "--r": `${radius}px`,
          "--x": "50%",
          "--y": "50%",
        } as React.CSSProperties
      }
    >
      {items.map((item, i) => (
        <article
          key={i}
          onMouseMove={handleCardMove}
          onMouseEnter={() => onItemHover?.(i)}
          onMouseLeave={() => onItemHover?.(null)}
          onClick={item.onClick}
          className="group relative flex flex-col items-center rounded-2xl overflow-hidden border transition-colors duration-300 cursor-pointer p-6"
          style={
            {
              "--card-border": item.accentColor,
              borderColor: light
                ? "rgba(160,140,110,0.15)"
                : "rgba(255,255,255,0.06)",
              background: light
                ? `linear-gradient(145deg, ${item.accentColor}10, rgba(235,225,210,0.7))`
                : `linear-gradient(145deg, ${item.accentColor}18, rgba(0,0,0,0.3))`,
            } as React.CSSProperties
          }
          onMouseOver={(e) => {
            (e.currentTarget as HTMLElement).style.borderColor =
              item.accentColor;
          }}
          onMouseOut={(e) => {
            (e.currentTarget as HTMLElement).style.borderColor = light
              ? "rgba(160,140,110,0.15)"
              : "rgba(255,255,255,0.06)";
          }}
        >
          {/* Spotlight on hover */}
          <div
            className="absolute inset-0 pointer-events-none opacity-0 group-hover:opacity-100 transition-opacity duration-500 z-20"
            style={{
              background: `radial-gradient(circle at var(--mouse-x) var(--mouse-y), ${spotlightColor}, transparent 70%)`,
            }}
          />

          {/* Icon */}
          <div className="relative z-10 w-20 h-20 mb-3">
            <img
              src={item.icon}
              alt={item.label}
              className="w-full h-full"
              style={{ imageRendering: "pixelated" }}
              draggable={false}
            />
          </div>

          {/* Label + badge */}
          <div className="relative z-10 text-center">
            <div className="flex items-center justify-center gap-1.5">
              <span
                className="text-base font-bold"
                style={{ color: light ? "#3d3529" : "rgba(255,255,255,0.9)" }}
              >
                {item.label}
              </span>
              {item.badge !== undefined && item.badge > 0 && (
                <span className="inline-flex items-center justify-center min-w-[18px] h-[18px] px-1 rounded-full bg-amber-500 text-[10px] font-bold text-white">
                  {item.badge}
                </span>
              )}
            </div>
            <p
              className="text-sm mt-0.5"
              style={{ color: light ? "#8a7e70" : "rgba(255,255,255,0.4)" }}
            >
              {item.description}
            </p>
          </div>
        </article>
      ))}

      {/* Chroma overlay — desaturate outside the spotlight radius */}
      <div
        className="absolute inset-0 pointer-events-none z-30"
        style={{
          backdropFilter: overlayFilter,
          WebkitBackdropFilter: overlayFilter,
          background: "rgba(0,0,0,0.001)",
          maskImage:
            "radial-gradient(circle var(--r) at var(--x) var(--y), transparent 0%, transparent 15%, rgba(0,0,0,0.10) 30%, rgba(0,0,0,0.22) 45%, rgba(0,0,0,0.35) 60%, rgba(0,0,0,0.50) 75%, rgba(0,0,0,0.68) 88%, white 100%)",
          WebkitMaskImage:
            "radial-gradient(circle var(--r) at var(--x) var(--y), transparent 0%, transparent 15%, rgba(0,0,0,0.10) 30%, rgba(0,0,0,0.22) 45%, rgba(0,0,0,0.35) 60%, rgba(0,0,0,0.50) 75%, rgba(0,0,0,0.68) 88%, white 100%)",
        }}
      />

      {/* Fade overlay — inverse mask, fades in when cursor leaves */}
      <div
        ref={fadeRef}
        className="absolute inset-0 pointer-events-none z-40"
        style={{
          backdropFilter: overlayFilter,
          WebkitBackdropFilter: overlayFilter,
          background: "rgba(0,0,0,0.001)",
          maskImage:
            "radial-gradient(circle var(--r) at var(--x) var(--y), white 0%, white 15%, rgba(255,255,255,0.90) 30%, rgba(255,255,255,0.78) 45%, rgba(255,255,255,0.65) 60%, rgba(255,255,255,0.50) 75%, rgba(255,255,255,0.32) 88%, transparent 100%)",
          WebkitMaskImage:
            "radial-gradient(circle var(--r) at var(--x) var(--y), white 0%, white 15%, rgba(255,255,255,0.90) 30%, rgba(255,255,255,0.78) 45%, rgba(255,255,255,0.65) 60%, rgba(255,255,255,0.50) 75%, rgba(255,255,255,0.32) 88%, transparent 100%)",
          opacity: 1,
        }}
      />
    </div>
  );
}
