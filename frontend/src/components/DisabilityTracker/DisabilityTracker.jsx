import { useState, useEffect, useRef } from 'react'
import './DisabilityTracker.css'

const STATUS_OPTIONS = [
  { value: 'לא הוגש', label: 'לא הוגש', color: 'status-not-submitted' },
  { value: 'ממתין לטיפול', label: 'ממתין לטיפול', color: 'status-pending' },
  { value: 'בתהליך', label: 'בתהליך', color: 'status-in-progress' },
  { value: 'אושר', label: 'אושר ✓', color: 'status-approved' },
  { value: 'נדחה', label: 'נדחה', color: 'status-rejected' },
]

const DOCUMENT_OPTIONS = [
  'אישור זכאות מביטוח לאומי',
  'ספח תעודת זהות',
  'תעודת נכה',
  'אישור רפואי',
  'תעודת לידה',
  'אבחון פסיכולוגי/פסיכיאטרי',
  'טופס בקשה',
  'צילום תעודת זהות',
]

const DEFAULT_ENTRIES = [
  {
    id: '1',
    org: 'ביטוח לאומי',
    benefit: 'קצבת ילד נכה',
    contact: '* 6050',
    documents: [],
    submissionDate: '',
    status: 'לא הוגש',
    notes: 'הורד אישור זכאות דרך האפליקציה',
    appHint: 'app-bituach',
  },
  {
    id: '2',
    org: 'ארנונה (עירייה)',
    benefit: 'הנחה בארנונה',
    contact: 'מחלקת רווחה בעירייה',
    documents: [],
    submissionDate: '',
    status: 'לא הוגש',
    notes: '',
    appHint: null,
  },
  {
    id: '3',
    org: 'חברת חשמל',
    benefit: 'הנחה בתעריף חשמל',
    contact: '*3366',
    documents: [],
    submissionDate: '',
    status: 'לא הוגש',
    notes: '',
    appHint: null,
  },
  {
    id: '4',
    org: 'תאגיד מים',
    benefit: 'הנחה בצריכת מים',
    contact: 'תאגיד המים המקומי',
    documents: [],
    submissionDate: '',
    status: 'לא הוגש',
    notes: '',
    appHint: null,
  },
  {
    id: '5',
    org: 'קופת החולים',
    benefit: 'שירותי התפתחות הילד',
    contact: 'מזכירות רפואית / מחלקת זכויות',
    documents: [],
    submissionDate: '',
    status: 'לא הוגש',
    notes: 'שלח אבחון ואישור זכאות ישירות דרך אפליקציית הקופה',
    appHint: 'app-kupat-holim',
  },
  {
    id: '6',
    org: 'משרד הרישוי',
    benefit: 'תו נכה לרכב',
    contact: 'gov.il — האזור האישי',
    documents: [],
    submissionDate: '',
    status: 'לא הוגש',
    notes: 'עקוב אחר אישור תו הנכה דרך אפליקציית gov.il',
    appHint: 'app-govil',
  },
  {
    id: '7',
    org: 'משרד החינוך',
    benefit: 'שילוב / סיוע חינוכי',
    contact: 'ועדת השמה מקומית',
    documents: [],
    submissionDate: '',
    status: 'לא הוגש',
    notes: '',
    appHint: null,
  },
]

const APP_RESOURCES = [
  {
    id: 'app-bituach',
    name: 'אפליקציית ביטוח לאומי',
    icon: '🏛️',
    description: 'הורד תעודת נכה לארנק הדיגיטלי והפק אישור זכאות לקצבת ילד נכה',
    color: '#4f83cc',
  },
  {
    id: 'app-govil',
    name: 'אפליקציית gov.il',
    icon: '🇮🇱',
    description: 'שלוף ספח ת.ז. ועקוב אחר אישור תו הנכה לרכב',
    color: '#2d7a4f',
  },
  {
    id: 'app-kupat-holim',
    name: 'אפליקציית קופת החולים',
    icon: '🏥',
    description: 'שלח אבחונים לפנייה להתפתחות הילד וסרוק חשבוניות לקבלת החזרים',
    color: '#c0392b',
  },
]

function generateId() {
  return Date.now().toString(36) + Math.random().toString(36).slice(2, 7)
}

function getStatusOption(value) {
  return STATUS_OPTIONS.find((s) => s.value === value) || STATUS_OPTIONS[0]
}

function ProgressBar({ entries }) {
  const approved = entries.filter((e) => e.status === 'אושר').length
  const submitted = entries.filter((e) => ['ממתין לטיפול', 'בתהליך', 'אושר'].includes(e.status)).length
  const pct = entries.length ? Math.round((approved / entries.length) * 100) : 0
  return (
    <div className="dt-progress-wrap">
      <div className="dt-progress-bar">
        <div className="dt-progress-fill" style={{ width: `${pct}%` }} />
      </div>
      <span className="dt-progress-label">
        {approved}/{entries.length} אושרו · {submitted} הוגשו
      </span>
    </div>
  )
}

