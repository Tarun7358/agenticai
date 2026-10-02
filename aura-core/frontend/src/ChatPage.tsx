import { useState, useEffect, useRef } from 'react';
import { streamChat, getStatus } from './api';
import { Send, Bot, User, Zap, AlertCircle } from 'lucide-react';

interface Message {
  role: 'user' | 'assistant';
  content: string;
  loading?: boolean;
}

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([
    {
      role: 'assistant',
      content: "Hey! I'm AURA 👋 I'm your personal AI, running right here on your laptop. I can help you with your Instagram analytics, check who's on your network, search your files, and answer anything. What do you need?",
    },
  ]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [sessionId] = useState(() => crypto.randomUUID());
  const [ollamaOnline, setOllamaOnline] = useState<boolean | null>(null);
  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    getStatus().then((s) => {
      setOllamaOnline(s.ollama?.status === 'online');
    }).catch(() => setOllamaOnline(false));
  }, []);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const send = async () => {
    if (!input.trim() || loading) return;
    const text = input.trim();
    setInput('');
    setMessages((m) => [...m, { role: 'user', content: text }]);
    setLoading(true);

    // Add loading assistant message
    setMessages((m) => [...m, { role: 'assistant', content: '', loading: true }]);

    try {
      let fullResponse = '';
      for await (const token of streamChat(text, sessionId)) {
        if (token.length < 100) {  // skip the session id line
          fullResponse += token;
          setMessages((m) => {
            const updated = [...m];
            updated[updated.length - 1] = { role: 'assistant', content: fullResponse, loading: true };
            return updated;
          });
        }
      }
      setMessages((m) => {
        const updated = [...m];
        updated[updated.length - 1] = { role: 'assistant', content: fullResponse, loading: false };
        return updated;
      });
    } catch {
      setMessages((m) => {
        const updated = [...m];
        updated[updated.length - 1] = {
          role: 'assistant',
          content: '⚠️ Failed to reach AURA backend. Make sure it\'s running.',
          loading: false,
        };
        return updated;
      });
    } finally {
      setLoading(false);
    }
  };

  const handleKey = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      send();
    }
  };

  const quickPrompts = [
    'What\'s my Instagram engagement rate?',
    'Who\'s connected to my network?',
    'Find files about my projects',
    'Give me a daily briefing',
  ];

  return (
    <div className="chat-page">
      {ollamaOnline === false && (
        <div style={{
          background: 'rgba(248,113,113,0.1)', border: '1px solid rgba(248,113,113,0.3)',
          borderRadius: 'var(--radius-sm)', padding: '10px 16px', margin: '16px 28px 0',
          display: 'flex', alignItems: 'center', gap: 8, fontSize: 13, color: 'var(--danger)'
        }}>
          <AlertCircle size={14} />
          Ollama is offline. Run <code style={{ background: 'rgba(0,0,0,0.3)', padding: '1px 6px', borderRadius: 4 }}>ollama serve</code> then <code style={{ background: 'rgba(0,0,0,0.3)', padding: '1px 6px', borderRadius: 4 }}>ollama pull mistral</code> in a terminal.
        </div>
      )}

      <div className="chat-messages">
        {messages.length === 1 && (
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 8 }}>
            {quickPrompts.map((p) => (
              <button
                key={p}
                className="btn"
                style={{ fontSize: 12 }}
                onClick={() => { setInput(p); inputRef.current?.focus(); }}
              >
                <Zap size={12} /> {p}
              </button>
            ))}
          </div>
        )}
        {messages.map((msg, i) => (
          <div key={i} className={`msg ${msg.role}`}>
            <div className="msg-avatar">
              {msg.role === 'assistant' ? <Bot size={14} /> : <User size={14} />}
            </div>
            <div className="msg-bubble" style={{ whiteSpace: 'pre-wrap' }}>
              {msg.content || (msg.loading ? '' : '')}
              {msg.loading && <span className="typing-cursor" />}
            </div>
          </div>
        ))}
        <div ref={bottomRef} />
      </div>

      <div className="chat-input-area">
        <textarea
          ref={inputRef}
          className="chat-input"
          placeholder="Ask AURA anything..."
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKey}
          rows={1}
        />
        <button className="send-btn" onClick={send} disabled={loading || !input.trim()}>
          <Send size={16} />
        </button>
      </div>
    </div>
  );
}
