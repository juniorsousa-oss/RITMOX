/* RITMOX — instalação PWA sem cache offline de treinos/anamnese. */
(()=>{if(!("serviceWorker"in navigator)||!window.isSecureContext)return;
window.addEventListener("load",()=>navigator.serviceWorker.register("/service-worker.js",{scope:"/"}).catch(()=>{}),{once:true});})();
