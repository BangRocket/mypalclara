import { Layout, NoteEditor, QuickSwitcher } from './components';
import { useUiStore } from './stores';
import { commands } from './lib/bindings';
import { save } from '@tauri-apps/plugin-dialog';
import './App.css';

function App() {
  const selectedNoteId = useUiStore((state) => state.selectedNoteId);

  const handleExport = async (noteId: number) => {
    try {
      // Open save dialog
      const filePath = await save({
        defaultPath: 'note.md',
        filters: [{ name: 'Markdown', extensions: ['md'] }],
      });

      if (filePath) {
        const result = await commands.exportNoteToFile(noteId, filePath);
        if (result.status === 'ok') {
          alert(`Note exported to ${result.data}`);
        } else {
          alert(`Export failed: ${result.error}`);
        }
      }
    } catch (error) {
      alert(`Export failed: ${error}`);
    }
  };

  return (
    <>
      {/* Quick Switcher - always rendered, opens with Cmd+P */}
      <QuickSwitcher />

      <Layout>
        {selectedNoteId ? (
          <NoteEditor noteId={selectedNoteId} onExport={handleExport} />
        ) : (
          <div className="flex items-center justify-center h-full text-gray-500">
            <div className="text-center">
              <svg
                className="w-16 h-16 mx-auto mb-4 text-gray-300"
                fill="none"
                stroke="currentColor"
                viewBox="0 0 24 24"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={1}
                  d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
                />
              </svg>
              <p>Select a note from the sidebar</p>
              <p className="text-sm mt-1">or create a new one with "+ Note"</p>
            </div>
          </div>
        )}
      </Layout>
    </>
  );
}

export default App;
