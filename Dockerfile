FROM python:3
WORKDIR /usr/src/django-ca

COPY requirements.txt ./
COPY ca/ ca/
COPY docker/localsettings.py ca/ca/
RUN pip install --no-cache-dir -r requirements.txt uwsgi
RUN mkdir -p /var/lib/django-ca/ /usr/share/django-ca/
RUN groupadd -r django-ca && useradd --no-log-init -r -g django-ca django-ca
RUN chown django-ca:django-ca /var/lib/django-ca/

# Collect static files
RUN python ca/manage.py collectstatic --noinput

# Cleanup 
RUN find ca | grep pyc$ | xargs rm
RUN find ca -type d -name __pycache__ | xargs rmdir
RUN rm -f ca/ca/test_settings.py

CMD python ca/manage.py migrate --noinput && uwsgi --static-map /static=/usr/share/django-ca --chdir=ca --http :8000 --module ca.wsgi

USER django-ca
EXPOSE 8000
VOLUME /var/lib/django-ca /etc/django-ca
VOLUME ["/etc/django-ca/", "/var/lib/django-ca/"]
