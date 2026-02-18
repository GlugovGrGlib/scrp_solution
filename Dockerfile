FROM public.ecr.aws/lambda/python:3.12

COPY pyproject.toml ./
RUN pip install --no-cache-dir .

COPY core/ ./core/
COPY stt/ ./stt/
COPY settings.toml ./

CMD ["stt.handler.handler"]
