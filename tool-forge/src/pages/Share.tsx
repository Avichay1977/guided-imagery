import { useEffect, useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { matchTool } from '../engine/usage'

/**
 * מה שהגיע משיתוף מאפליקציה אחרת.
 *
 * זו הנקודה שבה תוכן מוואטסאפ (או מכל אפליקציה) נכנס למערכת. אנחנו לא קוראים
 * הודעות ולא מתחברים לחשבון — המשתמש בוחר הודעה, לוחץ "שיתוף", ובוחר אותנו.
 * מה שמגיע לכאן הוא בדיוק מה שהוא בחר להעביר, ולא ביט אחד יותר.
 *
 * ה-service worker כבר תפס את ה-POST ושמר אותו; כאן אנחנו אוספים אותו ומחליטים
 * לאן הוא הולך.
 */

interface SharedPayload {
  at: string
  title: string
  text: string
  url: string
  images: Array<{ mediaType: string; data: string; name: string }>
}

export default function Share() {
  const { tools, archived, record } = useApp()
  const navigate = useNavigate()
  const [payload, setPayload] = useState<SharedPayload | null>(null)
  const [state, setState] = useState<'loading' | 'ready' | 'empty'>('loading')

  useEffect(() => {
    let cancelled = false
    fetch('./__shared__')
      .then((response) => response.json())
      .then((data: SharedPayload | null) => {
        if (cancelled) return
        if (!data || (!data.text && !data.title && data.images.length === 0)) {
          setState('empty')
          return
        }
        setPayload(data)
        setState('ready')
        record({ kind: 'action', message: 'התקבל תוכן משיתוף חיצוני' })
      })
      .catch(() => !cancelled && setState('empty'))
    return () => {
      cancelled = true
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const shelf = tools.filter((tool) => !archived.includes(tool.id))
  const body = [payload?.title, payload?.text, payload?.url].filter(Boolean).join('\n')
  const suggested = body ? matchTool(body, shelf) : null

  const sendTo = (toolId: string) => {
    // הכלי נפתח עם הטקסט מוכן בשדה הראשון; ההרצה נשארת החלטה של המשתמש
    sessionStorage.setItem('toolforge.incoming', body)
    navigate(`/tool/${toolId}`)
  }

  if (state === 'loading') {
    return <p className="text-sm text-panel-400">אוסף את מה ששותף…</p>
  }

  if (state === 'empty') {
    return (
      <section className="device rounded-xl p-6">
        <h1 className="text-lg font-semibold text-white">אין כאן תוכן משותף</h1>
        <p className="mt-2 text-sm leading-relaxed text-panel-400">
          כדי לשלוח לכאן משהו: בוואטסאפ (או בכל אפליקציה) לחצו לחיצה ארוכה על הודעה, בחרו
          "שיתוף", ובחרו את "בונה הכלים". הטקסט או התמונה יגיעו לכאן.
        </p>
        <Link
          to="/"
          className="mt-4 inline-block rounded-lg bg-signal-500 px-4 py-2 text-sm font-semibold text-panel-950"
        >
          חזרה
        </Link>
      </section>
    )
  }

  return (
    <div className="space-y-6">
      <section className="device rounded-xl p-5">
        <h1 className="text-lg font-semibold text-white">התקבל תוכן משיתוף</h1>
        <p className="mt-1 text-xs text-panel-500">
          מה שמוצג כאן הוא כל מה שהגיע. שום דבר אחר לא נקרא ולא נשמר.
        </p>

        {body && (
          <pre className="mt-4 max-h-64 overflow-auto whitespace-pre-wrap rounded-lg border border-panel-700 bg-panel-950 p-3 text-sm leading-relaxed text-panel-200">
            {body}
          </pre>
        )}

        {payload!.images.length > 0 && (
          <ul className="mt-3 grid grid-cols-2 gap-2">
            {payload!.images.map((image, index) => (
              <li key={index} className="rounded-lg border border-panel-700 bg-panel-950 p-2">
                <img
                  src={`data:${image.mediaType};base64,${image.data}`}
                  alt={image.name || 'תמונה משותפת'}
                  className="max-h-40 w-full rounded object-contain"
                />
              </li>
            ))}
          </ul>
        )}
      </section>

      <section>
        <h2 className="mb-3 text-sm font-semibold text-panel-300">לאן זה הולך?</h2>

        {suggested && (
          <button
            type="button"
            onClick={() => sendTo(suggested.id)}
            className="mb-3 w-full rounded-xl border border-signal-600/60 bg-signal-600/10 p-4 text-right transition hover:bg-signal-600/20"
          >
            <div className="flex items-center gap-2">
              <span className="text-2xl" aria-hidden>
                {suggested.icon}
              </span>
              <span className="font-semibold text-white">{suggested.name}</span>
            </div>
            <p className="mt-1 text-xs text-signal-300">נראה שזה שייך לכאן</p>
          </button>
        )}

        <ul className="grid gap-2 sm:grid-cols-2">
          {shelf
            .filter((tool) => tool.id !== suggested?.id)
            .map((tool) => (
              <li key={tool.id}>
                <button
                  type="button"
                  onClick={() => sendTo(tool.id)}
                  className="w-full rounded-xl border border-panel-800 bg-panel-900 p-3 text-right transition hover:border-signal-500"
                >
                  <span className="text-lg" aria-hidden>
                    {tool.icon}
                  </span>{' '}
                  <span className="text-sm text-panel-200">{tool.name}</span>
                </button>
              </li>
            ))}
        </ul>

        <Link
          to={`/build?brief=${encodeURIComponent(body.slice(0, 300))}`}
          className="mt-3 inline-block text-sm text-signal-300 hover:text-signal-400"
        >
          + לבנות כלי חדש מהתוכן הזה
        </Link>
      </section>
    </div>
  )
}
