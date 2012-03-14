Fab-bundle
==========

A standard stack for Django, using python packaging and Fabric for single-line
deployments on Debian/Ubuntu machines.

A "bundle" is like an app on ep.io, or an instance on gondor.io. You can
deploy as many bundles as you want on a single machine.

This isn't intended for large-scale deployment but rather small sites fitting
on a single server (although you can scale vertically).

Almost everything here is implemented, a couple of things are still missing:

* Celery
* ``vendor/`` packages
* Bundle destruction
* Log rotation
* Daily DB snapshots
* Symlinks for easy backups

Stack
-----

* Python (duh)
* PostgreSQL
* Redis (celery tasks, cache backend)
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
  private location. Your package should contain base default settings that
  ``fab-bundle`` will *extend*, for instance in
  ``project/default_settings.py``.

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

        # Nginx
        env.http_host = 'foo.example.com'

        # Django
        env.base_settings = 'project.default_settings'
        env.secret_key = 'your private secret confidential key'

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

Bundle location
```````````````

Bundles are put in ``$HOME/bundles`` by default. To change this, set
``bundle_root``::

    def production():
        # ...
        env.bundle_root = '/var/www/bundles'

Sentry
``````

You can use Sentry in remote mode, by adding this to the ``env`` object::

    def production():
        # ...
        env.sentry_dsn = 'you sentry DSN'

Make sure your project itself is configured to use ``raven``.

Sending Email
`````````````

::

    def production():
        # ...
        env.email = {
            'from': 'Example <hi@example.com>',
            'host': 'smtp.example.com',
            'user': 'example',
            'password': 'yay',
        }

You can also set the ``'tls'``, ``'port'`` and ``'backend'`` keys.

Postgres version
````````````````

Fab-bundle will try to install postgres 9.1. If it's not available on your
system, you'll need to check which version you have, make sure you pick the
one that works with postgis as well::

    apt-cache search postgis

This outputs stuff like ``postgresql-8.4-postgis``. Then set::

    env.pg_version = '8.4'

Migrations
``````````

Only Nashvegas is currently supported.

::

    def production():
        # ...
        env.migrations = 'nashvegas'

Note that you need to provide the path to your migrations in
``NASHVEGAS_MIGRATIONS_DIRECTORY``, for instance in your base settings::

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
            ('*/30 * * * *', './env/bin/django-admin.py command_name --settings=settings'),
        )

Commands are run from your bundle root. This folder contains:

* the virtualenv in ``env/``
* the nginx, supervisor, etc config in ``conf/``
* the nginx and gunicorn logs in ``logs/``
* the static and media files in ``public/``
* the settings and wsgi files, ``settings.py`` and ``wsgi.py``

Private index server
````````````````````

If you have your own PyPI for deployments, you can point to it like this::

    def production():
        # ...
        env.index_url = 'https://login:pass@pypi.example.com/index'

Note that it will be passed to pip's ``--index-url`` argument, not
``--find-links`` or ``--extra-index-url`` so you need all your dependencies
here.

Celery tasks
````````````

Celery support (via Redis) is opt-in::

    def production():
        # ...
        env.celery = True

Custom settings
```````````````

If you need custom settings that are only suited to your production
environment, set them as a string in ``env.settings``::

    from textwrap import dedent

    def production():
        # ...
        env.settings = dedent("""
            REGISTRATION_OPEN = True
        """).strip()

Make sure there is no indentation, the code must be valid top-level python
code. Custom settings are appended to the default ones.

Cache number
````````````

If you have several bundles on the same server and they use cache, you may
want to specify the ID of the redis DB to use::

    env.cache = 1

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

Rolling back
------------

Had a bad deploy? It happens. Rollback to a previous version, let's say 1.2::

    fab production deploy:1.2

Cleaning up
-----------

Want to remove your app? This will remove everything related to your bundle::

    fab production destroy
