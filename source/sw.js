const CACHE='__SW_CACHE_NAME__';
self.addEventListener('install',e=>self.skipWaiting());
self.addEventListener('activate',e=>e.waitUntil(caches.keys().then(k=>Promise.all(k.filter(x=>x!==CACHE).map(x=>caches.delete(x)))).then(()=>self.clients.claim())));
self.addEventListener('fetch',e=>{
  if(e.request.method!=='GET')return;
  const u=new URL(e.request.url);
  if(u.origin!==location.origin)return;
  const put=async(req,res)=>{try{if(res&&res.status===200&&res.clone){await caches.open(CACHE).then(c=>c.put(req,res.clone()));}}catch(_){}};
  const isHtml=!!(e.request.headers.get('accept')&&e.request.headers.get('accept').includes('text/html'));
  if(isHtml){
    // HTML：永远走网络。页面是最新的，缓存它只会把旧页面留住。
    e.respondWith(fetch(e.request).then(r=>{put(e.request,r);return r}).catch(()=>caches.match(e.request)));
    return;
  }
  // 静态资源：缓存优先。
  //   带版本号的 URL（?v=，见 themes/matery/scripts/asset-version.js）
  //   内容不会变 —— 命中就是最新的，直接给，不用再跟服务器来回一趟；
  //   不带版本号的（图片之类）在后台顺手跟服务器对一次，免得一直发旧的。
  const versioned=u.search.indexOf('v=')!==-1;
  e.respondWith(caches.match(e.request).then(c=>{
    if(c){
      if(!versioned){
        // 后台那次刷新的失败不许影响这一次的响应 —— try/catch 是因为
        // fetch() 在少数情况下会**同步**抛（比如给一个 mode 为 navigate
        // 的请求换 cache 模式）；那要是漏出去，整个 respondWith 就炸了。
        try{
          fetch(e.request,{cache:'no-cache'}).then(r=>{put(e.request,r);return r}).catch(()=>{});
        }catch(_){}
      }
      return c;
    }
    return fetch(e.request).then(r=>{put(e.request,r);return r}).catch(()=>caches.match(e.request));
  }));
});