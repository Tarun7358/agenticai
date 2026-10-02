import { useState } from 'react';
import { Search, FolderOpen, FileText, Loader } from 'lucide-react';
import { searchFiles } from './api';

interface SearchResult {
  filename: string;
  filepath: string;
  content_snippet: string;
  relevance: number;
  modified: string;
}

export default function FilesPage() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const search = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setSearched(true);
    const data = await searchFiles(query.trim(), 8);
    setResults(data.results || []);
    setLoading(false);
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') search();
  };

  const ext = (filepath: string) => filepath.split('.').pop()?.toUpperCase() || 'FILE';
  const extColor: Record<string, string> = {
    PDF: 'var(--danger)', MD: 'var(--accent)', PY: 'var(--warning)',
    TS: 'var(--accent-2)', JS: 'var(--accent-3)', DOCX: 'var(--accent)',
    TXT: 'var(--text-secondary)',
  };

  return (
    <div className="page">
      <div className="card">
        <div className="card-header">
          <FolderOpen size={16} color="var(--accent-2)" />
          <span className="card-title">File Search</span>
          <span className="card-subtitle">Semantic search across your documents</span>
        </div>
        <div style={{ display: 'flex', gap: 10 }}>
          <div style={{ flex: 1, position: 'relative' }}>
            <Search size={14} style={{ position: 'absolute', left: 12, top: '50%', transform: 'translateY(-50%)', color: 'var(--text-muted)' }} />
            <input
              style={{
                width: '100%', padding: '10px 12px 10px 36px',
                background: 'var(--bg-surface)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)', color: 'var(--text-primary)',
                fontSize: 14, outline: 'none', fontFamily: 'Inter',
              }}
              placeholder='Try: "my resume", "project notes", "budget spreadsheet"...'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={handleKey}
              onFocus={(e) => e.target.style.borderColor = 'var(--border-bright)'}
              onBlur={(e) => e.target.style.borderColor = 'var(--border)'}
            />
          </div>
          <button className="btn primary" onClick={search} disabled={loading}>
            {loading ? <Loader size={14} className="spin" /> : <Search size={14} />}
            Search
          </button>
        </div>

        <div style={{ marginTop: 12, fontSize: 12, color: 'var(--text-muted)' }}>
          💡 AURA searches your files using AI — it understands meaning, not just keywords.
          Configure folders in <code style={{ background: 'rgba(0,0,0,0.3)', padding: '1px 6px', borderRadius: 4 }}>WATCHED_FOLDERS</code> in your .env file.
        </div>
      </div>

      {loading && (
        <div className="empty-state">
          <div className="spinner" />
          <p>Searching your files...</p>
        </div>
      )}

      {!loading && searched && results.length === 0 && (
        <div className="empty-state">
          <FileText size={32} />
          <p>No files found for "{query}"</p>
          <p style={{ fontSize: 12 }}>Make sure your folders are indexed and Ollama is running.</p>
        </div>
      )}

      {!loading && results.length > 0 && (
        <div className="card">
          <div className="card-header">
            <Search size={14} color="var(--accent)" />
            <span className="card-title">{results.length} results for "{query}"</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {results.map((r, i) => (
              <div key={i} className="search-result">
                <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{
                    fontSize: 10, padding: '2px 6px', borderRadius: 4, fontWeight: 600,
                    background: 'rgba(0,0,0,0.3)',
                    color: extColor[ext(r.filepath)] || 'var(--text-secondary)',
                  }}>
                    {ext(r.filepath)}
                  </span>
                  <span className="search-result-name">{r.filename}</span>
                  <span style={{
                    marginLeft: 'auto', fontSize: 11,
                    color: r.relevance > 0.8 ? 'var(--success)' : r.relevance > 0.6 ? 'var(--warning)' : 'var(--text-muted)',
                  }}>
                    {Math.round(r.relevance * 100)}% match
                  </span>
                </div>
                <div className="search-result-snippet">{r.content_snippet}</div>
                <div className="search-result-meta">
                  {r.filepath} · Modified {r.modified ? new Date(r.modified).toLocaleDateString() : 'unknown'}
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
