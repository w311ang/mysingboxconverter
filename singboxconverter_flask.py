from flask import Flask
from flask import request
import httpx
import singboxconverter
import atexit

app = Flask(__name__)
converter=singboxconverter.converter()
atexit.register(lambda: converter.close())

@app.route("/")
def root():
	subs = request.args.getlist('sub')
	configurl = request.args.get('config', 'https://w311ang.github.io/my_singbox_template/index.yml')

	subconfig=[]
	for config in subs:
		params = config.split(',')
		suburl = params[0]
		is_sing_box_format = bool(int(params[1])) if len(params) >= 2 else False
		subconfig.append({
			'suburl': suburl,
			'is_sing_box_format': is_sing_box_format
		})

	if request.args.get('debug', 'false') == 'true':
		debug = True
	else:
		debug = False

	with httpx.Client() as client:
		config=client.get(configurl).text
	return converter.convert(subconfig, config, debug=debug)
