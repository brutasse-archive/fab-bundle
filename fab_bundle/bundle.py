import os

from fabric.api import task, env, run, local, put, cd, sudo
from fabric.contrib.files import exists

from .utils import die, err, yay, template


@task()
def deploy(force_version=None):
    """Deploys to the current bundle"""
    bundle_name = env.http_host
    bundle_root = '%s/%s' % (env.get('bundle_root', run('pwd') + '/bundles'),
                             bundle_name)
    env.bundle_root = bundle_root
    run('mkdir -p %s/{log,conf,public}' % bundle_root)

    # virtualenv, Packages
    if not exists(bundle_root + '/env'):
        run('virtualenv --no-site-packages %s/env' % bundle_root)

    local('python setup.py sdist')
    dists = os.listdir(os.path.join(os.getcwd(), 'dist'))
    dist = [d for d in sorted(dists) if d.endswith('.tar.gz')][-1]
    version = force_version or dist.split('-')[-1][:-7]
    requirement = dist.replace('-%s.tar.gz' % version, '==%s' % version)
    print requirement

    run('mkdir -p packages')
    if not exists('packages/%s' % dist):
        put('dist/%s' % dist, 'packages/%s' % dist)

    # TODO: vendor/ packages
    freeze = run('%s/env/bin/pip freeze' % bundle_root).split()
    if requirement in freeze and force_version is None:
        die("%s is already deployed. Increment the version number to deploy "
            "a new release." % requirement)

    cmd = '%s/env/bin/pip install %s gunicorn --find-links file://%s' % (
        bundle_root, requirement, run('pwd') + '/packages'
    )
    if 'index_url' in env:
        cmd += ' --index-url %(index_url)s' % env
    run(cmd)
    env.path = bundle_root
    python = run('ls %s/env/lib' % bundle_root)
    template('path_extension.pth',
             '%s/env/lib/%s/site-packages/_virtualenv_path_extensions.pth' % (
                 bundle_root, python
             ))

    env.media_root = bundle_root + '/public/media'
    env.static_root = bundle_root + '/public/static'
    if not 'staticfiles' in env:
        env.staticfiles = True
    if not 'cache' in env:
        env.cache = 0  # redis DB
    template('settings.py', '%s/settings.py' % bundle_root)
    template('wsgi.py', '%s/wsgi.py' % bundle_root)

    # Do we have a DB?
    result = run('psql -U postgres -l|grep UTF8')
    if bundle_name not in result:
        run(('createdb -U postgres -T template_postgis '
             '-E UTF8 %s') % bundle_name)

    if 'migrations' in env and env.migrations == 'nashvegas':
        # TODO run some migrations
        pass
    manage('syncdb')
    if env.staticfiles:
        manage('collectstatic')

    # TODO: session_cleanup command
    # TODO: cron tasks

    # Nginx vhost
    env.app = env.http_host.replace('.', '')
    template('nginx.conf', '%s/conf/nginx.conf' % bundle_root)
    with cd('/etc/nginx/sites-available'):
        sudo('ln -sf %s/conf/nginx.conf %s.conf' % (bundle_root,
                                                    env.http_host))
    with cd('/etc/nginx/sites-enabled'):
        sudo('ln -sf ../sites-available/%s.conf' % env.http_host)
    put(env.ssl_cert, '%s/conf/ssl.crt' % bundle_root)
    put(env.ssl_key, '%s/conf/ssl.key' % bundle_root)
    sudo('/etc/init.d/nginx reload')

    # Supervisor task(s) -- gunicorn + celeryd
    template('supervisor.conf', '%s/conf/supervisor.conf' % bundle_root)
    with cd('/etc/supervisor/conf.d'):
        sudo('ln -sf %s/conf/supervisor.conf %s.conf' % (bundle_root,
                                                         bundle_name))
    sudo('supervisorctl update')
    run('kill -HUP `pgrep gunicorn`')

    # All set, user feedback
    ip = run('curl http://ifconfig.me/')
    dns = run('nslookup %s' % env.http_host)
    if ip in dns:
        yay("Visit https://%s" % env.http_host)
    else:
        err("Deployment successful but make sure %s points to %s" % (
            env.http_host, ip))


@task()
def destroy():
    """Destroys the current bundle"""
    pass


def manage(command):
    """Runs a management command"""
    run('%s/env/bin/django-admin.py %s --noinput --settings=settings' % (
        env.bundle_root, command,
    ))