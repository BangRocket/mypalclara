import { useWindowStore } from '../window/store';
import { TaskbarEntry } from './TaskbarEntry';
import { COLORS, TASKBAR_HEIGHT } from '../theme/constants';

export function Taskbar() {
  const openedIds = useWindowStore((s) => s.getOpenedIds());

  return (
    <footer
      className="fixed bottom-0 left-0 right-0 flex items-center px-2 gap-1 backdrop-blur-xl"
      style={{
        height: TASKBAR_HEIGHT,
        backgroundColor: COLORS.taskbar,
        borderTop: `1px solid ${COLORS.surfaceLighter}`,
        zIndex: 9999,
      }}
    >
      <div className="flex items-center gap-1 flex-1 overflow-x-auto">
        {openedIds.map((id) => (
          <TaskbarEntry key={id} windowId={id} />
        ))}
      </div>
    </footer>
  );
}
