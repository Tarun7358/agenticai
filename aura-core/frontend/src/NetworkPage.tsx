import { useState, useEffect } from 'react';
import { Wifi, RefreshCw, Shield, ShieldOff, Monitor, Smartphone } from 'lucide-react';
import { getNetworkDevices, triggerNetworkScan, trustDevice } from './api';

interface Device {
  id: number;
  mac_address: string;
  ip_address: string;
  hostname: string;
  vendor: string;
  first_seen: string;
  last_seen: string;
  is_trusted: number;
  alias: string;
}

function deviceIcon(vendor: string) {
  const v = vendor.toLowerCase();
  if (v.includes('apple') || v.includes('samsung') || v.includes('xiaomi') || v.includes('oneplus')) return <Smartphone size={14} />;
  if (v.includes('intel') || v.includes('vmware')) return <Monitor size={14} />;
  return <Wifi size={14} />;
}

export default function NetworkPage() {
  const [devices, setDevices] = useState<Device[]>([]);
  const [scanning, setScanning] = useState(false);
  const [lastScan, setLastScan] = useState<string>('');

  const load = async () => {
    const data = await getNetworkDevices();
    setDevices(data.devices || []);
  };

  useEffect(() => { load(); }, []);

  const scan = async () => {
    setScanning(true);
    const result = await triggerNetworkScan();
    setLastScan(new Date().toLocaleTimeString());
    if (result.devices) setDevices(result.devices);
    await load();
    setScanning(false);
  };

  const trust = async (mac: string) => {
    const alias = prompt('Give this device a name (optional):') || '';
    await trustDevice(mac, alias);
    await load();
  };

  const trusted = devices.filter((d) => d.is_trusted);
  const unknown = devices.filter((d) => !d.is_trusted);

  return (
    <div className="page">
      {/* Header stats */}
      <div className="stats-grid">
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(110,231,247,0.1)', color: 'var(--accent)' }}><Wifi size={16} /></div>
          <div className="stat-value">{devices.length}</div>
          <div className="stat-label">Total Devices</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(52,211,153,0.1)', color: 'var(--success)' }}><Shield size={16} /></div>
          <div className="stat-value">{trusted.length}</div>
          <div className="stat-label">Trusted</div>
        </div>
        <div className="stat-card">
          <div className="stat-icon" style={{ background: 'rgba(251,191,36,0.1)', color: 'var(--warning)' }}><ShieldOff size={16} /></div>
          <div className="stat-value">{unknown.length}</div>
          <div className="stat-label">Unknown</div>
        </div>
      </div>

      {/* Scan button */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button className="btn primary" onClick={scan} disabled={scanning}>
          <RefreshCw size={14} className={scanning ? 'spin' : ''} />
          {scanning ? 'Scanning...' : 'Scan Now'}
        </button>
        {lastScan && <span style={{ fontSize: 12, color: 'var(--text-muted)' }}>Last scan: {lastScan}</span>}
      </div>

      {/* Unknown devices */}
      {unknown.length > 0 && (
        <div className="card" style={{ borderColor: 'rgba(251,191,36,0.3)' }}>
          <div className="card-header">
            <ShieldOff size={16} color="var(--warning)" />
            <span className="card-title">⚠️ Unknown Devices</span>
            <span className="card-subtitle">{unknown.length} unrecognized</span>
          </div>
          <div className="device-list">
            {unknown.map((d) => (
              <div key={d.mac_address} className="device-row">
                <div className="device-dot unknown" />
                <div style={{ color: 'var(--warning)', flexShrink: 0 }}>{deviceIcon(d.vendor)}</div>
                <div className="device-info">
                  <div className="device-name">{d.alias || d.hostname || d.vendor || 'Unknown Device'}</div>
                  <div className="device-meta">{d.ip_address} · {d.mac_address} · {d.vendor || 'Unknown vendor'}</div>
                </div>
                <span className="device-badge unknown">Unknown</span>
                <button className="btn" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => trust(d.mac_address)}>
                  <Shield size={11} /> Trust
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trusted devices */}
      <div className="card">
        <div className="card-header">
          <Shield size={16} color="var(--success)" />
          <span className="card-title">Trusted Devices</span>
          <span className="card-subtitle">{trusted.length} devices</span>
        </div>
        {trusted.length === 0 ? (
          <div className="empty-state">
            <Shield size={32} />
            <p>No trusted devices yet. Scan your network and trust your devices.</p>
          </div>
        ) : (
          <div className="device-list">
            {trusted.map((d) => (
              <div key={d.mac_address} className="device-row">
                <div className="device-dot trusted" />
                <div style={{ color: 'var(--success)', flexShrink: 0 }}>{deviceIcon(d.vendor)}</div>
                <div className="device-info">
                  <div className="device-name">{d.alias || d.hostname || d.vendor || 'Device'}</div>
                  <div className="device-meta">{d.ip_address} · {d.mac_address}</div>
                </div>
                <span className="device-badge trusted">Trusted</span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
