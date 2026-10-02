import { useState, useEffect } from 'react';
import { LayoutDashboard, MessageSquare, Wifi, ImageIcon, FolderOpen, Settings } from 'lucide-react';
import './index.css';
import ChatPage from './ChatPage';
import NetworkPage from './NetworkPage';
import InstagramPage from './InstagramPage';
import FilesPage from './FilesPage';
import DashboardPage from './DashboardPage';
import { getStatus } from './api';

type Page = 'dashboard' | 'chat' | 'network' | 'instagram' | 'files';

const NAV = [
  { id: 'dashboard' as Page, icon: <LayoutDashboard size={18} />, label: 'Dashboard' },
  { id: 'chat' as Page, icon: <MessageSquare size={18} />, label: 'Chat' },
  { id: 'network' as Page, icon: <Wifi size={18} />, label: 'Network' },
  { id: 'instagram' as Page, icon: <ImageIcon size={18} />, label: 'Instagram' },
  { id: 'files' as Page, icon: <FolderOpen size={18} />, label: 'Files' },
];

const PAGE_TITLES: Record<Page, string> = {
  dashboard: 'Dashboard',
  chat: 'Chat with AURA',
  network: 'Network Monitor',
  instagram: 'Instagram Analytics',
  files: 'File Search',
};

export default function App() {
  const [page, setPage] = useState<Page>('dashboard');
  const [ollamaOnline, setOllamaOnline] = useState<boolean | null>(null);
  const [hasUnknown, setHasUnknown] = useState(false);

  useEffect(() => {
    getStatus().then((s) => {
      setOllamaOnline(s.ollama?.status === 'online');
    }).catch(() => setOllamaOnline(false));
  }, []);

  // Poll for unknown devices
  useEffect(() => {
    const check = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/network/devices');
        const data = await res.json();
        const unknown = (data.devices || []).filter((d: any) => !d.is_trusted);
        setHasUnknown(unknown.length > 0);
      } catch { /* backend offline */ }
    };
    check();
    const interval = setInterval(check, 30000);
    return () => clearInterval(interval);
  }, []);

  return (
    <>
      <div className="glow-bg" />
      <div className="app">
        {/* Sidebar */}
        <aside className="sidebar">
          <div className="sidebar-logo">A</div>
          {NAV.map((n) => (
            <button
              key={n.id}
              className={`sidebar-btn ${page === n.id ? 'active' : ''}`}
              onClick={() => setPage(n.id)}
              title={n.label}
            >
              {n.icon}
              {n.id === 'network' && hasUnknown && <span className="badge" />}
            </button>
          ))}
          <div style={{ marginTop: 'auto' }}>
            <button className="sidebar-btn" title="Settings" onClick={() => alert('Settings coming soon!')}>
              <Settings size={18} />
            </button>
          </div>
        </aside>

        {/* Main */}
        <div className="main">
          {/* Header */}
          <header className="header">
            <div className="header-title">AURA</div>
            <span style={{ color: 'var(--text-muted)', fontSize: 13 }}>
              {PAGE_TITLES[page]}
            </span>
            <div className="header-status">
              <div className={`status-dot ${ollamaOnline ? '' : 'offline'}`} />
              {ollamaOnline === null ? 'Connecting...' : ollamaOnline ? 'AI Online' : 'AI Offline'}
            </div>
          </header>

          {/* Page content */}
          {page === 'dashboard' && <DashboardPage />}
          {page === 'chat' && <ChatPage />}
          {page === 'network' && <NetworkPage />}
          {page === 'instagram' && <InstagramPage />}
          {page === 'files' && <FilesPage />}
        </div>
      </div>
    </>
  );
}
