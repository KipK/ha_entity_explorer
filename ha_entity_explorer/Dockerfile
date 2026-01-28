ARG BUILD_FROM
FROM $BUILD_FROM

# Install requirements for add-on
RUN \
  apk add --no-cache \
    python3 \
    py3-pip

# Copy data for add-on
COPY requirements.txt /tmp/
RUN pip3 install --no-cache-dir -r /tmp/requirements.txt

WORKDIR /app
COPY . /app

# Move run.sh to root and chmod
RUN cp /app/run.sh /run.sh && chmod a+x /run.sh

CMD [ "/run.sh" ]
