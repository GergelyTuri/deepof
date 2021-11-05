FROM continuumio/anaconda3:latest
COPY Pipfile .
COPY Pipfile.lock .
RUN apt-get --allow-releaseinfo-change update \
 && apt-get install -y --no-install-recommends libgl1-mesa-dev \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir pipenv
RUN pipenv install --python=3.8.12 --dev --system --ignore-pipfile
CMD [ "/bin/bash" ]
