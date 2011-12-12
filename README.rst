Fab-bundle
==========

A standard stack for Django, using python packaging and Fabric for single-line
deployments on Debian machines.

Stack
-----

* Python (duh)
* PostgreSQL
* Redis (celery tasks, cache backend)
* Gunicorn
* Supervisor
* Nginx
* SSL
* Sentry, using a remote sentry server
* GIS-ready by default
  
HTTPS is enabled and enforced. Standard HTTP is not supported, this is a
feature. If you run several bundles on the same server, SNI is good enough.

Usage
-----

* Package your django project, you should be able to pip install it from a
  private location. Your package should contain base default settings that
  ``fab-bundle`` will *extend*, for instance in
  ``project/default_settings.py``.

* Put your private requirements (if any) into a ``vendor/`` directory, as
  python packages.

::

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
        env.ssl_cert = '/path/to/ssl_cert.crt'
        env.ssl_key = '/path/to/ssl_cert_key.key'

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

Should you ever need a plain shell, do::

    fab production ssh

Configuration
-------------

Bundle location
```````````````

Bundles are put in ``$HOME/bundles`` by default. To change this, put

Sentry
``````

You can use Sentry in remote mode, by adding this to the ``env`` object::

    def production():
        # ...
        env.sentry = {
            'key': 'your private secret sentry key',
            'url': 'https://sentry.example.com/store/',
        }

Make sure your project itself is configured with ``raven`` or
``sentry.client``.

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

You can also set the ``'tls'``, ``'port'`` and ``'backend'`` keys. You can use
localhost if you want, ``postfix`` is installed.

Migrations
``````````

Only Nashvegas is currently supported.

::

    def production():
        # ...
        env.migrations = 'nashvegas'

Staticfiles
```````````

They're enabled by default. To disable them::

    def production():
        # ...
        env.staticfiles = False

Cron tasks
``````````

The ``session_cleanup`` task is enabled by default if your project uses
sessions. To add more tasks::

    def production():
        # ...
        env.cron = (
            '*/30 * * * * MANAGEMENT_COMMAND command_name',
            '*/10 * * * * /path/to/stuff/to/do',
        )

If you need to run a management command, just put ``MANAGEMENT_COMMAND``
followed by your command name and options and it'll be translated to a full
``django-admin.py`` command.

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

Rolling back
------------

Had a bad deploy? It happens. Rollback to a previous version, let's say 1.2::

    fab production deploy:1.2

Cleaning up
-----------

Want to remove your app? This will remove everything related to your bundle::

    fab production destroy
