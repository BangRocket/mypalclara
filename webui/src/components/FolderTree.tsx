import { useState } from 'react';
import { useFolders } from '../hooks';
import { useUiStore } from '../stores';
import type { Folder } from '../lib/bindings';

interface FolderItemProps {
  folder: Folder;
  level: number;
}

function FolderItem({ folder, level }: FolderItemProps) {
  const [expanded, setExpanded] = useState(true);
  const selectedFolderId = useUiStore((state) => state.selectedFolderId);
  const selectFolder = useUiStore((state) => state.selectFolder);

  const { data: children } = useFolders(folder.id);
  const hasChildren = children && children.length > 0;

  const isSelected = selectedFolderId === folder.id;

  return (
    <div>
      <div
        className={`flex items-center py-1 px-2 cursor-pointer hover:bg-gray-100 ${
          isSelected ? 'bg-blue-50 text-blue-700' : ''
        }`}
        style={{ paddingLeft: `${level * 12 + 8}px` }}
        onClick={() => selectFolder(folder.id)}
      >
        {/* Expand/collapse toggle */}
        <button
          onClick={(e) => {
            e.stopPropagation();
            setExpanded(!expanded);
          }}
          className="w-4 h-4 mr-1 flex items-center justify-center text-gray-400 hover:text-gray-600"
        >
          {hasChildren && (
            <svg
              className={`w-3 h-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
              fill="currentColor"
              viewBox="0 0 20 20"
            >
              <path
                fillRule="evenodd"
                d="M7.293 14.707a1 1 0 010-1.414L10.586 10 7.293 6.707a1 1 0 011.414-1.414l4 4a1 1 0 010 1.414l-4 4a1 1 0 01-1.414 0z"
                clipRule="evenodd"
              />
            </svg>
          )}
        </button>

        {/* Folder icon */}
        <svg className="w-4 h-4 mr-2 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M2 6a2 2 0 012-2h5l2 2h5a2 2 0 012 2v6a2 2 0 01-2 2H4a2 2 0 01-2-2V6z" />
        </svg>

        <span className="text-sm truncate">{folder.name}</span>
      </div>

      {/* Children */}
      {expanded && hasChildren && (
        <div>
          {children.map((child) => (
            <FolderItem key={child.id} folder={child} level={level + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function FolderTree() {
  const { data: folders, isLoading, error } = useFolders(null);
  const selectedFolderId = useUiStore((state) => state.selectedFolderId);
  const selectFolder = useUiStore((state) => state.selectFolder);

  if (isLoading) {
    return <div className="p-2 text-sm text-gray-500">Loading folders...</div>;
  }

  if (error) {
    return <div className="p-2 text-sm text-red-500">Error loading folders</div>;
  }

  // Filter to root-level folders only (parent_id is null)
  const rootFolders = folders?.filter((f) => f.parent_id === null) ?? [];

  return (
    <div className="py-1">
      {/* All Notes option */}
      <div
        className={`flex items-center py-1 px-2 cursor-pointer hover:bg-gray-100 ${
          selectedFolderId === null ? 'bg-blue-50 text-blue-700' : ''
        }`}
        onClick={() => selectFolder(null)}
      >
        <span className="w-4 h-4 mr-1" /> {/* Spacer for alignment */}
        <svg className="w-4 h-4 mr-2 text-gray-500" fill="currentColor" viewBox="0 0 20 20">
          <path d="M7 3a1 1 0 000 2h6a1 1 0 100-2H7zM4 7a1 1 0 011-1h10a1 1 0 110 2H5a1 1 0 01-1-1zM2 11a2 2 0 012-2h12a2 2 0 012 2v4a2 2 0 01-2 2H4a2 2 0 01-2-2v-4z" />
        </svg>
        <span className="text-sm">All Notes</span>
      </div>

      {/* Folder tree */}
      {rootFolders.map((folder) => (
        <FolderItem key={folder.id} folder={folder} level={0} />
      ))}
    </div>
  );
}
