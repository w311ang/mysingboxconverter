FROM python
WORKDIR /app
COPY . /app
RUN pip install --no-cache-dir -r requirements.txt
EXPOSE 5000
CMD ["flask", "--app", "singboxconverter_flask", "--debug", "run"]
