/* Identidade institucional RITMOX. Regras da marca são de acesso admin no servidor.
   Esta rotina jamais altera nem remove a assinatura by Nexon Labs. */
(async function applyRitmoxBrand(){
  try{
    const response=await fetch("/api/brand/public",{credentials:"same-origin",cache:"no-store"});
    if(!response.ok)return;
    const brand=await response.json();
    const primary=brand.primary_color||"#ff2d7a";
    const secondary=brand.secondary_color||"#00e5ff";
    for(const [key,color] of Object.entries({
      "--pink":primary,"--pink-2":primary,
      "--cyan":secondary,
      "--ritmox-primary":primary,"--ritmox-secondary":secondary
    })){
      document.documentElement.style.setProperty(key,color);
    }
    if(brand.logo_data){
      document.querySelectorAll(".brand-lockup-image, .logo").forEach(img=>{
        img.src=brand.logo_data;
        img.style.objectFit="contain";
      });
    }
    if(brand.favicon_data){
      document.querySelectorAll('link[rel="icon"], link[rel="shortcut icon"], link[rel="apple-touch-icon"]').forEach(link=>{
        link.href=brand.favicon_data;
      });
    }
  }catch(error){
    console.warn("Identidade do RITMOX indisponível, mantendo padrão.",error);
  }
})();
