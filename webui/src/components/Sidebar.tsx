import { FolderTree } from './FolderTree';
import { NotesList } from './NotesList';
import { useCreateNote, useCreateFolder } from '../hooks';
import { useUiStore } from '../stores';

export function Sidebar() {
  const selectedFolderId = useUiStore((state) => state.selectedFolderId);
  const createNote = useCreateNote();
  const createFolder = useCreateFolder();

  const handleNewNote = () => {
    createNote.mutate({
      title: 'Untitled',
      content: '',
      folder_id: selectedFolderId,
    });
  };

  const handleNewFolder = () => {
    const name = prompt('Folder name:');
    if (name) {
      createFolder.mutate({
        name,
        parent_id: selectedFolderId,
      });
    }
  };

  return (
    <div className="h-full flex flex-col">
      {/* Actions */}
      <div className="p-2 border-b border-gray-200 flex gap-1">
        <button
          onClick={handleNewNote}
          className="flex-1 px-2 py-1 text-sm bg-blue-500 text-white rounded hover:bg-blue-600"
          disabled={createNote.isPending}
        >
          + Note
        </button>
        <button
          onClick={handleNewFolder}
          className="px-2 py-1 text-sm bg-gray-100 rounded hover:bg-gray-200"
          disabled={createFolder.isPending}
        >
          + Folder
        </button>
      </div>

      {/* Folder tree */}
      <div className="flex-shrink-0 max-h-48 overflow-auto border-b border-gray-200">
        <FolderTree />
      </div>

      {/* Notes list */}
      <div className="flex-1 overflow-auto">
        <NotesList />
      </div>
    </div>
  );
}
