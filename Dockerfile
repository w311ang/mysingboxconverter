FROM python:3.12.4
WORKDIR /app
COPY . /app
RUN pip install --upgrade pip
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
CMD ["flask", "--app", "singboxconverter_flask", "--debug", "run", "--host", "0.0.0.0"]
