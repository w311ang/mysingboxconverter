import httpx
import json
import yaml
from cachetools import cached, TTLCache
import re
from copy import deepcopy

class converter:
	client=httpx.Client()

	@cached(cache=TTLCache(maxsize=1024, ttl=3600))
	def __getsub(self, suburl, is_sing_box_format=False):
		client=self.client
		if is_sing_box_format:
			r=client.get(suburl)
			r=yaml.safe_load(r.text)
			assert type(r) != str, 'Invalid YAML format'
		else:
			r=client.get('http://subconverter:25500/sub?target=singbox', params={'url': suburl})
			r=r.json()
		return r

	def convert(self, subconfig: list[dict], config, debug=False):
		def removed_key(d, key):
			d=dict(d)
			del d[key]
			return d

		template=yaml.safe_load(config)

		if debug:
			template['log']['level']='debug'

		outbounds=[]
		tags_config=[]
		for config in subconfig:
			is_sing_box_format=config['is_sing_box_format']
			suburl=config['suburl']
			include_all_outbounds=config['include_all_outbounds']
			r=self.__getsub(suburl, is_sing_box_format=is_sing_box_format)
			use_Proxies_instead_of_select = r.get('custom_config', {}).get('use_Proxies_instead_of_select', False) if is_sing_box_format else False
			filter_outbound_types=['direct','block','dns','selector','urltest']
			filtered_outbounds=[i for i in r['outbounds'] if not i['type'] in filter_outbound_types]
			if include_all_outbounds:
				outbounds+=r['outbounds']
			else:
				outbounds+=filtered_outbounds
			tags_config.append({
				'tags': [i['tag'] for i in filtered_outbounds],
				'use_Proxies_instead_of_select': use_Proxies_instead_of_select
			})

		template['outbounds']+=outbounds

		for config in tags_config:
			tags=config['tags']
			use_Proxies_instead_of_select=config['use_Proxies_instead_of_select']
			for index, outbound in enumerate(template['outbounds']):
				if use_Proxies_instead_of_select:
					if outbound['tag']=='select':
						continue
				else:
					if outbound['tag']=='Proxies':
						continue
				if 'outbounds-regex' in outbound:
					regex=outbound['outbounds-regex']
					template['outbounds'][index]['outbounds']=[tag for tag in tags if re.match(regex, tag)]
					del template['outbounds'][index]['outbounds-regex']
				elif outbound['type'] in ['selector', 'urltest']:
					template['outbounds'][index]['outbounds']+=tags

		# 修复当mixed-in(domain_strategy为prefer_ipv4)传入一次请求后，该请求解析的域名的缓存也将刷新为prefer_ipv4的，在tun-in再请求一次aaaa就会发现没有走ipv4_only反而响应了ipv6
		# 解决方法就是让mixed-in的dns请求与tun-in的分开，分开缓存，不让mixed-in的刷新tun-in的就解决了
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

		# 同上，是为了修复解析出ipv6问题
		dns_rules_modded=[]
		for rule in template['dns']['rules']:
			if ('outbound' in rule) or ('inbound' in rule):
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
