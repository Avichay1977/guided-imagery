import { Link } from 'react-router-dom'

export default function Welcome() {
  return (
    <div className="flex min-h-[70vh] flex-col items-center justify-center gap-6 text-center">
      <div className="text-6xl" aria-hidden="true">
        🧩
      </div>
      <h1 className="text-3xl font-bold text-calm-800">זכות על הרצף</h1>
      <p className="max-w-sm text-lg leading-relaxed text-gray-600">
        ניווט זכויות, מסמכים ובירוקרטיה למשפחות ואנשים על הרצף בישראל.
        <br />
        בלי ז׳רגון. צעד אחד בכל פעם.
      </p>
      <Link
        to="/onboarding"
        className="rounded-2xl bg-calm-700 px-10 py-4 text-xl font-bold text-white shadow-lg transition hover:bg-calm-800"
      >
        בואו נתחיל
      </Link>
      <p className="text-sm text-gray-400">כמה שאלות קצרות — ותקבלו רשימת זכויות מותאמת אישית</p>
    </div>
  )
}
