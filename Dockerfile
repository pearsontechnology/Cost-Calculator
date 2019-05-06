FROM python:2.7

LABEL Name=cost-calculator Version=0.0.1

WORKDIR /app
ADD . /app

RUN python -m pip install -r requirements.txt
CMD ["python", "/app/main.py"]

