import { Link } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { nextBestAction } from '../engine/eligibility'
import { docLabel } from '../data/docTypes'

export default function Focus() {
  const { profile, actions, ownedDocTypes } = useApp()
  if (!profile) return null

  const next = nextBestAction(profile, actions, ownedDocTypes)

  return (
    <div className="flex min-h-[85vh] flex-col items-center justify-center gap-8 text-center">
      <p className="text-gray-500">נשימה עמוקה. יש רק דבר אחד לעשות עכשיו:</p>
      {next ? (
        <>
          <div className="rounded-3xl border-2 border-calm-200 bg-white p-8 shadow-lg">
            <h1 className="text-2xl font-bold leading-relaxed text-calm-800">
              {next.missingDocs.length > 0
                ? `להשיג מסמך אחד: ${docLabel(next.missingDocs[0])}`
                : next.status === 'rejected'
                  ? 'להכין מכתב ערעור — יש תבנית מוכנה'
                  : `להגיש: ${next.right.title}`}
            </h1>
            <p className="mt-4 text-gray-500">זה הכול. שאר הדברים מחכים בסבלנות.</p>
          </div>
          <Link
            to={next.status === 'rejected' ? '/letters/appeal' : `/rights/${next.right.id}`}
            className="rounded-2xl bg-calm-700 px-10 py-4 text-xl font-bold text-white"
          >
            קדימה, צעד אחד
          </Link>
        </>
      ) : (
        <div className="rounded-3xl bg-green-50 p-8 text-xl text-green-800">
          אין שום משימה פתוחה. מותר לנוח. 🌿
        </div>
      )}
      <Link to="/" className="text-gray-400 underline">
        חזרה למסך הראשי
      </Link>
    </div>
  )
}
