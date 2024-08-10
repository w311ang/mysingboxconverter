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
	singbox_subs_index = map(int, request.args.get('singbox_subs_index', '').split(','))

	subconfig = [
		{
			'suburl': suburl,
			'is_sing_box_format': True if index in singbox_subs_index else False
		} for index, suburl in enumerate(subs)
	]

	if request.args.get('debug', 'false') == 'true':
		debug = True
	else:
		debug = False

	with httpx.Client() as client:
		config=client.get(configurl).text
	return converter.convert(subconfig, config, debug=debug)
