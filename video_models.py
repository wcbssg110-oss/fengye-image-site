"""Payload contracts from GMI's model quickstarts (2026-10-01)."""
def build_video(body):
    requested = body.get('model', 'seedance-2-5-260628')
    prompt = str(body.get('prompt') or '').strip()
    first = body.get('first_frame') or body.get('image') or ''
    last = body.get('last_frame') or ''
    images = body.get('reference_images') or []
    videos = body.get('reference_videos') or []
    clip = body.get('first_clip') or ''
    if not isinstance(images, list) or not isinstance(videos, list):
        raise ValueError('参考素材格式错误')
    duration = int(body.get('duration', 5))
    res = body.get('resolution', '720p')
    ratio = body.get('ratio', '9:16')
    if ratio not in ('16:9','9:16','1:1','4:3','3:4','21:9','adaptive'):
        raise ValueError('画面比例不支持')
    if not prompt or len(prompt) > (1500 if requested.startswith('wan') else 2000):
        raise ValueError('请填写提示词，Wan 最多 1500 字，其余最多 2000 字')
    payload = {'prompt': prompt, 'duration': duration}
    model = requested
    if requested == 'seedance-2-5-260628':
        if not 4 <= duration <= 30 or res not in ('480p','720p'):
            raise ValueError('Seedance 2.5 官方接口支持 4–30 秒、480p/720p')
        if len(images) > 9 or len(videos) > 3 or clip:
            raise ValueError('Seedance 最多 9 张参考图、3 个参考视频')
        payload.update(resolution=res, ratio=ratio, generate_audio=body.get('generate_audio', True))
        if first: payload['first_frame'] = first
        if last: payload['last_frame'] = last
        if images: payload['reference_images'] = images
        if videos: payload['reference_videos'] = videos
    elif requested in ('kling-3.0-turbo-t2v','kling-3.0-turbo-i2v'):
        if not 3 <= duration <= 15 or res not in ('720p','1080p'):
            raise ValueError('可灵 Turbo 支持 3–15 秒、720p/1080p')
        if last or images or videos or clip:
            raise ValueError('可灵 Turbo 仅支持单张首帧；不支持尾帧、参考图组和参考视频')
        model = 'kling-3.0-turbo-i2v' if first else 'kling-3.0-turbo-t2v'
        payload.update(resolution=res, duration=str(duration))
        if first: payload['first_frame'] = first
        else:
            if ratio not in ('16:9','9:16','1:1'): raise ValueError('可灵画面比例不支持')
            payload['aspect_ratio'] = ratio
    elif requested in ('wan2.7-t2v','wan2.7-i2v','wan2.7-r2v'):
        if not 2 <= duration <= 15 or res not in ('720p','1080p'):
            raise ValueError('Wan 2.7 支持 2–15 秒、720p/1080p')
        if ratio not in ('16:9','9:16','1:1','4:3','3:4'): raise ValueError('Wan 画面比例不支持')
        payload.update(resolution=res.upper(), prompt_extend=False, watermark=False)
        if requested == 'wan2.7-r2v':
            if last or clip or len(images)+len(videos)>5 or not (images or videos):
                raise ValueError('Wan 参考模式需上传参考素材，图与视频合计最多 5 个；不支持尾帧')
            payload.update(ratio=ratio)
            if first: payload['first_frame'] = first
            if images: payload['reference_image'] = images
            if videos: payload['reference_video'] = videos
        else:
            if images or videos: raise ValueError('多素材参考请选择 Wan 2.7 参考模式')
            model = 'wan2.7-i2v' if (first or last or clip) else 'wan2.7-t2v'
            if first: payload['first_frame'] = first
            if last: payload['last_frame'] = last
            if clip: payload['first_clip'] = clip
            if model.endswith('t2v'): payload['ratio'] = ratio
    else:
        raise ValueError('不支持的视频模型')
    return model, payload
