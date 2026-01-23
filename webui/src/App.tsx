import { useEffect, useState } from "react";
import { commands, type Note } from "./lib/bindings";
import "./App.css";

function App() {
  const [notes, setNotes] = useState<Note[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Fetch notes on mount
  useEffect(() => {
    loadNotes();
  }, []);

  async function loadNotes() {
    try {
      setLoading(true);
      setError(null);
      const result = await commands.listNotes(null);
      if (result.status === "ok") {
        setNotes(result.data);
      } else {
        setError(result.error);
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setLoading(false);
    }
  }

  async function handleCreateNote() {
    try {
      const result = await commands.createNote({
        title: `New Note ${notes.length + 1}`,
        content: "# Hello\n\nThis note was created from React!",
        folder_id: 1, // Default folder
      });
      if (result.status === "ok") {
        setNotes([result.data, ...notes]);
      } else {
        setError(result.error);
      }
    } catch (e) {
      setError(String(e));
    }
  }

  return (
    <main className="container">
      <h1>MyPalClara Desktop</h1>
      <p>Clara's collaborative knowledge workspace</p>

      <div className="card">
        <button onClick={handleCreateNote}>Create Note</button>
        <button onClick={loadNotes} style={{ marginLeft: "0.5rem" }}>
          Refresh
        </button>
      </div>

      {loading && <p>Loading notes...</p>}
      {error && <p className="error">Error: {error}</p>}

      <div className="notes-list">
        <h2>Notes ({notes.length})</h2>
        {notes.length === 0 && !loading && (
          <p>No notes yet. Click "Create Note" to add one.</p>
        )}
        {notes.map((note) => (
          <div key={note.id} className="note-item">
            <strong>{note.title}</strong>
            <span className="note-meta">
              {note.author} - {new Date(note.updated_at).toLocaleDateString()}
            </span>
          </div>
        ))}
      </div>

      <p className="read-the-docs">Phase 1: Foundation complete</p>
    </main>
  );
}

export default App;
