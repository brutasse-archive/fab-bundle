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
    run('%s/env/bin/pip install -U pip' % bundle_root)

    local('python setup.py sdist')
    dists = [
        d for d in os.listdir(os.path.join(os.getcwd(),
                                           'dist')) if d.endswith('.tar.gz')
    ]
    version_string = lambda d: d.rsplit('-', 1)[1][:-7]
    def int_or_s(num):
        try:
            return int(num)
        except ValueError:
            return num
    dist = sorted(dists, key=lambda d: map(int_or_s,
                                           version_string(d).split('.')))[-1]
    version = force_version or version_string(dist)
    dist_name = dist.rsplit('-', 1)[0]
    requirement = '%s==%s' % (dist_name, version)

    packages = env.bundle_root + '/packages'
    run('mkdir -p %s' % packages)
    if not exists('%s/%s' % (packages, dist)):
        put('dist/%s' % dist, '%s/%s' % (packages, dist))

    # TODO: vendor/ packages
    freeze = run('%s/env/bin/pip freeze' % bundle_root).split()
    if requirement in freeze and force_version is None:
        die("%s is already deployed. Increment the version number to deploy "
            "a new release." % requirement)

    cmd = '%s/env/bin/pip install -U %s gunicorn --find-links file://%s' % (
        bundle_root, requirement, packages
    )
    if 'index_url' in env:
        cmd += ' --index-url %(index_url)s' % env
    run(cmd)
    env.path = bundle_root
    python = run('ls %s/env/lib' % bundle_root)
    template(
        'path_extension.pth',
        '%s/env/lib/%s/site-packages/_virtualenv_path_extensions.pth' % (
            bundle_root, python
        ),
    )

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
        if 'gis' in env and env.gis is False:
            db_template = 'template0'
        else:
            db_template = 'template_postgis'
        run(('createdb -U postgres -T %s '
             '-E UTF8 %s') % (db_template, bundle_name))

    if 'migrations' in env:
        if env.migrations != 'nashvegas':
            die("%s is not supported for migrations." % env.migrations)
        manage('upgradedb -l', noinput=False)  # This creates the migration
                                               # tables

        installed = run('psql -U postgres %s -c "select id from '
                        'nashvegas_migration limit 1;"' % bundle_name)
        installed = '0 rows' not in installed
        if installed:
            manage('upgradedb -e', noinput=False)
        else:
            # 1st deploy, force syncdb and seed migrations.
            manage('syncdb')
            manage('upgradedb -s', noinput=False)
    else:
        manage('syncdb')

    if env.staticfiles:
        manage('collectstatic')

    # Some things don't like dots
    env.app = env.http_host.replace('.', '')

    # Cron tasks
    if 'cron' in env:
        template('cron', '%(bundle_root)s/conf/cron' % env, use_sudo=True)
        sudo('chown root:root %(bundle_root)s/conf/cron' % env)
        sudo('chmod 644 %(bundle_root)s/conf/cron' % env)
        sudo('ln -sf %(bundle_root)s/conf/cron /etc/cron.d/%(app)s' % env)
    else:
        # Make sure to deactivate tasks if the cron section is removed
        sudo('rm -f %(bundle_root)s/conf/cron /etc/cron.d/%(app)s' % env)

    # Log rotation
    logrotate = '/etc/logrotate.d/%(app)s' % env
    template('logrotate', logrotate, use_sudo=True)
    sudo('chown root:root %s' % logrotate)

    # Nginx vhost
    changed = template('nginx.conf', '%s/conf/nginx.conf' % bundle_root)
    with cd('/etc/nginx/sites-available'):
        sudo('ln -sf %s/conf/nginx.conf %s.conf' % (bundle_root,
                                                    env.http_host))
    with cd('/etc/nginx/sites-enabled'):
        sudo('ln -sf ../sites-available/%s.conf' % env.http_host)
    if 'ssl_cert' in env and 'ssl_key' in env:
        put(env.ssl_cert, '%s/conf/ssl.crt' % bundle_root)
        put(env.ssl_key, '%s/conf/ssl.key' % bundle_root)
    if changed:  # TODO detect if the certs have changed
        sudo('/etc/init.d/nginx reload')

    # Supervisor task(s) -- gunicorn + rq
    changed = template('supervisor.conf',
                       '%s/conf/supervisor.conf' % bundle_root)
    with cd('/etc/supervisor/conf.d'):
        sudo('ln -sf %s/conf/supervisor.conf %s.conf' % (bundle_root,
                                                         bundle_name))
    if changed:
        sudo('supervisorctl update')
    run('kill -HUP `pgrep gunicorn`')

    # All set, user feedback
    ip = run('curl http://ifconfig.me/')
    dns = run('nslookup %s' % env.http_host)
    if ip in dns:
        proto = 'https' if 'ssl_cert' in env else 'http'
        yay("Visit %s://%s" % (proto, env.http_host))
    else:
        err("Deployment successful but make sure %s points to %s" % (
            env.http_host, ip))


@task()
def destroy():
    """Destroys the current bundle"""
    pass


def manage(command, noinput=True):
    """Runs a management command"""
    noinput = '--noinput' if noinput else ''
    run('%s/env/bin/django-admin.py %s %s --settings=settings' % (
        env.bundle_root, command, noinput,
    ))
