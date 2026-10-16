import sys, unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0, 'D:/monid-pool')
from server import gmi_image as m

class ImageTests(unittest.IsolatedAsyncioTestCase):
 async def asyncSetUp(self):
  self.cache_patch = patch.object(m, 'cache_image', new=AsyncMock(side_effect=lambda task_id, url: url))
  self.cache_patch.start()
  self.addCleanup(self.cache_patch.stop)

 def test_echoed_reference_excluded(self):
  raw = {'outcome': {'next_turn_contents': [
   {'role':'user','parts':[{'inline_data':{'mime_type':'image/png','data':'REFERENCE'}}]},
   {'role':'model','parts':[{'fileData':{'mimeType':'image/png','fileUri':'https://storage.googleapis.com/generated.png'}}]}
  ], 'media_urls':[{'url':'https://example.org/other.png'}]}}
  self.assertEqual(m.image_urls(raw), ['https://storage.googleapis.com/generated.png'])

 def test_user_only_not_output(self):
  self.assertEqual(m.image_urls({'outcome':{'next_turn_contents':[{'role':'user','parts':[{'inline_data':{'data':'REFERENCE'}}]}]}}), [])

 async def test_submit(self):
  task = {'id':'test','key':'secret','status':'queued'}
  req = AsyncMock(return_value={'request_id':'up','status':'success','outcome':{'media_urls':[{'url':'https://example.org/result.png'}]}})
  with patch.object(m.gmi_http,'request',new=req), patch.object(m,'save_task'):
   await m.run_task(task, {'prompt':'draw'})
  self.assertEqual(req.call_args.kwargs['body']['model'], 'gemini-nano-banana-2.1')
  self.assertEqual(task['status'], 'completed')
  self.assertNotIn('key', m.public_task(task))

 async def test_ordered_reference_url_payload(self):
  req = AsyncMock(return_value={'request_id':'up','status':'success','outcome':{'media_urls':[{'url':'https://example.org/result.png'}]}})
  uploads = AsyncMock(side_effect=['https://storage.googleapis.com/ref1.png', 'https://storage.googleapis.com/ref2.png'])
  task = {'id':'test','key':'secret','status':'queued'}
  payload = {'prompt':'replace shoes','contents':[{'role':'user','parts':[
   {'text':'replace shoes'}, {'inline_data':{'data':'first'}}, {'inline_data':{'data':'second'}}]}]}
  with patch.object(m.gmi_http,'request',new=req), patch.object(m,'save_task'), patch.object(m,'upload_reference',new=uploads):
   await m.run_task(task,payload)
  sent = req.call_args.kwargs['body']['payload']
  self.assertNotIn('contents',sent)
  self.assertEqual(sent['image'],['https://storage.googleapis.com/ref1.png','https://storage.googleapis.com/ref2.png'])
  self.assertEqual(sent['prompt'],'replace shoes')
  self.assertEqual(task['reference_count'],2)

 async def test_upload_error_does_not_submit_generation(self):
  request = AsyncMock()
  task = {'id':'t','key':'secret','status':'queued'}
  with patch.object(m.gmi_http,'request',new=request), patch.object(m,'save_task'), patch.object(m,'upload_reference',new=AsyncMock(side_effect=RuntimeError('transport'))):
   await m.run_task(task,{'prompt':'draw','contents':[{'parts':[{'inline_data':{'data':'ref'}}]}]})
  request.assert_not_called()
  self.assertEqual(task['failed_phase'],'uploading')
  self.assertIn('尚未提交',task['error'])

 async def test_jpeg_signature_content_type_match(self):
  import base64, httpx
  from unittest.mock import MagicMock
  response = httpx.Response(200,request=httpx.Request('PUT','https://storage.googleapis.com/upload'))
  client = AsyncMock(); client.put.return_value = response
  factory = MagicMock(); factory.return_value.__aenter__ = AsyncMock(return_value=client)
  factory.return_value.__aexit__ = AsyncMock(return_value=None)
  signer = AsyncMock(return_value={'upload_url':'https://storage.googleapis.com/upload','public_url':'https://storage.googleapis.com/result.jpeg'})
  with patch('httpx.AsyncClient',factory), patch.object(m.gmi_http,'request',new=signer):
   await m.upload_reference('test',{'data':base64.b64encode(b'\xff\xd8\xfftest').decode()})
  self.assertEqual(signer.call_args.kwargs['body'],{'file_type':'jpeg'})
  self.assertEqual(client.put.call_args.kwargs['headers']['Content-Type'],'image/jpeg')

 async def test_no_resubmit(self):
  req = AsyncMock(side_effect=m.gmi_http.ApiError(502,'network failed'))
  with patch.object(m.gmi_http,'request',new=req), patch.object(m,'save_task'):
   task = {'id':'t','key':'secret','status':'queued'}
   await m.run_task(task, {'prompt':'draw'})
  self.assertEqual(req.await_count, 1)
  self.assertEqual(task['status'], 'failed')

 async def test_resume(self):
  req = AsyncMock(return_value={'status':'success','outcome':{'media_urls':[{'url':'https://example.org/result.png'}]}})
  with patch.object(m.gmi_http,'request',new=req), patch.object(m,'save_task'), patch.object(m.asyncio,'sleep',new=AsyncMock()):
   task = {'id':'t','key':'original','upstream_id':'up','status':'running'}
   await m.run_task(task)
  self.assertEqual(req.call_args.args[0], 'GET')
  self.assertEqual(req.call_args.kwargs['token'], 'original')

 def test_input_not_output(self):
  self.assertEqual(m.image_urls({'payload':{'image':[{'url':'https://example.org/input.png'}]}}), [])

 def test_inline(self):
  self.assertEqual(m.image_urls({'outcome':{'candidates':[{'content':{'parts':[{'inlineData':{'mimeType':'image/png','data':'abc'}}]}}]}}), ['data:image/png;base64,abc'])

if __name__ == '__main__': unittest.main()
