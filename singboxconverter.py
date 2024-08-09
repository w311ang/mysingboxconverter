import httpx
import json
import yaml
from cachetools import cached, TTLCache
import re
from copy import deepcopy

class converter:
	client=httpx.Client()

	@cached(cache=TTLCache(maxsize=1024, ttl=3600))
	def __getsub(self, suburl):
		client=self.client
		r=client.get('http://subconverter:25500/sub?target=singbox', params={'url': suburl})
		r=r.json()
		return r

	def convert(self, suburl, config, debug=False):
		def removed_key(d, key):
			d=dict(d)
			del d[key]
			return d

		template=yaml.safe_load(config)

		if debug:
			template['log']['level']='debug'

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

		dns_servers_modded=[]
		for server in template['dns']['servers']:
			if (not 'strategy' in server) or server['strategy']!='ipv4_only':
				dns_servers_modded.append(server)
				continue

			server_prefer_ipv4=dict(server)
			server_prefer_ipv4['tag']+='-prefer_ipv4'
			del server_prefer_ipv4['strategy']
			dns_servers_modded.append(server_prefer_ipv4)
			dns_servers_modded.append(server)

		dns_rules_modded=[]
		for rule in template['dns']['rules']:
			if 'outbound' in rule:
				dns_rules_modded.append(rule)
				continue
			server=[server for server in template['dns']['servers'] if server['tag']==rule['server']][0]
			if (not 'strategy' in server) or server['strategy']!='ipv4_only':
				dns_rules_modded.append(rule)
				continue

			rule_prefer_ipv4={
				'type': 'logical',
				'mode': 'and',
				'rules': [
					{
						'inbound': 'mixed-in'
					},
					removed_key(rule, 'server')
				],
				'server': rule['server']+'-prefer_ipv4'
			}
			rule_ipv4_only=deepcopy(rule_prefer_ipv4)
			rule_ipv4_only['rules'][0]['invert']=True
			rule_ipv4_only['server']=rule['server']
			dns_rules_modded.append(rule_prefer_ipv4)
			dns_rules_modded.append(rule_ipv4_only)
		template['dns']['servers']=dns_servers_modded
		template['dns']['rules']=dns_rules_modded

		return json.dumps(template)

	def close(self):
		self.client.close()
