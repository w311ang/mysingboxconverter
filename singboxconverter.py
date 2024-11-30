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
			r=client.get('http://127.0.0.1:25500/sub?target=singbox', params={'url': suburl})
			r=r.json()
		return r

	def convert(self, subconfig: list[dict], template, params_config={}, debug=False):
		def removed_key(d, key):
			d=dict(d)
			del d[key]
			return d

		def applied_params(data, params):
			if isinstance(data, dict):
				return {k: applied_params(v, params) for k, v in data.items()}
			elif isinstance(data, list):
				return [applied_params(item, params) for item in data]
			elif isinstance(data, str):
				param_request=re.match('%((?!%).+)%(.*)', data)
				if param_request:
					param_key, default=param_request.groups()
					try:
						default=json.loads(default)
					except json.decoder.JSONDecodeError:
						pass
					if param_key in params:
						return params[param_key]
					else:
						assert default != '', 'value of param not found and default is empty'
						return default
				else:
					return data
			else:
				return data

		template=applied_params(yaml.safe_load(template), params_config)
		assert type(template) != str, 'Invalid YAML format'

		if debug:
			template['log']['level']='debug'

		outbounds=template['outbounds']
		for config in subconfig:
			suburl=config['suburl']
			is_sing_box_format=config['is_sing_box_format']
			r=applied_params(self.__getsub(suburl, is_sing_box_format=is_sing_box_format), params_config)
			config['cache']=r
			include_all_outbounds=config['include_all_outbounds']
			for new_outbound in r['outbounds']:
				if include_all_outbounds and new_outbound['type'] == 'selector':
					outbounds.insert(outbounds.index('%%新订阅select添加处%%'), new_outbound)

		for config in subconfig:
			is_sing_box_format=config['is_sing_box_format']
			include_all_outbounds=config['include_all_outbounds']

			r=config['cache']
			use_Proxies_instead_of_select = r.get('custom_config', {}).get('use_Proxies_instead_of_select', False) if is_sing_box_format else False

			for new_outbound in r['outbounds']:
				if (not include_all_outbounds) and (not new_outbound['type'] in ['direct','block','dns','selector','urltest']):
					outbounds.append(new_outbound)
				elif include_all_outbounds and new_outbound['type'] != 'selector':
					outbounds.append(new_outbound)
				if not new_outbound['type'] in ['direct','block','dns','selector','urltest']:
					for outbound in outbounds:
						if outbound == '%%新订阅select添加处%%' or not outbound['type'] in ['selector', 'urltest']:
							continue
						if use_Proxies_instead_of_select and outbound['tag'] in ['select', 'auto']:
							continue
						elif (not use_Proxies_instead_of_select) and outbound['tag'] in ['Proxies', 'auto-Proxies']:
							continue
						if 'outbounds-regex' in outbound:
							outbound['outbounds']=[] if not 'outbounds' in outbound else outbound['outbounds']
							if re.match(outbound['outbounds-regex'], new_outbound['tag']):
								outbound['outbounds'].append(new_outbound['tag'])
						elif not ('detour' in new_outbound and outbound['tag'] == new_outbound['detour']):
							outbound['outbounds'].append(new_outbound['tag'])

		outbounds.remove('%%新订阅select添加处%%')
		for outbound in outbounds:
			outbound.pop('outbounds-regex', None)
			if 'outbounds' in outbound and outbound['outbounds'] == []:
				outbound['outbounds']=['block']

		# ~~修复当mixed-in(domain_strategy为prefer_ipv4)传入一次请求后，该请求解析的域名的缓存也将刷新为prefer_ipv4的，在tun-in再请求一次aaaa就会发现没有走ipv4_only反而响应了ipv6~~
		# 目前是为了防止ipv4_only的mixed-in的解析缓存影响到tun-in的无ipv4_only(国内域名)解析
		# 解决方法就是让mixed-in的dns请求与tun-in的分开，分开缓存，不让mixed-in的刷新tun-in的就解决了
		dns_servers_modded=[]
		for server in template['dns']['servers']:
			if (not 'strategy' in server) or server['strategy']!='ipv4_only':
				dns_servers_modded.append(server)
				continue

			server_prefer_ipv4=dict(server)
			server_prefer_ipv4['tag']+='-mixed_in'
			del server_prefer_ipv4['strategy']
			dns_servers_modded.append(server_prefer_ipv4)
			dns_servers_modded.append(server)

		# 同上，是为了修复解析出ipv6问题
		dns_rules_modded=[]
		for rule in template['dns']['rules']:
			if ('outbound' in rule) or ('inbound' in rule):
				dns_rules_modded.append(rule)
				continue
			server=[server for server in template['dns']['servers'] if server['tag']==rule['server']]
			server=server[0] if len(server) >= 1 else {}
			if server=={} or (not 'strategy' in server) or server['strategy']!='ipv4_only':
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
				'server': rule['server']+'-mixed_in'
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
