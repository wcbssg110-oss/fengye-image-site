function buildVideo(body) {
  const requested=body.model, prompt=String(body.prompt||'').trim();
  const first=body.first_frame||body.image||'', last=body.last_frame||'';
  const images=body.reference_images||[], videos=body.reference_videos||[], clip=body.first_clip||'';
  const duration=Number(body.duration), resolution=body.resolution||'720p', ratio=body.ratio||'9:16';
  if(!Array.isArray(images)||!Array.isArray(videos)) throw Error('参考素材格式错误');
  if(!prompt||prompt.length>(requested.startsWith('wan')?1500:2000))throw Error('提示词为空或过长');
  if(!Number.isInteger(duration))throw Error('视频时长须为整数');
  if(!['16:9','9:16','1:1','4:3','3:4','21:9','adaptive'].includes(ratio))throw Error('画面比例不支持');
  const valid=u=>{try{const v=new URL(u);return v.protocol==='https:'&&!v.username&&!v.password;}catch{return false;}};
  if([first,last,clip,...images,...videos].filter(Boolean).some(u=>!valid(u)))throw Error('素材须上传成功后再提交');
  let model=requested,payload={prompt,duration};
  if(requested==='seedance-2-5-260628'){
    if(duration<4||duration>30||!['480p','720p'].includes(resolution))throw Error('Seedance 2.5 支持4–30秒、480p/720p');
    if(images.length>9||videos.length>3||clip)throw Error('Seedance 最多9张参考图、3个参考视频');
    Object.assign(payload,{resolution,generate_audio:body.generate_audio!==false});
    payload.ratio=first||last?'adaptive':ratio;
    if(first)payload.first_frame=first;if(last)payload.last_frame=last;
    if(images.length)payload.reference_images=images;if(videos.length)payload.reference_videos=videos;
  }else if(['kling-3.0-turbo-t2v','kling-3.0-turbo-i2v'].includes(requested)){
    if(duration<3||duration>15||!['720p','1080p'].includes(resolution))throw Error('可灵支持3–15秒、720p/1080p');
    if(last||images.length||videos.length||clip)throw Error('可灵 Turbo 仅支持单张首帧');
    model=first?'kling-3.0-turbo-i2v':'kling-3.0-turbo-t2v';
    Object.assign(payload,{resolution,duration:String(duration)});
    if(first)payload.first_frame=first;else {if(!['16:9','9:16','1:1'].includes(ratio))throw Error('可灵比例不支持');payload.aspect_ratio=ratio;}
  }else if(['wan2.7-t2v','wan2.7-i2v','wan2.7-r2v'].includes(requested)){
    if(duration<2||duration>15||!['720p','1080p'].includes(resolution))throw Error('Wan 支持2–15秒、720p/1080p');
    if(!['16:9','9:16','1:1','4:3','3:4'].includes(ratio))throw Error('Wan 比例不支持');
    Object.assign(payload,{resolution:resolution.toUpperCase(),prompt_extend:false,watermark:false});
    if(requested==='wan2.7-r2v'){
      if(last||clip||images.length+videos.length>5||!images.length&&!videos.length)throw Error('Wan 参考模式需素材且图与视频合计最多5个，不支持尾帧');
      payload.ratio=ratio;if(first)payload.first_frame=first;
      if(images.length)payload.reference_image=images;if(videos.length)payload.reference_video=videos;
    }else{
      if(images.length||videos.length)throw Error('多素材请选择 Wan 参考模式');
      model=first||last||clip?'wan2.7-i2v':'wan2.7-t2v';
      if(first)payload.first_frame=first;if(last)payload.last_frame=last;if(clip)payload.first_clip=clip;
      if(model.endsWith('t2v'))payload.ratio=ratio;
    }
  }else throw Error('不支持的视频模型');
  return {model,payload};
}
module.exports={buildVideo};
