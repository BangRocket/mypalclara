import { useWindowResize, type ResizeDirection } from './hooks/useWindowResize';

interface ResizeHandlesProps {
  windowId: string;
}

const HANDLE_SIZE = 6;
const CORNER_SIZE = 12;

interface HandleConfig {
  direction: ResizeDirection;
  className: string;
  style: React.CSSProperties;
}

const handles: HandleConfig[] = [
  { direction: 'left',   className: 'cursor-ew-resize',   style: { left: -HANDLE_SIZE/2, top: CORNER_SIZE, width: HANDLE_SIZE, bottom: CORNER_SIZE } },
  { direction: 'right',  className: 'cursor-ew-resize',   style: { right: -HANDLE_SIZE/2, top: CORNER_SIZE, width: HANDLE_SIZE, bottom: CORNER_SIZE } },
  { direction: 'top',    className: 'cursor-ns-resize',   style: { top: -HANDLE_SIZE/2, left: CORNER_SIZE, height: HANDLE_SIZE, right: CORNER_SIZE } },
  { direction: 'bottom', className: 'cursor-ns-resize',   style: { bottom: -HANDLE_SIZE/2, left: CORNER_SIZE, height: HANDLE_SIZE, right: CORNER_SIZE } },
  { direction: 'top-left',     className: 'cursor-nwse-resize', style: { top: -HANDLE_SIZE/2, left: -HANDLE_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { direction: 'top-right',    className: 'cursor-nesw-resize', style: { top: -HANDLE_SIZE/2, right: -HANDLE_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { direction: 'bottom-left',  className: 'cursor-nesw-resize', style: { bottom: -HANDLE_SIZE/2, left: -HANDLE_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE } },
  { direction: 'bottom-right', className: 'cursor-nwse-resize', style: { bottom: -HANDLE_SIZE/2, right: -HANDLE_SIZE/2, width: CORNER_SIZE, height: CORNER_SIZE } },
];

export function ResizeHandles({ windowId }: ResizeHandlesProps) {
  const { handleResizeStart } = useWindowResize(windowId);

  return (
    <>
      {handles.map((h) => (
        <div
          key={h.direction}
          className={`absolute z-50 ${h.className}`}
          style={{ ...h.style, position: 'absolute' }}
          onMouseDown={(e) => handleResizeStart(e, h.direction)}
        />
      ))}
    </>
  );
}
