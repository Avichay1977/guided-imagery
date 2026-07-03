import type { Profile, Right } from '../types'

const LAST_CHECKED = '2026-07-03'

const isChild = (p: Profile) => p.ageGroup !== '18+'
const hasDiagnosis = (p: Profile) =>
  p.diagnosisStatus === 'private' || p.diagnosisStatus === 'public'
const hasChildAllowance = (p: Profile) => p.allowanceStatus === 'child_disability'
const hasAdultAllowance = (p: Profile) =>
  p.allowanceStatus === 'general_disability' || p.allowanceStatus === 'special_services'

export const RIGHTS: Right[] = [
  {
    id: 'diagnosis_referral',
    title: 'הפניה לאבחון דרך קופת החולים',
    shortDescription:
      'ילדים עד גיל 18 עם סימנים לאוטיזם זכאים לאבחון וטיפול דרך מכוני התפתחות הילד של קופות החולים.',
    category: 'health',
    priority: 1,
    eligibility: (p) =>
      isChild(p) && (p.diagnosisStatus === 'none' || p.diagnosisStatus === 'in_process')
        ? 'eligible'
        : 'no',
    requiredDocuments: ['hmo_docs', 'id_appendix'],
    steps: [
      'לקבוע תור לרופא/ת הילדים ולתאר את הקשיים (תקשורת, ויסות חושי, נוקשות, קושי חברתי).',
      'לבקש הפניה למכון להתפתחות הילד או לאבחון ASD.',
      'אפשר להשתמש במחולל המכתבים כדי להכין בקשת הפניה מוכנה מראש.',
      'לשמור כל מסמך ואבחון ביניים — הם ישמשו בהמשך גם לביטוח לאומי.',
    ],
    source: {
      name: 'משרד הבריאות — אבחון וטיפול באוטיזם',
      url: 'https://www.gov.il/he/departments/topics/autism',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
    letterTemplateId: 'hmo_referral',
  },
  {
    id: 'child_disability_allowance',
    title: 'גמלת ילד נכה מביטוח לאומי',
    shortDescription:
      'ילד עם אבחון אוטיזם זכאי לגמלת ילד נכה בשיעור 100% (כ-3,820 ₪ לחודש). במקרים של תלות מלאה ייתכנו שיעורים של 188% או 235%.',
    category: 'allowance',
    priority: 2,
    eligibility: (p) => {
      if (!isChild(p)) return 'no'
      if (hasChildAllowance(p)) return 'no'
      if (hasDiagnosis(p)) return 'eligible'
      if (p.diagnosisStatus === 'in_process' || p.allowanceStatus === 'unknown') return 'maybe'
      return 'no'
    },
    eligibilityNote: 'אם האבחון עדיין בתהליך — אפשר להתחיל לאסוף מסמכים כבר עכשיו.',
    requiredDocuments: [
      'medical_diagnosis',
      'psych_diagnosis',
      'diagnostic_tool_report',
      'school_confirmation',
      'id_appendix',
      'bank_confirmation',
    ],
    steps: [
      'לוודא שיש אבחון רפואי מפסיכיאטר ילדים ונוער / נוירולוג / רופא התפתחותי.',
      'לוודא שיש אבחון פסיכולוגי ודו״ח כלי אבחון (ADOS / CARS / GARS / ADI).',
      'להשיג אישור לימודים מהמסגרת החינוכית.',
      'למלא טופס 7821 באתר ביטוח לאומי (טופס מקוון).',
      'לציין בתביעה בקשה לתשלום רטרואקטיבי — עד שנה אחורה ממועד ההגשה.',
    ],
    formUrl:
      'https://www.btl.gov.il/benefits/Disabled_Child/Pages/default.aspx',
    source: {
      name: 'ביטוח לאומי — גמלת ילד נכה',
      url: 'https://www.btl.gov.il/benefits/Disabled_Child/Pages/default.aspx',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
    letterTemplateId: 'ni_docs',
  },
  {
    id: 'retroactive_claim',
    title: 'תשלום רטרואקטיבי על גמלת ילד נכה',
    shortDescription:
      'הזכאות לגמלה יכולה להיות רטרואקטיבית עד שנה ממועד הגשת התביעה — חשוב לאסוף מסמכים של השנה האחרונה.',
    category: 'allowance',
    priority: 3,
    eligibility: (p) =>
      isChild(p) && hasDiagnosis(p) && !hasChildAllowance(p) ? 'eligible' : 'no',
    requiredDocuments: ['medical_diagnosis', 'psych_diagnosis'],
    steps: [
      'לבדוק מאיזה תאריך קיימים מסמכים רפואיים המעידים על המצב.',
      'לצרף לתביעה את כל המסמכים מהשנה האחרונה.',
      'לבקש במפורש בטופס התביעה תשלום רטרואקטיבי.',
    ],
    source: {
      name: 'ביטוח לאומי — גמלת ילד נכה',
      url: 'https://www.btl.gov.il/benefits/Disabled_Child/Pages/default.aspx',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
  },
  {
    id: 'hmo_treatments',
    title: 'טיפולים פרא-רפואיים דרך קופת החולים',
    shortDescription:
      'ילד עם אבחון זכאי לעד 3 טיפולים בשבוע דרך הקופה: ריפוי בעיסוק, קלינאות תקשורת, פיזיותרפיה, פסיכולוגיה, עבודה סוציאלית.',
    category: 'health',
    priority: 4,
    eligibility: (p) => (isChild(p) && hasDiagnosis(p) ? 'eligible' : 'no'),
    requiredDocuments: ['medical_diagnosis', 'hmo_docs'],
    steps: [
      'לפנות לקופת החולים עם האבחון ולבקש תוכנית טיפולים.',
      'לבדוק אילו טיפולים זמינים בסניף הקרוב ומה זמני ההמתנה.',
      'אם אין זמינות — לבקש התחייבות (טופס 17) לטיפול אצל ספק חיצוני.',
    ],
    source: {
      name: 'משרד הבריאות — זכויות ילדים עם אוטיזם',
      url: 'https://www.gov.il/he/departments/topics/autism',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
    letterTemplateId: 'hmo_referral',
  },
  {
    id: 'tavam',
    title: 'טיפול בריאותי מקדם (טב״ם)',
    shortDescription:
      'ילדים עד גיל 7 שאובחנו על הרצף ושוהים במסגרות ייעודיות זכאים לטיפול בריאותי מקדם במימון משרד הבריאות.',
    category: 'health',
    priority: 5,
    eligibility: (p) => {
      if (!(p.ageGroup === '0-3' || p.ageGroup === '3-7')) return 'no'
      if (!hasDiagnosis(p)) return 'no'
      return p.educationFramework === 'special_autism' || p.educationFramework === 'special'
        ? 'eligible'
        : 'maybe'
    },
    eligibilityNote: 'הזכאות תלויה בשהות במסגרת ייעודית לילדים על הרצף.',
    requiredDocuments: ['medical_diagnosis', 'school_confirmation'],
    steps: [
      'לבדוק מול המסגרת החינוכית אם היא מוכרת כמסגרת ייעודית (גן תקשורת / מעון שיקומי).',
      'לוודא שהמסגרת מגישה את הבקשה למימון טב״ם.',
    ],
    source: {
      name: 'כל זכות — טיפול בריאותי מקדם',
      url: 'https://www.kolzchut.org.il/he/טיפול_בריאותי_מקדם_(טב%22ם)_לילדים_עם_אוטיזם',
      lastChecked: LAST_CHECKED,
      confidence: 'medium',
    },
  },
  {
    id: 'water_discount',
    title: 'הטבה בתעריף המים',
    shortDescription:
      'מקבלי גמלת ילד נכה זכאים לתוספת חודשית של 3.5 מ״ק מים בתעריף הנמוך — הכמות בתעריף הנמוך מוכפלת ל-7 מ״ק לחודש.',
    category: 'municipal',
    priority: 6,
    eligibility: (p) => {
      if (hasChildAllowance(p) || hasAdultAllowance(p)) return 'eligible'
      if (hasDiagnosis(p)) return 'maybe'
      return 'no'
    },
    eligibilityNote: 'הזכאות נגזרת מקבלת קצבה — אם עדיין אין קצבה, קודם מגישים תביעה לביטוח לאומי.',
    requiredDocuments: ['ni_decision', 'water_bill', 'id_appendix'],
    steps: [
      'לוודא שהזכאי רשום כמתגורר בכתובת שבה מתנהל חשבון המים.',
      'לבדוק אם ההטבה כבר מיושמת אוטומטית (רשות המים מעבירה רשימות זכאים).',
      'אם לא — לפנות לתאגיד המים עם אישור הקצבה. אפשר להיעזר במחולל המכתבים.',
    ],
    source: {
      name: 'כל זכות — כמות מים מוגדלת בתעריף נמוך',
      url: 'https://www.kolzchut.org.il/he/הקצאת_כמות_מים_נוספת_בתעריף_נמוך_לאנשים_עם_מוגבלות',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
    letterTemplateId: 'water',
  },
  {
    id: 'arnona_discount',
    title: 'הנחה בארנונה',
    shortDescription:
      'הורים לילד שמתגורר איתם ומקבל גמלת ילד נכה עשויים לקבל הנחה של עד 33% (עד 90% במצטבר), בכפוף להחלטת הרשות המקומית.',
    category: 'municipal',
    priority: 7,
    eligibility: (p) => {
      if (hasChildAllowance(p) && p.livesAtHome !== 'no') return 'eligible'
      if (hasAdultAllowance(p)) return 'maybe'
      if (hasDiagnosis(p)) return 'maybe'
      return 'no'
    },
    eligibilityNote:
      'חשוב: חשבון הארנונה צריך להיות רשום על שם ההורה/הזכאי המתגורר בנכס.',
    requiredDocuments: ['ni_decision', 'arnona_bill', 'id_appendix'],
    steps: [
      'לבדוק על שם מי רשום חשבון הארנונה — אם לא על שם ההורה, לעדכן קודם ברשות.',
      'להגיש בקשה להנחה במחלקת הגבייה של הרשות המקומית עם אישור הקצבה.',
      'לשאול אם ההנחה ניתנת רטרואקטיבית לשנת הכספים הנוכחית.',
    ],
    source: {
      name: 'כל זכות — הנחה בארנונה להורים לילד עם נכות',
      url: 'https://www.kolzchut.org.il/he/הנחה_בארנונה_להורים_לילד_עם_נכות',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
    letterTemplateId: 'arnona',
  },
  {
    id: 'tax_credit',
    title: 'נקודות זיכוי במס הכנסה',
    shortDescription:
      'הורים ל"ילד נטול יכולת" זכאים ל-2 נקודות זיכוי שנתיות — שווי של כ-5,808 ₪ לשנה (כ-484 ₪ לחודש) לשנת 2026.',
    category: 'tax',
    priority: 8,
    eligibility: (p) => {
      if (p.userType !== 'parent') return 'no'
      if (hasChildAllowance(p) || (hasDiagnosis(p) && isChild(p))) return 'eligible'
      if (hasDiagnosis(p)) return 'maybe'
      return 'no'
    },
    eligibilityNote: 'ניתן לבקש גם עבור בגיר עם מוגבלות שההורה מכלכל.',
    requiredDocuments: ['medical_diagnosis', 'ni_decision', 'form_101'],
    steps: [
      'למלא טופס 116א (בקשה לזיכוי ממס בגין קרוב נטול יכולת).',
      'לצרף אבחון ואישור גמלת ילד נכה.',
      'להגיש לפקיד השומה או דרך המעסיק. אפשר לבקש החזר עד 6 שנים אחורה.',
    ],
    source: {
      name: 'כל זכות — נקודות זיכוי להורים לילד עם מוגבלות',
      url: 'https://www.kolzchut.org.il/he/נקודות_זיכוי_ממס_הכנסה_להורים_לילד_עם_מוגבלות',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
    letterTemplateId: 'tax_credit',
  },
  {
    id: 'parking_badge',
    title: 'תג חניה לרכב',
    shortDescription:
      'תג נכה עשוי להינתן כשיש קושי בניידות או צורך בליווי צמוד — לפי מצב תפקודי ומסמכים רפואיים.',
    category: 'transport',
    priority: 9,
    eligibility: (p) => {
      if (!hasDiagnosis(p)) return 'no'
      return p.functionalLevel === 'supervision' || p.functionalLevel === 'high_dependency'
        ? 'maybe'
        : 'no'
    },
    eligibilityNote: 'הזכאות אינה אוטומטית — נבחנת לפי מסמכים רפואיים על מגבלות ניידות/השגחה.',
    requiredDocuments: ['medical_diagnosis', 'id_appendix'],
    steps: [
      'לאסוף מסמכים רפואיים המתארים את הקושי בניידות או הצורך בהשגחה.',
      'להגיש בקשה מקוונת ליחידה לטיפול במוגבלי ניידות במשרד התחבורה.',
    ],
    source: {
      name: 'משרד התחבורה — בקשה לתג נכה',
      url: 'https://www.gov.il/he/service/request_for_disabled_parking_badge',
      lastChecked: LAST_CHECKED,
      confidence: 'medium',
    },
  },
  {
    id: 'education_committee',
    title: 'ועדת זכאות ואפיון (חינוך מיוחד)',
    shortDescription:
      'קובעת זכאות לשירותי חינוך מיוחדים — סל אישי, שילוב או מסגרת ייעודית. חשוב להגיע עם תיק מסמכים מסודר.',
    category: 'education',
    priority: 10,
    eligibility: (p) => {
      if (!isChild(p) || p.ageGroup === '0-3') return 'no'
      if (hasDiagnosis(p)) return 'eligible'
      return p.diagnosisStatus === 'in_process' ? 'maybe' : 'no'
    },
    requiredDocuments: [
      'medical_diagnosis',
      'psych_diagnosis',
      'school_confirmation',
      'committee_protocol',
    ],
    steps: [
      'לפנות למסגרת החינוכית או למתי״א ולבקש דיון בוועדת זכאות ואפיון.',
      'להכין תיק: אבחונים, שאלוני תפקוד, דוחות חינוכיים.',
      'לזכור: להורים יש זכות להשתתף בדיון ולהשמיע עמדה, כולל בחירת סוג המסגרת.',
    ],
    source: {
      name: 'כל זכות — ועדת זכאות ואפיון',
      url: 'https://www.kolzchut.org.il/he/ועדת_זכאות_ואפיון',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
    letterTemplateId: 'education_committee',
  },
  {
    id: 'general_disability',
    title: 'קצבת נכות כללית (18+)',
    shortDescription:
      'מיועדת למי שמעל גיל 18 שכושר ההשתכרות שלו נפגע ב-50% ומעלה עקב ליקוי גופני, שכלי או נפשי.',
    category: 'allowance',
    priority: 2,
    eligibility: (p) => {
      if (isChild(p)) return 'no'
      if (p.allowanceStatus === 'general_disability') return 'no'
      return hasDiagnosis(p) ? 'maybe' : 'no'
    },
    eligibilityNote:
      'אצל בוגרים הזכאות נבחנת לפי תפקוד וכושר עבודה — לא לפי האבחון בלבד.',
    requiredDocuments: ['medical_diagnosis', 'psych_diagnosis', 'id_appendix', 'bank_confirmation'],
    steps: [
      'לאסוף מסמכים רפואיים עדכניים על האבחון וההשפעה על התפקוד והעבודה.',
      'להגיש תביעה לקצבת נכות כללית באתר ביטוח לאומי.',
      'להתכונן לוועדה רפואית: לתאר יום-יום אמיתי, לא "יום טוב".',
    ],
    source: {
      name: 'ביטוח לאומי — קצבת נכות כללית',
      url: 'https://www.btl.gov.il/benefits/Disability_Insurance/Pages/default.aspx',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
  },
  {
    id: 'special_services',
    title: 'קצבת שירותים מיוחדים (18+)',
    shortDescription:
      'למי שזקוק לעזרה רבה בפעולות יום-יום (לבישה, אכילה, רחצה, ניידות בבית) או להשגחה מתמדת למניעת סכנה.',
    category: 'allowance',
    priority: 3,
    eligibility: (p) => {
      if (isChild(p)) return 'no'
      if (p.allowanceStatus === 'special_services') return 'no'
      return p.functionalLevel === 'supervision' || p.functionalLevel === 'high_dependency'
        ? 'maybe'
        : 'no'
    },
    requiredDocuments: ['medical_diagnosis', 'id_appendix'],
    steps: [
      'לתעד את הצורך בעזרה או השגחה בפעולות היום-יום.',
      'להגיש תביעה לקצבת שירותים מיוחדים בביטוח לאומי.',
    ],
    source: {
      name: 'ביטוח לאומי — קצבת שירותים מיוחדים',
      url: 'https://www.btl.gov.il/benefits/Attendance_Allowance/Pages/default.aspx',
      lastChecked: LAST_CHECKED,
      confidence: 'high',
    },
  },
  {
    id: 'adult_utility_discounts',
    title: 'הנחות מים, ארנונה וחשמל לבוגרים',
    shortDescription:
      'מבוגרים על הרצף שמקבלים קצבת נכות כללית או שירותים מיוחדים עשויים להיות זכאים להנחות במים, ארנונה וחשמל.',
    category: 'municipal',
    priority: 6,
    eligibility: (p) => {
      if (isChild(p)) return 'no'
      return hasAdultAllowance(p) ? 'eligible' : 'no'
    },
    requiredDocuments: ['ni_decision', 'arnona_bill', 'water_bill', 'electricity_bill'],
    steps: [
      'לבדוק שהחשבונות רשומים על שם הזכאי בכתובת המגורים.',
      'לפנות לרשות המקומית (ארנונה), לתאגיד המים ולחברת החשמל עם אישור הקצבה.',
    ],
    source: {
      name: 'משרד הבריאות — זכויות בוגרים על הרצף',
      url: 'https://www.gov.il/he/departments/topics/autism',
      lastChecked: LAST_CHECKED,
      confidence: 'medium',
    },
  },
]

export function getRight(id: string): Right | undefined {
  return RIGHTS.find((r) => r.id === id)
}
