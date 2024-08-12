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
	templateurl = params_dict.pop('config', ['https://w311ang.github.io/my_singbox_template/index.yml'])[0]
	debug = True if params_dict.pop('debug', ['false'])[0] == 'true' else False
	for param_key, param_value in params_dict.items():
		param_value=param_value[0]
		if not param_value:
			del params_dict[param_key]
			continue
		try:
			params_dict[param_key]=json.loads(param_value)
		except json.decoder.JSONDecodeError:
			params_dict[param_key]=param_value.split(',') if ',' in param_value else param_value

	subs=[sub.split(',') for sub in subs]
	subconfig=[
		{
			'suburl': sub[0],
			'is_sing_box_format': bool(int(sub[1])) if len(sub) >= 2 else False,
			'include_all_outbounds': bool(int(sub[2])) if len(sub) >= 3 else False
		} for sub in subs
	]

	with httpx.Client() as client:
		template=client.get(templateurl).text
	return converter.convert(subconfig, template, params_config=params_dict, debug=debug)
