from flask import Flask
from flask import request
import httpx
import singboxconverter
import atexit
import json

app = Flask(__name__)
converter=singboxconverter.converter()
atexit.register(lambda: converter.close())

@app.route("/")
def root():
	params_dict = request.args.to_dict(flat=False)
	subs = params_dict.pop('sub')
	configurl = params_dict.pop('config', 'https://w311ang.github.io/my_singbox_template/index.yml')
	for param_key, param_value in params_dict.items():
		try:
			params_dict[param_key]=json.loads(param_value)
		except json.decoder.JSONDecodeError:
			params_dict[param_key]=param_value

	subs=[sub.split(',') in subs]
	subconfig=[
		{
			'suburl': params[0],
			'is_sing_box_format': bool(int(params[1])) if len(params) >= 2 else False,
			'include_all_outbounds': bool(int(params[2])) if len(params) >= 3 else False
		} for config in subs
	]

	if request.args.get('debug', 'false') == 'true':
		debug = True
	else:
		debug = False

	with httpx.Client() as client:
		config=client.get(configurl).text
	return converter.convert(subconfig, config, subs_params=subs_params, debug=debug)
