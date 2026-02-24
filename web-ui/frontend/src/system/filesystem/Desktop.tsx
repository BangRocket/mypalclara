import { useCallback, useEffect } from 'react';
import { useFileSystemStore } from './store';
import { DesktopIcon } from './Icon';
import { useAppRegistry } from '../apps/registry';
import { TASKBAR_HEIGHT } from '../theme/constants';

export function Desktop() {
  const desktopEntries = useFileSystemStore((s) => s.getDesktopEntries());
  const lookupSize = useFileSystemStore((s) => s.lookup.size);
  const { apps } = useAppRegistry();

  // Initialize file system on mount if empty
  useEffect(() => {
    if (lookupSize === 0) {
      useFileSystemStore.getState().initDesktop(apps);
    }
  }, [lookupSize, apps]);

  const handleClick = useCallback(() => {
    useFileSystemStore.getState().clearSelection();
  }, []);

  const handleContextMenu = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    // Desktop context menu — will be wired in Task 13
  }, []);

  const handleIconContextMenu = useCallback(
    (_e: React.MouseEvent, _entryId: string) => {
      // Icon context menu — will be wired in Task 13
    },
    [],
  );

  return (
    <div
      className="absolute inset-0"
      style={{
        bottom: TASKBAR_HEIGHT,
        height: `calc(100% - ${TASKBAR_HEIGHT}px)`,
      }}
      onClick={handleClick}
      onContextMenu={handleContextMenu}
    >
      {desktopEntries.map((entry) => (
        <DesktopIcon
          key={entry.id}
          entry={entry}
          onContextMenu={handleIconContextMenu}
        />
      ))}
    </div>
  );
}
