exports.handler=async event=>{
  const json=(code,data)=>({statusCode:code,headers:{'Content-Type':'application/json','Cache-Control':'no-store'},body:JSON.stringify(data)});
  if(event.httpMethod!=='POST')return json(405,{error:'method not allowed'});
  const key=(process.env.GMI_API_KEY||'').trim();if(!key)return json(503,{error:'GMI_API_KEY is not configured'});
  try{
    const raw=event.isBase64Encoded?Buffer.from(event.body||'','base64'):Buffer.from(event.body||'');
    const req=new Request('http://localhost/upload',{method:'POST',headers:{'Content-Type':event.headers['content-type']||event.headers['Content-Type']},body:raw});
    const file=(await req.formData()).get('file');if(!file||typeof file.arrayBuffer!=='function')return json(400,{error:'请选择素材'});
    const ext=file.name.split('.').pop().toLowerCase(), mime={png:'image/png',jpg:'image/jpeg',jpeg:'image/jpeg',mp4:'video/mp4'};
    if(!mime[ext]||file.size>(ext==='mp4'?50:10)*1024*1024)return json(400,{error:'素材格式或大小不受支持'});
    const sign=await fetch('https://console.gmicloud.ai/api/v1/ie/requestqueue/apikey/upload-url',{method:'POST',headers:{Authorization:'Bearer '+key,'Content-Type':'application/json'},body:JSON.stringify({file_type:ext})});
    const data=await sign.json();if(!sign.ok)return json(sign.status,data);
    const uploaded=await fetch(data.upload_url,{method:'PUT',headers:{'Content-Type':mime[ext]},body:await file.arrayBuffer()});
    if(!uploaded.ok)return json(502,{error:'素材上传失败'});
    return json(200,{url:data.public_url,name:file.name});
  }catch{return json(502,{error:'无法上传到 GMI Cloud'});}
};
