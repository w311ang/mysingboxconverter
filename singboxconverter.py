import httpx
import json
import yaml
from cachetools import cached, TTLCache
import re

class converter:
	client=httpx.Client()

	@cached(cache=TTLCache(maxsize=1024, ttl=3600))
	def __getsub(self, suburl):
		client=self.client
		r=client.get('http://subconverter:25500/sub?target=singbox', params={'url': suburl})
		r=r.json()
		return r

	def convert(self, suburl, config):
		template=yaml.safe_load(config)

		r=self.__getsub(suburl)
		outbounds=[i for i in r['outbounds'] if not i['type'] in ['direct','block','dns','selector','urltest']]
		tags=[i['tag'] for i in outbounds]

		for index, outbound in enumerate(template['outbounds']):
			if 'outbounds-regex' in outbound:
				regex=outbound['outbounds-regex']
				template['outbounds'][index]['outbounds']=[tag for tag in tags if re.match(regex, tag)]
				del template['outbounds'][index]['outbounds-regex']
			elif outbound['type'] in ['selector', 'urltest']:
				template['outbounds'][index]['outbounds']+=tags

		template['outbounds']+=outbounds

		return json.dumps(template)

	def close(self):
		self.client.close()
