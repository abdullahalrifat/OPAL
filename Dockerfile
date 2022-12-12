FROM permitio/opal-client:latest
WORKDIR /app/
COPY . ./
RUN python3 setup.py install --user