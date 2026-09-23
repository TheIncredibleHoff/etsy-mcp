import { Link, Route, Routes } from "react-router-dom";
import UploadPage from "./pages/UploadPage";
import ResultsPage from "./pages/ResultsPage";

export default function App() {
  return (
    <div className="app">
      <header className="app-header">
        <Link to="/" className="brand">
          ⚾ Swing Analyzer
        </Link>
      </header>
      <main>
        <Routes>
          <Route path="/" element={<UploadPage />} />
          <Route path="/videos/:id" element={<ResultsPage />} />
        </Routes>
      </main>
    </div>
  );
}
