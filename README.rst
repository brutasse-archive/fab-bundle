Fab-bundle
==========

A standard stack for Django, using python packaging and Fabric for single-line
deployments on Debian/Ubuntu machines.

A "bundle" is like an app on ep.io, or an instance on gondor.io. You can
deploy as many bundles as you want on a single machine.

This isn't intended for large-scale deployment but rather small sites fitting
on a single server (although you can scale vertically).

Almost everything here is implemented, a couple of things are still missing:

* Bundle destruction

Stack
-----

* Python (duh)
* PostgreSQL
* Redis (RQ tasks, cache backend)
* Gunicorn
* Supervisor
* Nginx
* Sentry, using a remote sentry server
* GIS-ready by default
* HTTPS handling with A grade from ssllabs.com
* XSendfile support

Usage
-----

* Package your django project, you should be able to pip install it from a
  private location. Your package should be able to configure itself completely
  using environment variables.

* Put your private requirements (if any) into a ``vendor/`` directory, as
  python packages.

::

    pip install ssh
    pip install https://github.com/brutasse/fab-bundle/tarball/master#egg=fab-bundle

Create a ``fabfile.py`` file in your project root::

    from fab_bundle import env, task, bootstrap, deploy, destroy, ssh

    @task
    def production():
        """Use the production server"""
        # SSH login info
        env.user = 'bruno'
        env.hosts = ['example.com']
        env.key_filename = '/path/to/id_rsa'
        env.admin = 'email@example.com'

        # Nginx
        env.http_host = 'foo.example.com'

        # Django
        env.wsgi = 'project.wsgi:application'
        env.env = {
            'SECRET_KEY': 'production secret key',
            'DATABASE_URL': 'postgis://localhost:5432/example.com',
            '…': 'etc etc',
        }

Bootstrap the server setup::

    fab production bootstrap

Deploy your package::

    fab production deploy

This runs ``setup.py sdist``, uploads the package and its private requirements
to the server and updates or creates the bundle's environment and layout.

For subsequent deploys you don't need to run ``bootstrap`` again, although
doing so is harmless.

To deploy a specific version (for instance for rolling back), add your version
number as an argument::

    fab production deploy:1.1.2

Note that this will **not** re-upload the package if it's already been
uploaded.

Should you ever need a plain shell, do::

    fab production ssh

Configuration
-------------

Python requirements
```````````````````

You need to add the following packages to your environment:

* django-redis-cache
* psycopg2
* redis

Reporting
`````````

Every day you get an email with the load average, out-of-date packages and
disk space available on your machine. This email is sent to ``env.admin``::

    env.admin = 'email@example.com'

HTTPS
`````

Fab-bundle checks for the presence of ``ssl_key`` and ``ssl_cert`` in
``env``::

        env.ssl_cert = '/path/to/ssl_cert.crt'
        env.ssl_key = '/path/to/ssl_cert_key.key'

Just set them to local files on your machine and your site will be configured
to be HTTPS-only, with:

* HSTS support
* Secure session and CSRF cookies
* Permanent redirection from non-SSL to SSL requests
* HTTPS on static and media serving

Gunicorn
````````

Gunicorn uses the ``gevent`` worker class, ``gevent`` and ``greenlet`` will be
installed in your bundle virtualenv.

It also uses 2 workers by default. To change the number of workers, do::

    env.workers = 4

The WSGI entry point for gunicorn must be configured in ``env.wsgi``.

Bundle location
```````````````

Bundles are put in ``$HOME/bundles`` by default. To change this, set
``bundle_root``::

    def production():
        # ...
        env.bundle_root = '/var/www/bundles'

STATIC and MEDIA files
``````````````````````

You can configure your application to use the correct locations using the
``STATIC_ROOT`` and ``MEDIA_ROOT`` environment variables::

    STATIC_ROOT = os.environ['STATIC_ROOT']
    MEDIA_ROOT = os.environ['MEDIA_ROOT']

These locations are served under the ``/static/`` and ``/media/`` URLs,
respectively.

Sentry
``````

Set a ``SENTRY_DSN`` environment variable::

    env.env = {
        'SENTRY_DSN': 'https://…',
    }

Then use ``raven`` directly. By default raven looks for the environment
variable::

    from raven import Client
    client = Client()
    client.captureMessage(stuff)

