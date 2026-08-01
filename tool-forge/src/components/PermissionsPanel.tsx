import type { ToolSpec } from '../types'
import { PERMISSION_LABELS } from '../engine/capabilities'
import { permissionsFor } from '../engine/specSchema'

/**
 * מה הכלי הזה רשאי לעשות — נגזר מהיכולות שהוא משתמש בהן, לא מוצהר בנפרד.
 * אם משהו לא מופיע כאן, אין דרך שהכלי יעשה אותו.
 */
export function PermissionsPanel({ spec }: { spec: ToolSpec }) {
  const permissions = permissionsFor(spec)

  return (
    <ul className="space-y-1 text-xs">
      {permissions.map((permission) => {
        const needsApproval = permission === 'calendar.write'
        return (
          <li key={permission} className="flex items-start gap-2">
            <span aria-hidden className={needsApproval ? 'text-amber-300' : 'text-signal-400'}>
              {needsApproval ? '⚠' : '✓'}
            </span>
            <span className="text-panel-400">
              {PERMISSION_LABELS[permission]}
              {needsApproval && <span className="text-amber-300"> · דורש אישור</span>}
            </span>
          </li>
        )
      })}
      <li className="flex items-start gap-2">
        <span aria-hidden className="text-panel-600">
          ✕
        </span>
        <span className="text-panel-600">
          שליחת הודעות, מחיקת מידע, תשלומים וכל פעולה אחרת מחוץ לאפליקציה
        </span>
      </li>
    </ul>
  )
}
