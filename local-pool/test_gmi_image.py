import sys, unittest
from unittest.mock import patch, AsyncMock
sys.path.insert(0, 'D:/monid-pool')
from server import gmi_image as m

class ImageTests(unittest.IsolatedAsyncioTestCase):
 async def test_submit(self):
  task = {'id':'test','key':'secret','status':'queued'}
  req = AsyncMock(return_value={'request_id':'up','status':'success','outcome':{'media_urls':[{'url':'https://example.org/result.png'}]}})
  with patch.object(m.gmi_http,'request',new=req), patch.object(m,'save_task'):
   await m.run_task(task, {'prompt':'draw'})
  self.assertEqual(req.call_args.kwargs['body']['model'], 'gemini-nano-banana-2.1')
  self.assertEqual(task['status'], 'completed')
  self.assertNotIn('key', m.public_task(task))

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