Sending Email
`````````````

Expose your email configuration secrets as an environment variable::

    env.env = {
        'FROM_EMAIL': 'Example <hi@example.com>',
        'EMAIL_URL': 'smtp://user:password@host:587',
    }

Then make your application configure its email backend using that environment
variable.

Postgres
````````

Fab-bundle will try to install postgres 9.1. If it's not available on your
system, you'll need to check which version you have, make sure you pick the
one that works with postgis as well::

    apt-cache search postgis

This outputs stuff like ``postgresql-8.4-postgis``. Then set::

    env.pg_version = '8.4'

You will get daily DB backups in ``$HOME/dbs``, they're kept for 7 days and
then rotated, so it's up to you to back them up offsite if you need to.

To configure your application, set an environment variable::

    env.env = {
        'DATABASE_URL': 'postgis://postgres:@localhost/example.com',
    }

Then make your application configure its database backend using that
environment variable.

For each bundle, you get a database with the bundle's ``http_host`` as
database name.

Migrations
``````````

Only Nashvegas is currently supported.

::

    def production():
        # ...
        env.migrations = 'nashvegas'

Note that you need to provide the path to your migrations in
``NASHVEGAS_MIGRATIONS_DIRECTORY``, for instance in your settings::

    NASHVEGAS_MIGRATIONS_DIRECTORY = os.path.join(
        os.path.abspath(os.path.dirname(__file__)),
        'migrations',
    )

Staticfiles
```````````

They're enabled by default. To disable them::

    def production():
        # ...
        env.staticfiles = False

Cron tasks
``````````

To add scheduled tasks::

    def production():
        # ...
        env.cron = (
            ('*/30 * * * *', './env/bin/django-admin.py command_name'),
        )

Commands are run from your bundle root. This folder contains:

* the virtualenv in ``env/``
* the environment variables in ``envdir``
* the nginx, supervisor, etc config in ``conf/``
* the nginx, supervisor and gunicorn logs in ``log/``
* the static and media files in ``public/``
* the python packages in ``packages/``

Cron commands' stdout and stderr are appended to
``<bundle_root>/log/cron.log``.

Private index server
````````````````````

If you have your own PyPI for deployments, you can point to it like this::

    def production():
        # ...
        env.index_url = 'https://login:pass@pypi.example.com/index'

Note that it will be passed to pip's ``--index-url`` argument, not
``--find-links`` or ``--extra-index-url`` so you need all your dependencies
here.

RQ tasks
````````

`RQ`_ support is opt-in. You can set the number of workers like this::

    def production():
        # ...
        env.rq = {
            'workers': 1,
        }

.. _RQ: https://github.com/nvie/rq

You still need to specify the python requirements yourself. Note that the
``rqworker`` will use the redis database specified in ``env.cache``. You also
need to pass this number to your application using an environment variable and
configure the ``RQ`` setting::

    env.env = {
        'REDIS_URL': 'redis://localhost:6379/2',
    }

    RQ = {
        'db': int(urlparse.urlparse(os.environ['REDIS_URL']).path[1:]),
    }

Make sure you use the DB id from this setting when you enqueue new tasks.

Custom settings
```````````````

If you need custom settings, the pattern is the same as with email and
database settings: define environment variables and parse them in your
application's settings file.

XSendfile
`````````

Nginx has the ability to serve private files and leave your upstream server
decide whether the file should be served or not via a header. This is called
`XSendfile`_

.. _XSendfile: http://wiki.nginx.org/XSendfile

To make this work with fab-bundle, set env.xsendfile to the list of locations
you want to protect::

    env.xsendfile = [
        '/media/private/',
        '/media/other/',
    ]

Note that your ``MEDIA_ROOT`` is served under the ``/media/`` URL prefix.

Then in your view::

    response = HttpResponse(mimetype='application/octet-stream')
    response['X-Accel-Redirect'] = '/media/private/file-one.zip'
    return response

GIS
```

Fab-bundle installs the libraries required by geodjango and creates all the
databases from a spatial template. If you don't need this, you can disable GIS
support by setting ``env.gis``::

    env.gis = False

Rolling back
------------

Had a bad deploy? It happens. Rollback to a previous version, let's say 1.2::

    fab production deploy:1.2

Backing up
----------

Databases are dumped every day, you can sync them as well as your media files
using a script such as::

    #! /bin/sh
    mkdir -p log dbs
    DOMAIN="bundle_domain"
    HOST="ssh_host_address"
    RSYNC="rsync -avz -e ssh"
    $RSYNC $HOST:dbs/*/$DOMAIN* dbs
    $RSYNC $HOST:bundles/$DOMAIN/public/media .
    $RSYNC $HOST:bundles/$DOMAIN/log/*.gz log

Cleaning up
-----------

Want to remove your app? This will remove everything related to your bundle::

    fab production destroy