function StatusBadge({ value, onChange }) {
  const [open, setOpen] = useState(false)
  const opt = getStatusOption(value)
  const ref = useRef(null)

  useEffect(() => {
    if (!open) return
    function handle(e) {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', handle)
    return () => document.removeEventListener('mousedown', handle)
  }, [open])

  return (
    <div className="dt-status-wrap" ref={ref}>
      <button
        className={`dt-status-badge ${opt.color}`}
        onClick={() => setOpen((o) => !o)}
        type="button"
      >
        {opt.label} ▾
      </button>
      {open && (
        <div className="dt-status-dropdown">
          {STATUS_OPTIONS.map((s) => (
            <button
              key={s.value}
              className={`dt-status-option ${s.color}`}
              onClick={() => { onChange(s.value); setOpen(false) }}
              type="button"
            >
              {s.label}
            </button>
          ))}
        </div>
      )}
    </div>
  )
}

function DocumentTags({ docs, onAdd, onRemove }) {
  const [showPicker, setShowPicker] = useState(false)
  const [custom, setCustom] = useState('')
  const available = DOCUMENT_OPTIONS.filter((d) => !docs.includes(d))

  function addDoc(doc) {
    if (doc && !docs.includes(doc)) onAdd(doc)
    setShowPicker(false)
    setCustom('')
  }

  return (
    <div className="dt-docs-wrap">
      <div className="dt-doc-tags">
        {docs.map((d) => (
          <span key={d} className="dt-doc-tag">
            {d}
            <button type="button" onClick={() => onRemove(d)} className="dt-doc-remove">×</button>
          </span>
        ))}
        <button type="button" className="dt-doc-add" onClick={() => setShowPicker((p) => !p)}>
          + מסמך
        </button>
      </div>
      {showPicker && (
        <div className="dt-doc-picker">
          {available.map((d) => (
            <button key={d} type="button" className="dt-doc-pick-item" onClick={() => addDoc(d)}>
              {d}
            </button>
          ))}
          <div className="dt-doc-custom-row">
            <input
              className="dt-doc-custom-input"
              value={custom}
              onChange={(e) => setCustom(e.target.value)}
              placeholder="מסמך מותאם אישית..."
              onKeyDown={(e) => e.key === 'Enter' && addDoc(custom.trim())}
            />
            <button type="button" className="dt-doc-pick-item" onClick={() => addDoc(custom.trim())}>
              הוסף
            </button>
          </div>
        </div>
      )}
    </div>
  )
}

function EntryCard({ entry, onChange, onDelete, highlight }) {
  const [expanded, setExpanded] = useState(false)
  const opt = getStatusOption(entry.status)

  return (
    <div className={`dt-card ${highlight ? 'dt-card-new' : ''}`}>
      <div className="dt-card-header" onClick={() => setExpanded((e) => !e)}>
        <div className="dt-card-title-row">
          <span className="dt-card-org">{entry.org}</span>
          <StatusBadge
            value={entry.status}
            onChange={(v) => onChange({ ...entry, status: v })}
          />
        </div>
        <div className="dt-card-meta">
          <span className="dt-card-benefit">🎯 {entry.benefit}</span>
          {entry.submissionDate && (
            <span className="dt-card-date">📅 {entry.submissionDate}</span>
          )}
        </div>
        <span className="dt-card-chevron">{expanded ? '▲' : '▼'}</span>
      </div>

      {expanded && (
        <div className="dt-card-body">
          <label className="dt-field-label">שם הגוף</label>
          <input
            className="dt-input"
            value={entry.org}
            onChange={(e) => onChange({ ...entry, org: e.target.value })}
          />

          <label className="dt-field-label">הטבה מבוקשת</label>
          <input
            className="dt-input"
            value={entry.benefit}
            onChange={(e) => onChange({ ...entry, benefit: e.target.value })}
          />

          <label className="dt-field-label">תאריך הגשה</label>
          <input
            className="dt-input"
            type="date"
            value={entry.submissionDate}
            onChange={(e) => onChange({ ...entry, submissionDate: e.target.value })}
          />

          <label className="dt-field-label">מסמכים שנשלחו</label>
          <DocumentTags
            docs={entry.documents}
            onAdd={(d) => onChange({ ...entry, documents: [...entry.documents, d] })}
            onRemove={(d) => onChange({ ...entry, documents: entry.documents.filter((x) => x !== d) })}
          />

          <label className="dt-field-label">גורם קשר</label>
          <input
            className="dt-input"
            value={entry.contact}
            onChange={(e) => onChange({ ...entry, contact: e.target.value })}
          />

          <label className="dt-field-label">הערות</label>
          <textarea
            className="dt-input dt-textarea"
            value={entry.notes}
            onChange={(e) => onChange({ ...entry, notes: e.target.value })}
            rows={2}
          />

          <button
            type="button"
            className="dt-delete-btn"
            onClick={() => onDelete(entry.id)}
          >
            מחק רשומה
          </button>
        </div>
      )}
    </div>
  )
}

function ResourcesSection() {
  return (
    <div className="dt-resources">
      <h3 className="dt-section-title">🔧 כלים מומלצים</h3>
      <div className="dt-app-list">
        {APP_RESOURCES.map((app) => (
          <div key={app.id} className="dt-app-card" style={{ borderColor: app.color + '44' }}>
            <span className="dt-app-icon">{app.icon}</span>
            <div>
              <div className="dt-app-name" style={{ color: app.color }}>{app.name}</div>
              <div className="dt-app-desc">{app.description}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="dt-kol-zchut">
        <span className="dt-kz-icon">📚</span>
        <div>
          <div className="dt-kz-title">כל זכות — מאגר זכויות לרצף האוטיזם</div>
          <div className="dt-kz-desc">
            היכנס לאתר כל-זכות.org, חפש "זכויות ילדים על רצף האוטיזם" ובחר "הוסף למסך הבית" — תאייקון שמתנהג כאפליקציה ומתעדכן אוטומטית.
          </div>
        </div>
      </div>

      <div className="dt-privacy-warning">
        <span>⚠️</span>
        <span>אזהרת פרטיות: אל תזין סיסמאות ממשלתיות, פרטי קופת חולים או מידע רפואי של הילד בפלטפורמות שאינן רשמיות.</span>
      </div>
    </div>
  )
}

export default function DisabilityTracker({ onBack }) {
  const [entries, setEntries] = useState(() => {
    try {
      const saved = localStorage.getItem('disability-tracker-entries')
      return saved ? JSON.parse(saved) : DEFAULT_ENTRIES
    } catch {
      return DEFAULT_ENTRIES
    }
  })
  const [newId, setNewId] = useState(null)
  const [tab, setTab] = useState('tracker') // tracker | resources

  useEffect(() => {
    localStorage.setItem('disability-tracker-entries', JSON.stringify(entries))
  }, [entries])

  function updateEntry(updated) {
    setEntries((prev) => prev.map((e) => (e.id === updated.id ? updated : e)))
  }

  function deleteEntry(id) {
    setEntries((prev) => prev.filter((e) => e.id !== id))
  }

  function addEntry() {
    const id = generateId()
    const entry = {
      id,
      org: 'גוף חדש',
      benefit: '',
      contact: '',
      documents: [],
      submissionDate: '',
      status: 'לא הוגש',
      notes: '',
      appHint: null,
    }
    setEntries((prev) => [...prev, entry])
    setNewId(id)
    setTimeout(() => setNewId(null), 2000)
  }

  function resetToDefaults() {
    if (window.confirm('האם לאפס את כל הרשומות לברירת המחדל? פעולה זו תמחק את כל השינויים.')) {
      setEntries(DEFAULT_ENTRIES)
    }
  }

  return (
    <div className="dt-root" dir="rtl">
      <div className="dt-header">
        <button className="dt-back-btn" onClick={onBack} type="button">
          ← חזרה
        </button>
        <div className="dt-header-text">
          <h1 className="dt-title">מעקב זכויות נכות</h1>
          <p className="dt-subtitle">ניהול ומעקב בירוקרטי מרכזי</p>
        </div>
      </div>

      <ProgressBar entries={entries} />

      <div className="dt-tabs">
        <button
          className={`dt-tab ${tab === 'tracker' ? 'dt-tab-active' : ''}`}
          onClick={() => setTab('tracker')}
          type="button"
        >
          📋 מעקב בקשות
        </button>
        <button
          className={`dt-tab ${tab === 'resources' ? 'dt-tab-active' : ''}`}
          onClick={() => setTab('resources')}
          type="button"
        >
          🔧 כלים ומשאבים
        </button>
      </div>

      {tab === 'tracker' && (
        <div className="dt-tracker-section">
          <div className="dt-legend">
            {STATUS_OPTIONS.map((s) => (
              <span key={s.value} className={`dt-legend-item ${s.color}`}>{s.label}</span>
            ))}
          </div>

          <div className="dt-entries">
            {entries.map((entry) => (
              <EntryCard
                key={entry.id}
                entry={entry}
                onChange={updateEntry}
                onDelete={deleteEntry}
                highlight={entry.id === newId}
              />
            ))}
          </div>

          <div className="dt-actions">
            <button type="button" className="dt-add-btn" onClick={addEntry}>
              + הוסף גוף חדש
            </button>
            <button type="button" className="dt-reset-btn" onClick={resetToDefaults}>
              אפס לברירת מחדל
            </button>
          </div>
        </div>
      )}

      {tab === 'resources' && <ResourcesSection />}
    </div>
  )
}
