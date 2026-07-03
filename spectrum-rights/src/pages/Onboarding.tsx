import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useApp } from '../store/AppContext'
import { DOC_TYPES } from '../data/docTypes'
import type { Profile } from '../types'

type Answers = Partial<Profile>

interface ChoiceQuestion {
  key: keyof Profile
  kind: 'choice'
  title: string
  subtitle?: string
  options: { value: string; label: string }[]
  skipIf?: (a: Answers) => boolean
}

interface TextQuestion {
  key: keyof Profile
  kind: 'text'
  title: string
  subtitle?: string
  placeholder: string
}

interface MultiQuestion {
  key: keyof Profile
  kind: 'multi'
  title: string
  subtitle?: string
  options: { value: string; label: string }[]
}

type Question = ChoiceQuestion | TextQuestion | MultiQuestion

const QUESTIONS: Question[] = [
  {
    key: 'userType',
    kind: 'choice',
    title: 'מי ממלא את השאלון?',
    options: [
      { value: 'parent', label: 'הורה לילד/ה על הרצף' },
      { value: 'adult', label: 'אני על הרצף' },
      { value: 'family', label: 'בן/בת משפחה אחר/ת' },
    ],
  },
  {
    key: 'ageGroup',
    kind: 'choice',
    title: 'מה הגיל של האדם על הרצף?',
    options: [
      { value: '0-3', label: '0 עד 3' },
      { value: '3-7', label: '3 עד 7' },
      { value: '7-18', label: '7 עד 18' },
      { value: '18+', label: '18 ומעלה' },
    ],
  },
  {
    key: 'diagnosisStatus',
    kind: 'choice',
    title: 'מה מצב האבחון?',
    options: [
      { value: 'none', label: 'אין אבחון — רק חשד' },
      { value: 'in_process', label: 'בתהליך אבחון' },
      { value: 'private', label: 'יש אבחון פרטי' },
      { value: 'public', label: 'יש אבחון דרך הקופה / ציבורי' },
    ],
  },
  {
    key: 'allowanceStatus',
    kind: 'choice',
    title: 'האם מתקבלת קצבה מביטוח לאומי?',
    options: [
      { value: 'none', label: 'אין קצבה' },
      { value: 'child_disability', label: 'גמלת ילד נכה' },
      { value: 'general_disability', label: 'קצבת נכות כללית' },
      { value: 'special_services', label: 'קצבת שירותים מיוחדים' },
      { value: 'unknown', label: 'לא יודע/ת' },
    ],
  },
  {
    key: 'city',
    kind: 'text',
    title: 'באיזו עיר גרים?',
    subtitle: 'ההנחות בארנונה ובמים תלויות ברשות המקומית',
    placeholder: 'למשל: חיפה',
  },
  {
    key: 'hmo',
    kind: 'choice',
    title: 'באיזו קופת חולים?',
    options: [
      { value: 'clalit', label: 'כללית' },
      { value: 'maccabi', label: 'מכבי' },
      { value: 'meuhedet', label: 'מאוחדת' },
      { value: 'leumit', label: 'לאומית' },
    ],
  },
  {
    key: 'educationFramework',
    kind: 'choice',
    title: 'באיזו מסגרת חינוכית?',
    skipIf: (a) => a.ageGroup === '18+',
    options: [
      { value: 'none', label: 'אין מסגרת כרגע' },
      { value: 'regular', label: 'מסגרת רגילה' },
      { value: 'integration', label: 'שילוב במסגרת רגילה' },
      { value: 'special', label: 'חינוך מיוחד' },
      { value: 'special_autism', label: 'גן/כיתת תקשורת (ייעודי לרצף)' },
    ],
  },
  {
    key: 'livesAtHome',
    kind: 'choice',
    title: 'האם האדם על הרצף גר בבית עם המשפחה?',
    options: [
      { value: 'yes', label: 'כן' },
      { value: 'no', label: 'לא' },
      { value: 'unknown', label: 'מצב מורכב / חלקי' },
    ],
  },
  {
    key: 'billsInApplicantName',
    kind: 'choice',
    title: 'האם חשבונות הארנונה והמים רשומים על שם ההורה / הזכאי?',
    subtitle: 'זה משפיע על היכולת לקבל הנחות ארנונה ומים',
    options: [
      { value: 'yes', label: 'כן' },
      { value: 'no', label: 'לא' },
      { value: 'unknown', label: 'לא יודע/ת' },
    ],
  },
  {
    key: 'functionalLevel',
    kind: 'choice',
    title: 'איך היית מתאר/ת את המצב התפקודי?',
    subtitle: 'אין תשובה נכונה — זה עוזר לדייק את רשימת הזכויות',
    options: [
      { value: 'independent', label: 'עצמאי/ת ברוב הדברים' },
      { value: 'partial_help', label: 'צריך/ה עזרה חלקית' },
      { value: 'supervision', label: 'צריך/ה השגחה' },
      { value: 'high_dependency', label: 'תלות גבוהה בעזרת הזולת' },
    ],
  },
  {
    key: 'documentsAvailable',
    kind: 'multi',
    title: 'אילו מסמכים כבר יש לך ביד?',
    subtitle: 'אפשר לסמן כמה שרוצים, או לדלג — נשלים אחר כך',
    options: DOC_TYPES.map((d) => ({ value: d.id, label: d.label })),
  },
]

