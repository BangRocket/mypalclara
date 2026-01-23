import { useState } from "react";
import "./App.css";

function App() {
  const [count, setCount] = useState(0);

  return (
    <main className="container">
      <h1>MyPalClara Desktop</h1>
      <p>Clara's collaborative knowledge workspace</p>

      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          Clicked {count} times
        </button>
        <p>React is working correctly.</p>
      </div>

      <p className="read-the-docs">
        Phase 1: Foundation scaffold complete
      </p>
    </main>
  );
}

export default App;
