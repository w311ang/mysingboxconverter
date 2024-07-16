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
	sub = request.args.get('sub')
	configurl = request.args.get('config', 'https://w311ang.github.io/my_singbox_template/index.yml')

	with httpx.Client() as client:
		config=client.get(configurl).text
	return converter.convert(sub, config)