const DEFAULTS: Profile = {
  userType: 'parent',
  ageGroup: '7-18',
  diagnosisStatus: 'none',
  allowanceStatus: 'none',
  city: '',
  hmo: '',
  educationFramework: '',
  livesAtHome: 'yes',
  billsInApplicantName: 'unknown',
  functionalLevel: 'partial_help',
  documentsAvailable: [],
}

export default function Onboarding() {
  const { setProfile } = useApp()
  const navigate = useNavigate()
  const [answers, setAnswers] = useState<Answers>({})
  const [step, setStep] = useState(0)
  const [textValue, setTextValue] = useState('')
  const [multiValue, setMultiValue] = useState<string[]>([])

  const visible = QUESTIONS.filter((q) => !('skipIf' in q && q.skipIf && q.skipIf(answers)))
  const question = visible[step]
  const isLast = step === visible.length - 1

  function finish(finalAnswers: Answers) {
    setProfile({ ...DEFAULTS, ...finalAnswers })
    navigate('/')
  }

  function advance(next: Answers) {
    if (isLast) {
      finish(next)
    } else {
      setAnswers(next)
      setStep(step + 1)
      setTextValue('')
      setMultiValue([])
    }
  }

  function answerChoice(value: string) {
    advance({ ...answers, [question.key]: value })
  }

  function answerText() {
    advance({ ...answers, [question.key]: textValue.trim() })
  }

  function answerMulti() {
    advance({ ...answers, [question.key]: multiValue })
  }

  function back() {
    if (step > 0) {
      setStep(step - 1)
    } else {
      navigate('/')
    }
  }

  return (
    <div className="flex min-h-[80vh] flex-col">
      <div className="mb-6 flex items-center gap-3">
        <button onClick={back} className="text-2xl text-gray-400" aria-label="חזרה">
          →
        </button>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-calm-100">
          <div
            className="h-full rounded-full bg-calm-600 transition-all"
            style={{ width: `${((step + 1) / visible.length) * 100}%` }}
          />
        </div>
        <span className="text-sm text-gray-400">
          {step + 1}/{visible.length}
        </span>
      </div>

      <h2 className="mb-2 text-2xl font-bold text-calm-800">{question.title}</h2>
      {question.subtitle && <p className="mb-4 text-gray-500">{question.subtitle}</p>}

      <div className="mt-4 flex flex-col gap-3">
        {question.kind === 'choice' &&
          question.options.map((opt) => (
            <button
              key={opt.value}
              onClick={() => answerChoice(opt.value)}
              className="rounded-2xl border-2 border-calm-100 bg-white p-4 text-right text-lg transition hover:border-calm-600 hover:bg-calm-50"
            >
              {opt.label}
            </button>
          ))}

        {question.kind === 'text' && (
          <>
            <input
              type="text"
              value={textValue}
              onChange={(e) => setTextValue(e.target.value)}
              placeholder={question.placeholder}
              className="rounded-2xl border-2 border-calm-100 bg-white p-4 text-lg focus:border-calm-600 focus:outline-none"
            />
            <button
              onClick={answerText}
              className="mt-2 rounded-2xl bg-calm-700 p-4 text-lg font-bold text-white disabled:opacity-40"
              disabled={!textValue.trim()}
            >
              המשך
            </button>
          </>
        )}

        {question.kind === 'multi' && (
          <>
            <div className="flex max-h-[45vh] flex-col gap-2 overflow-y-auto">
              {question.options.map((opt) => {
                const checked = multiValue.includes(opt.value)
                return (
                  <button
                    key={opt.value}
                    onClick={() =>
                      setMultiValue(
                        checked
                          ? multiValue.filter((v) => v !== opt.value)
                          : [...multiValue, opt.value],
                      )
                    }
                    className={`rounded-2xl border-2 p-3 text-right transition ${
                      checked
                        ? 'border-calm-600 bg-calm-50 font-medium'
                        : 'border-calm-100 bg-white'
                    }`}
                  >
                    {checked ? '✓ ' : ''}
                    {opt.label}
                  </button>
                )
              })}
            </div>
            <button
              onClick={answerMulti}
              className="mt-2 rounded-2xl bg-calm-700 p-4 text-lg font-bold text-white"
            >
              {multiValue.length > 0 ? `סיום (${multiValue.length} מסמכים)` : 'דילוג — אין לי מסמכים כרגע'}
            </button>
          </>
        )}
      </div>
    </div>
  )
}
