FROM python:2.7-alpine3.8

LABEL Name=cost-calculator Version=0.0.1

WORKDIR /app
ADD . /app

RUN python3 -m pip install -r requirements.txt 

ENTRYPOINT [ "python3","/app/main.py" ]

