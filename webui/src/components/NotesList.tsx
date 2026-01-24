import { useNotes } from '../hooks';
import { useUiStore } from '../stores';

export function NotesList() {
  const selectedFolderId = useUiStore((state) => state.selectedFolderId);
  const selectedNoteId = useUiStore((state) => state.selectedNoteId);
  const selectNote = useUiStore((state) => state.selectNote);

  const { data: notes, isLoading, error } = useNotes(selectedFolderId);

  if (isLoading) {
    return <div className="p-2 text-sm text-gray-500">Loading notes...</div>;
  }

  if (error) {
    return <div className="p-2 text-sm text-red-500">Error loading notes</div>;
  }

  if (!notes || notes.length === 0) {
    return (
      <div className="p-4 text-sm text-gray-500 text-center">
        No notes yet.
        <br />
        Click "+ Note" to create one.
      </div>
    );
  }

  return (
    <div className="py-1">
      {notes.map((note) => {
        const isSelected = selectedNoteId === note.id;
        const preview = note.content.slice(0, 60).replace(/[#*_`]/g, '').trim() || 'No content';

        return (
          <div
            key={note.id}
            className={`px-3 py-2 cursor-pointer border-b border-gray-100 ${
              isSelected ? 'bg-blue-50' : 'hover:bg-gray-50'
            }`}
            onClick={() => selectNote(note.id)}
          >
            <div className="text-sm font-medium truncate">{note.title}</div>
            <div className="text-xs text-gray-500 truncate">{preview}</div>
            <div className="text-xs text-gray-400 mt-1">
              {new Date(note.updated_at).toLocaleDateString()}
            </div>
          </div>
        );
      })}
    </div>
  );
}
