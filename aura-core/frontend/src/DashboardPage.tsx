import { useState, useEffect } from 'react';
import { Wifi, ImageIcon, FolderOpen, Activity, Cpu } from 'lucide-react';
import { getStatus, getNetworkDevices, getEvents } from './api';

export default function DashboardPage() {
  const [status, setStatus] = useState<any>(null);
  const [devices, setDevices] = useState<any[]>([]);
  const [events, setEvents] = useState<any[]>([]);

  useEffect(() => {
    Promise.all([getStatus(), getNetworkDevices(), getEvents(undefined, 10)]).then(([s, n, e]) => {
      setStatus(s);
      setDevices(n.devices || []);
      setEvents(e.events || []);
    });
  }, []);

  const unknown = devices.filter((d) => !d.is_trusted);

  const agentStatus = [
    { name: 'AI Brain (Ollama)', online: status?.ollama?.status === 'online', icon: <Cpu size={14} />, detail: status?.model },
    { name: 'Instagram', online: status?.instagram_configured, icon: <ImageIcon size={14} />, detail: status?.instagram_configured ? 'Connected' : 'Configure in .env' },
    { name: 'Network', online: devices.length > 0, icon: <Wifi size={14} />, detail: `${devices.length} devices` },
    { name: 'File Index', online: (status?.file_index?.indexed_files || 0) > 0, icon: <FolderOpen size={14} />, detail: `${status?.file_index?.indexed_files || 0} files indexed` },
  ];

  return (
    <div className="page">
      {/* Alert for unknown devices */}
      {unknown.length > 0 && (
        <div style={{
          background: 'rgba(251,191,36,0.08)', border: '1px solid rgba(251,191,36,0.3)',
          borderRadius: 'var(--radius-md)', padding: '14px 18px',
          display: 'flex', alignItems: 'center', gap: 10, fontSize: 13,
        }}>
          <Wifi size={16} color="var(--warning)" />
          <span style={{ color: 'var(--warning)', fontWeight: 500 }}>
            ⚠️ {unknown.length} unknown device{unknown.length > 1 ? 's' : ''} on your network.
          </span>
          <span style={{ color: 'var(--text-muted)', fontSize: 12 }}>Go to Network tab to review them.</span>
        </div>
      )}

      {/* Stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(110,231,247,0.1)', color: 'var(--accent)' }}><Wifi size={16} /></div>
          <div className="stat-value">{devices.length}</div>
          <div className="stat-label">Network Devices</div>
          {unknown.length > 0 && <div className="stat-delta down">⚠️ {unknown.length} unknown</div>}
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(167,139,250,0.1)', color: 'var(--accent-2)' }}><FolderOpen size={16} /></div>
          <div className="stat-value">{status?.file_index?.indexed_files || 0}</div>
          <div className="stat-label">Indexed Files</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(251,191,36,0.1)', color: 'var(--warning)' }}><Activity size={16} /></div>
          <div className="stat-value">{events.length}</div>
          <div className="stat-label">Recent Events</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(52,211,153,0.1)', color: 'var(--success)' }}><Cpu size={16} /></div>
          <div className="stat-value">{status?.ollama?.status === 'online' ? 'ON' : 'OFF'}</div>
          <div className="stat-label">AI Status</div>
          <div className={`stat-delta ${status?.ollama?.status === 'online' ? 'up' : 'down'}`}>
            {status?.ollama?.status === 'online' ? '✓ Online' : '✗ Offline'}
          </div>
        </div>
      </div>

      <div className="grid-2">
        {/* Agent Status */}
        <div className="card">
          <div className="card-header">
            <Activity size={16} color="var(--accent)" />
            <span className="card-title">Agent Status</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
            {agentStatus.map((a) => (
              <div key={a.name} style={{
                display: 'flex', alignItems: 'center', gap: 10,
                padding: '10px 12px', borderRadius: 'var(--radius-sm)',
                background: 'var(--bg-surface)', border: '1px solid var(--border)',
              }}>
                <div style={{
                  width: 8, height: 8, borderRadius: '50%',
                  background: a.online ? 'var(--success)' : 'var(--text-muted)',
                  boxShadow: a.online ? '0 0 6px var(--success)' : 'none',
                }} />
                <div style={{ color: 'var(--text-secondary)', flexShrink: 0 }}>{a.icon}</div>
                <span style={{ fontSize: 13, fontWeight: 500 }}>{a.name}</span>
                <span style={{ marginLeft: 'auto', fontSize: 11, color: a.online ? 'var(--success)' : 'var(--text-muted)' }}>
                  {a.detail}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Recent Events */}
        <div className="card">
          <div className="card-header">
            <Activity size={16} color="var(--accent-2)" />
            <span className="card-title">Recent Events</span>
          </div>
          {events.length === 0 ? (
            <div className="empty-state" style={{ padding: '24px' }}>
              <Activity size={24} />
              <p>No events yet. Events appear as agents collect data.</p>
            </div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {events.slice(0, 8).map((e: any) => (
                <div key={e.id} style={{
                  display: 'flex', alignItems: 'center', gap: 8,
                  padding: '8px 0', borderBottom: '1px solid var(--border)',
                  fontSize: 12,
                }}>
                  <span className="chip" style={{ fontSize: 10 }}>{e.agent}</span>
                  <span style={{ color: 'var(--text-secondary)', flex: 1 }}>{e.event_type.replace(/_/g, ' ')}</span>
                  <span style={{ color: 'var(--text-muted)', fontSize: 10 }}>
                    {new Date(e.timestamp).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* Setup guide if things are offline */}
      {status?.ollama?.status !== 'online' && (
        <div className="card" style={{ borderColor: 'rgba(110,231,247,0.2)' }}>
          <div className="card-header">
            <Cpu size={16} color="var(--accent)" />
            <span className="card-title">🚀 Quick Setup</span>
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10, fontSize: 13 }}>
            {[
              { step: '1', cmd: 'winget install ollama.ollama', label: 'Install Ollama' },
              { step: '2', cmd: 'ollama serve', label: 'Start Ollama server' },
              { step: '3', cmd: 'ollama pull mistral', label: 'Download Mistral 7B model (~4GB)' },
              { step: '4', cmd: 'ollama pull nomic-embed-text', label: 'Download embeddings model' },
            ].map((s) => (
              <div key={s.step} style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                <div style={{
                  width: 22, height: 22, borderRadius: '50%',
                  background: 'var(--accent-glow)', border: '1px solid var(--border-bright)',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  fontSize: 11, fontWeight: 700, color: 'var(--accent)', flexShrink: 0,
                }}>{s.step}</div>
                <span style={{ color: 'var(--text-secondary)' }}>{s.label}</span>
                <code style={{
                  marginLeft: 'auto', background: 'rgba(0,0,0,0.4)',
                  padding: '3px 10px', borderRadius: 4, fontSize: 12,
                  color: 'var(--accent)', border: '1px solid var(--border)',
                }}>{s.cmd}</code>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
