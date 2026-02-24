import { useCallback, useEffect, useRef, useState } from 'react';
import { useFileSystemStore } from './store';
import { useAppRegistry } from '../apps/registry';
import { useWindowStore } from '../window/store';
import { COLORS, ICON_SIZE } from '../theme/constants';
import type { FSEntry } from './types';

interface DesktopIconProps {
  entry: FSEntry;
  onContextMenu: (e: React.MouseEvent, entryId: string) => void;
}

export function DesktopIcon({ entry, onContextMenu }: DesktopIconProps) {
  const isSelected = useFileSystemStore((s) => s.isSelected(entry.id));
  const renaming = useFileSystemStore((s) => s.renaming);
  const isRenaming = renaming === entry.id;
  const { getApp } = useAppRegistry();

  const [renameValue, setRenameValue] = useState(entry.name);
  const renameInputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (isRenaming && renameInputRef.current) {
      setRenameValue(entry.name);
      renameInputRef.current.focus();
      renameInputRef.current.select();
    }
  }, [isRenaming, entry.name]);

  const handleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();
      if (e.shiftKey || e.metaKey) {
        useFileSystemStore.getState().toggleSelect(entry.id);
      } else {
        useFileSystemStore.getState().select(entry.id);
      }
    },
    [entry.id],
  );

  const handleDoubleClick = useCallback(
    (e: React.MouseEvent) => {
      e.stopPropagation();

      if (entry.type === 'app-shortcut') {
        const app = getApp(entry.appId);
        if (app) {
          const windowId = app.singleton ? entry.appId : entry.id;
          useWindowStore
            .getState()
            .openWindow(
              windowId,
              entry.appId,
              app.name,
              app.defaultWindowSize,
              app.icon,
            );
        }
      } else if (entry.type === 'directory') {
        useWindowStore
          .getState()
          .openWindow(entry.id, 'file-explorer', entry.name, undefined, entry.icon);
      } else if (entry.type === 'file') {
        useWindowStore
          .getState()
          .openWindow(entry.id, 'text-editor', entry.name, undefined, entry.icon);
      }
    },
    [entry, getApp],
  );

  const handleRightClick = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      e.stopPropagation();
      // Select the icon if not already selected
      if (!useFileSystemStore.getState().isSelected(entry.id)) {
        useFileSystemStore.getState().select(entry.id);
      }
      onContextMenu(e, entry.id);
    },
    [entry.id, onContextMenu],
  );

  const handleRenameSubmit = useCallback(() => {
    const trimmed = renameValue.trim();
    if (trimmed && trimmed !== entry.name) {
      useFileSystemStore.getState().renameEntry(entry.id, trimmed);
    } else {
      useFileSystemStore.getState().setRenaming(null);
    }
  }, [entry.id, entry.name, renameValue]);

  const handleRenameKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        handleRenameSubmit();
      } else if (e.key === 'Escape') {
        useFileSystemStore.getState().setRenaming(null);
      }
    },
    [handleRenameSubmit],
  );

  const iconEmoji = entry.icon ?? (entry.type === 'directory' ? '\uD83D\uDCC1' : '\uD83D\uDCC4');

  return (
    <div
      data-entry-id={entry.id}
      className="absolute flex flex-col items-center cursor-pointer select-none"
      style={{
        left: entry.iconPosition.x,
        top: entry.iconPosition.y,
        width: ICON_SIZE.width,
        height: ICON_SIZE.height,
      }}
      onClick={handleClick}
      onDoubleClick={handleDoubleClick}
      onContextMenu={handleRightClick}
    >
      {/* Icon area */}
      <div
        className="flex items-center justify-center rounded-lg"
        style={{
          width: 48,
          height: 48,
          fontSize: 32,
          backgroundColor: isSelected ? `${COLORS.primary}22` : 'transparent',
          border: isSelected ? `2px solid ${COLORS.primary}` : '2px solid transparent',
          transition: 'background-color 100ms, border-color 100ms',
        }}
      >
        {iconEmoji}
      </div>

      {/* Label */}
      {isRenaming ? (
        <input
          ref={renameInputRef}
          value={renameValue}
          onChange={(e) => setRenameValue(e.target.value)}
          onBlur={handleRenameSubmit}
          onKeyDown={handleRenameKeyDown}
          className="mt-1 text-xs text-center rounded px-1 outline-none"
          style={{
            width: ICON_SIZE.width - 4,
            backgroundColor: COLORS.surfaceLight,
            color: COLORS.text,
            border: `1px solid ${COLORS.primary}`,
          }}
        />
      ) : (
        <span
          className="mt-1 text-xs text-center leading-tight"
          style={{
            color: COLORS.text,
            width: ICON_SIZE.width - 4,
            display: '-webkit-box',
            WebkitLineClamp: 2,
            WebkitBoxOrient: 'vertical',
            overflow: 'hidden',
            textOverflow: 'ellipsis',
            wordBreak: 'break-word',
            textShadow: '0 1px 3px rgba(0,0,0,0.8)',
          }}
        >
          {entry.name}
        </span>
      )}
    </div>
  );
}
