const CACHE_NAME = 'align-cache-v2'; // ভার্সন আপডেট করা হয়েছে
const urlsToCache = [
  '/static/manifest.json',
  '/static/icon-192.png',
  '/static/icon-512.png',
  'https://fonts.googleapis.com/css2?family=Urbanist:wght@300;400;500;600;700;800&display=swap'
];

self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache => {
      return cache.addAll(urlsToCache);
    })
  );
  self.skipWaiting(); // নতুন ফাইল দ্রুত আপডেট করার জন্য
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cache => {
          if (cache !== CACHE_NAME) {
            return caches.delete(cache); // পুরোনো ক্যাশে মুছে ফেলা
          }
        })
      );
    })
  );
});

self.addEventListener('fetch', event => {
  // লগ-ইন বা ডেটা সেভ করার (POST) রিকোয়েস্টগুলো সরাসরি ইন্টারনেটে পাঠাবে
  if (event.request.method !== 'GET') {
      return; 
  }

  // Network First Strategy: আগে সার্ভার থেকে ফ্রেশ ডেটা আনবে, নেট না থাকলে ক্যাশে দেখাবে
  event.respondWith(
    fetch(event.request)
      .then(response => {
        let responseClone = response.clone();
        caches.open(CACHE_NAME).then(cache => {
          cache.put(event.request, responseClone);
        });
        return response;
      })
      .catch(() => {
        return caches.match(event.request);
      })
  );
});