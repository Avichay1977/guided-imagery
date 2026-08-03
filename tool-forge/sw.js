/**
 * Service worker — מה שהופך את האפליקציה למתקינה על אנדרואיד ולעובדת בלי רשת.
 *
 * שמות הקבצים שוויט מייצר כוללים hash, ולכן אין רשימת precache קבועה:
 * המטמון נבנה בזמן ריצה. מסמכים עוברים network-first (כדי לקבל גרסה חדשה
 * כשיש רשת), ונכסים סטטיים cache-first (כדי שהטעינה תהיה מיידית).
 */
const CACHE = 'toolforge-v1'

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE).then((cache) => cache.addAll(['./', './manifest.webmanifest'])),
  )
  self.skipWaiting()
})

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((key) => key !== CACHE && key !== SHARE_CACHE)
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  )
})

/**
 * שיתוף מאפליקציה אחרת (Share Target).
 *
 * זו הדרך היחידה שאנדרואיד נותן לאפליקציה לקבל תוכן מאפליקציה אחרת בלי
 * הרשאות מיוחדות ובלי לגעת בנתונים שלה: המשתמש בוחר "שיתוף" בוואטסאפ (או
 * בכל אפליקציה), בוחר אותנו, והמערכת שולחת לנו POST. אין כאן קריאה של
 * הודעות — יש כאן הודעה אחת שהמשתמש בחר להעביר.
 *
 * ה-POST מגיע לכתובת שאין לה דף, ולכן צריך לתפוס אותו כאן, לשמור את התוכן,
 * ולהפנות לאפליקציה. תמונות עוברות ל-data URL כי הן צריכות לשרוד ניווט.
 */
const SHARE_CACHE = 'toolforge-share'
const SHARE_KEY = './__shared__'

async function readShare(request) {
  const form = await request.formData()
  const files = form.getAll('files').filter((item) => item instanceof File)

  const images = []
  const texts = []
  for (const file of files) {
    if (file.type.startsWith('image/')) {
      const buffer = await file.arrayBuffer()
      let binary = ''
      const bytes = new Uint8Array(buffer)
      for (let i = 0; i < bytes.length; i++) binary += String.fromCharCode(bytes[i])
      images.push({ mediaType: file.type, data: btoa(binary), name: file.name })
    } else {
      texts.push(await file.text())
    }
  }

  return {
    at: new Date().toISOString(),
    title: form.get('title') || '',
    text: [form.get('text') || '', ...texts].filter(Boolean).join('\n\n'),
    url: form.get('url') || '',
    images,
  }
}

self.addEventListener('fetch', (event) => {
  const request = event.request

  if (request.method === 'POST' && new URL(request.url).pathname.endsWith('/share')) {
    event.respondWith(
      (async () => {
        try {
          const shared = await readShare(request)
          const cache = await caches.open(SHARE_CACHE)
          await cache.put(
            SHARE_KEY,
            new Response(JSON.stringify(shared), {
              headers: { 'Content-Type': 'application/json' },
            }),
          )
        } catch {
          // שיתוף שנכשל לא אמור להשאיר את המשתמש במסך שבור
        }
        return Response.redirect('./#/share', 303)
      })(),
    )
    return
  }

  // הקריאה שהאפליקציה עושה כדי לאסוף את מה שהשיתוף השאיר
  if (request.method === 'GET' && new URL(request.url).pathname.endsWith('/__shared__')) {
    event.respondWith(
      (async () => {
        const cache = await caches.open(SHARE_CACHE)
        const hit = await cache.match(SHARE_KEY)
        if (!hit) return new Response('null', { headers: { 'Content-Type': 'application/json' } })
        await cache.delete(SHARE_KEY) // צריכה חד־פעמית
        return hit
      })(),
    )
    return
  }

  if (request.method !== 'GET') return

  const url = new URL(request.url)
  if (url.origin !== self.location.origin) return

  if (request.mode === 'navigate') {
    event.respondWith(
      fetch(request)
        .then((response) => {
          const copy = response.clone()
          caches.open(CACHE).then((cache) => cache.put('./', copy))
          return response
        })
        .catch(() => caches.match('./').then((cached) => cached ?? Response.error())),
    )
    return
  }

  event.respondWith(
    caches.match(request).then(
      (cached) =>
        cached ??
        fetch(request).then((response) => {
          if (response.ok) {
            const copy = response.clone()
            caches.open(CACHE).then((cache) => cache.put(request, copy))
          }
          return response
        }),
    ),
  )
})
