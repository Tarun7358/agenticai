import { useState, useEffect } from 'react';
import { Heart, MessageCircle, Users, TrendingUp, Clock, ExternalLink } from 'lucide-react';
import { getInstagramProfile, getInstagramPosts, getInstagramTrend, getInstagramBestTimes } from './api';
import { LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer } from 'recharts';

export default function InstagramPage() {
  const [profile, setProfile] = useState<any>(null);
  const [posts, setPosts] = useState<any[]>([]);
  const [trend, setTrend] = useState<any[]>([]);
  const [bestTimes, setBestTimes] = useState<any[]>([]);
  const [tab, setTab] = useState<'overview' | 'posts' | 'analytics'>('overview');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    setLoading(true);
    Promise.all([
      getInstagramProfile(),
      getInstagramPosts(12),
      getInstagramTrend(),
      getInstagramBestTimes(),
    ]).then(([p, po, t, bt]) => {
      if (p.status === 'ok') setProfile(p.data);
      else setError(p.message || 'Not connected');
      if (po.status === 'ok') setPosts(po.posts || []);
      if (t.history) setTrend(t.history);
      if (bt.status === 'ok') setBestTimes(bt.best_times || []);
    }).catch(() => setError('Backend offline')).finally(() => setLoading(false));
  }, []);

  if (loading) return <div className="page"><div className="empty-state"><div className="spinner" /><p>Loading Instagram data...</p></div></div>;

  if (error) return (
    <div className="page">
      <div className="card" style={{ borderColor: 'rgba(248,113,113,0.3)' }}>
        <div style={{ color: 'var(--danger)', fontSize: 14 }}>⚠️ {error}</div>
        <p style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 8 }}>
          Add your Instagram credentials to <code>backend/.env</code> and restart AURA.
        </p>
      </div>
    </div>
  );

  const maxEngagement = Math.max(...posts.map((p) => p.engagement_rate || 0), 1);

  return (
    <div className="page">
      {/* Profile header */}
      {profile && (
        <div className="card" style={{ background: 'linear-gradient(135deg, rgba(110,231,247,0.06), rgba(167,139,250,0.06))' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 20 }}>
            <div style={{
              width: 64, height: 64, borderRadius: '50%',
              background: 'linear-gradient(135deg, var(--accent), var(--accent-2))',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              fontSize: 24, fontWeight: 800, color: '#000'
            }}>
              {profile.username?.[0]?.toUpperCase()}
            </div>
            <div>
              <div style={{ fontFamily: 'Space Grotesk', fontSize: 18, fontWeight: 700 }}>@{profile.username}</div>
              <div style={{ color: 'var(--text-secondary)', fontSize: 13 }}>{profile.full_name}</div>
              <div style={{ color: 'var(--text-muted)', fontSize: 12, marginTop: 4 }}>{profile.biography?.slice(0, 80)}</div>
            </div>
            <div style={{ marginLeft: 'auto', display: 'flex', gap: 24 }}>
              {[
                { label: 'Followers', value: profile.followers?.toLocaleString(), icon: <Users size={14} /> },
                { label: 'Following', value: profile.followees?.toLocaleString(), icon: <Users size={14} /> },
                { label: 'Posts', value: profile.mediacount, icon: <TrendingUp size={14} /> },
              ].map((s) => (
                <div key={s.label} style={{ textAlign: 'center' }}>
                  <div style={{ fontSize: 20, fontWeight: 700, fontFamily: 'Space Grotesk' }}>{s.value}</div>
                  <div style={{ fontSize: 11, color: 'var(--text-muted)' }}>{s.label}</div>
                </div>
              ))}
            </div>
          </div>
        </div>
      )}

      {/* Tabs */}
      <div className="tabs">
        {(['overview', 'posts', 'analytics'] as const).map((t) => (
          <button key={t} className={`tab ${tab === t ? 'active' : ''}`} onClick={() => setTab(t)}>
            {t.charAt(0).toUpperCase() + t.slice(1)}
          </button>
        ))}
      </div>

      {tab === 'overview' && (
        <>
          {/* Follower trend chart */}
          {trend.length > 1 && (
            <div className="card">
              <div className="card-header">
                <TrendingUp size={16} color="var(--accent)" />
                <span className="card-title">Follower Trend</span>
              </div>
              <ResponsiveContainer width="100%" height={180}>
                <LineChart data={trend}>
                  <XAxis dataKey="fetched_at" hide />
                  <YAxis domain={['auto', 'auto']} hide />
                  <Tooltip
                    contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
                    labelFormatter={(v) => v ? new Date(v as string).toLocaleDateString() : ''}
                  />
                  <Line type="monotone" dataKey="followers" stroke="var(--accent)" strokeWidth={2} dot={false} />
                </LineChart>
              </ResponsiveContainer>
            </div>
          )}

          {/* Best times */}
          {bestTimes.length > 0 && (
            <div className="card">
              <div className="card-header">
                <Clock size={16} color="var(--accent-2)" />
                <span className="card-title">Best Times to Post</span>
              </div>
              <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
                {bestTimes.map((t: any, i: number) => (
                  <div key={t.hour} style={{
                    padding: '8px 14px', borderRadius: 'var(--radius-sm)',
                    background: i === 0 ? 'var(--accent-glow)' : 'var(--bg-surface)',
                    border: `1px solid ${i === 0 ? 'var(--border-bright)' : 'var(--border)'}`,
                    fontSize: 13,
                  }}>
                    <span style={{ color: i === 0 ? 'var(--accent)' : 'var(--text-primary)', fontWeight: 600 }}>
                      {t.hour}:00
                    </span>
                    <span style={{ color: 'var(--text-muted)', fontSize: 11, marginLeft: 6 }}>
                      avg {t.avg_engagement} eng
                    </span>
                  </div>
                ))}
              </div>
            </div>
          )}
        </>
      )}

      {tab === 'posts' && (
        <div className="posts-grid">
          {posts.map((p: any) => (
            <div key={p.shortcode} className="post-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="chip">{p.is_video ? '🎥 Video' : '📷 Photo'}</span>
                <a href={p.url} target="_blank" rel="noreferrer" style={{ color: 'var(--text-muted)' }}>
                  <ExternalLink size={12} />
                </a>
              </div>
              <div className="post-caption">{p.caption || 'No caption'}</div>
              <div className="engagement-bar">
                <div className="engagement-fill" style={{ width: `${(p.engagement_rate / maxEngagement) * 100}%` }} />
              </div>
              <div className="post-stats">
                <span className="post-stat"><Heart size={10} /> {p.likes?.toLocaleString()}</span>
                <span className="post-stat"><MessageCircle size={10} /> {p.comments?.toLocaleString()}</span>
                <span style={{ marginLeft: 'auto', color: 'var(--accent)', fontSize: 10 }}>{p.engagement_rate}%</span>
              </div>
              <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>
                {new Date(p.date).toLocaleDateString()}
              </div>
            </div>
          ))}
        </div>
      )}

      {tab === 'analytics' && (
        <div className="card">
          <div className="card-header">
            <TrendingUp size={16} color="var(--accent)" />
            <span className="card-title">Post Performance</span>
          </div>
          <ResponsiveContainer width="100%" height={240}>
            <LineChart data={posts.slice().reverse()}>
              <XAxis dataKey="date" hide />
              <YAxis yAxisId="left" hide />
              <YAxis yAxisId="right" orientation="right" hide />
              <Tooltip
                contentStyle={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, fontSize: 12 }}
              />
              <Line yAxisId="left" type="monotone" dataKey="likes" stroke="var(--accent)" strokeWidth={2} dot={false} name="Likes" />
              <Line yAxisId="right" type="monotone" dataKey="comments" stroke="var(--accent-2)" strokeWidth={2} dot={false} name="Comments" />
            </LineChart>
          </ResponsiveContainer>
        </div>
      )}
    </div>
  );
}
