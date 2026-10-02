const host = (typeof window !== 'undefined' && window.location.hostname) ? window.location.hostname : '127.0.0.1';
const API = `http://${host}:8000`;

export async function getStatus() {
  const res = await fetch(`${API}/api/status`);
  return res.json();
}

export async function getNetworkDevices() {
  const res = await fetch(`${API}/api/network/devices`);
  return res.json();
}

export async function triggerNetworkScan() {
  const res = await fetch(`${API}/api/network/scan/now`);
  return res.json();
}

export async function trustDevice(mac: string, alias: string) {
  const res = await fetch(`${API}/api/network/trust`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ mac, alias }),
  });
  return res.json();
}

export async function getInstagramProfile() {
  const res = await fetch(`${API}/api/instagram/profile`);
  return res.json();
}

export async function getInstagramPosts(limit = 12) {
  const res = await fetch(`${API}/api/instagram/posts?limit=${limit}`);
  return res.json();
}

export async function getInstagramTrend() {
  const res = await fetch(`${API}/api/instagram/trend`);
  return res.json();
}

export async function getInstagramBestTimes() {
  const res = await fetch(`${API}/api/instagram/best-times`);
  return res.json();
}

export async function searchFiles(query: string, limit = 5) {
  const res = await fetch(`${API}/api/files/search`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ query, limit }),
  });
  return res.json();
}

export async function getFileStats() {
  const res = await fetch(`${API}/api/files/stats`);
  return res.json();
}

export async function getEvents(agent?: string, limit = 30) {
  const url = agent
    ? `${API}/api/events?agent=${agent}&limit=${limit}`
    : `${API}/api/events?limit=${limit}`;
  const res = await fetch(url);
  return res.json();
}

export async function* streamChat(message: string, sessionId: string) {
  const res = await fetch(`${API}/api/chat/stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ message, session_id: sessionId }),
  });

  const reader = res.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        const data = line.slice(6);
        if (data === '[DONE]') return;
        yield data;
      }
    }
  }
}
