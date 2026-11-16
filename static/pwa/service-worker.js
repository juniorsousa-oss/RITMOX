/* RITMOX PWA: sem fetch interception e sem CacheStorage. */
self.addEventListener("install",()=>{self.skipWaiting();});
self.addEventListener("activate",e=>{e.waitUntil(self.clients.claim());});
