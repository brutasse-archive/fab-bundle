import os

from io import BytesIO

from fabric.api import task, env, run, local, put, cd, sudo
from fabric.contrib.files import exists

from .utils import die, err, yay, template


@task()
def deploy(force_version=None):
    """Deploys to the current bundle"""
    bundle_name = env.http_host
    bundle_root = '{0}/{1}'.format(
        env.get('bundle_root', run('pwd') + '/bundles'),
        bundle_name,
    )
    env.bundle_root = bundle_root
    run('mkdir -p %s/{log,conf,public}' % bundle_root)

    # virtualenv, Packages
    if not exists(bundle_root + '/env'):
        run('virtualenv --no-site-packages {0}/env'.format(bundle_root))
    run('{0}/env/bin/pip install -U pip'.format(bundle_root))

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
    requirement = '{0}=={1}'.format(dist_name, version)

    packages = env.bundle_root + '/packages'
    run('mkdir -p {0}'.format(packages))
    if not exists('{0}/{1}'.format(packages, dist)):
        put('dist/{0}'.format(dist), '{0}/{1}'.format(packages, dist))

    has_vendor = 'vendor' in os.listdir(os.getcwd())
    if has_vendor:
        local_files = set(os.listdir(os.path.join(os.getcwd(), 'vendor')))
        uploaded = set(run('ls {0}'.format(packages)).split())
        diff = local_files - uploaded
        for file_name in diff:
            put('vendor/{0}'.format(file_name),
                '{0}/{1}'.format(packages, file_name))

    freeze = run('{0}/env/bin/pip freeze'.format(bundle_root)).split()
    if requirement in freeze and force_version is None:
        die("{0} is already deployed. Increment the version number to deploy "
            "a new release.".format(requirement))

    cmd = ('{0}/env/bin/pip install -U {1} gunicorn gevent greenlet '
           'setproctitle --find-links file://{2}'.format(
               bundle_root, requirement, packages,
           ))
    if 'index_url' in env:
        cmd += ' --index-url {0}'.format(env.index_url)
    run(cmd)
    env.path = bundle_root

    manage_envdir(bundle_root)

    if not 'staticfiles' in env:
        env.staticfiles = True
    if not 'cache' in env:
        env.cache = 0  # redis DB

    # Do we have a DB?
    result = run('psql -U postgres -l|grep UTF8')
    if bundle_name not in result:
        if 'gis' in env and env.gis is False:
            db_template = 'template0'
        else:
            db_template = 'template_postgis'
        run('createdb -U postgres -T {0} -E UTF8 {1}').format(db_template,
                                                              bundle_name)

    if 'migrations' in env:
        if env.migrations != 'nashvegas':
            die("{0} is not supported for migrations.".format(env.migrations))
        manage('upgradedb -l', noinput=False)  # This creates the migration
                                               # tables

        installed = run('psql -U postgres {0} -c "select id from '
                        'nashvegas_migration limit 1;"'.format(bundle_name))
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
    if not 'workers' in env:
        env.workers = 2
    changed = template('supervisor.conf',
                       '%s/conf/supervisor.conf' % bundle_root)
    with cd('/etc/supervisor/conf.d'):
        sudo('ln -sf %s/conf/supervisor.conf %s.conf' % (bundle_root,
                                                         bundle_name))

    if 'rq' in env and env.rq:
        changed = True  # Always supervisorctl update

        # RQ forks processes and they load the latest version of the code.
        # No need to restart the worker **unless** RQ has been updated (TODO).
        for worker_id in range(env.rq['workers']):
            env.worker_id = worker_id
            template(
                'rq.conf', '%s/conf/rq%s.conf' % (bundle_root, worker_id),
            )
            with cd('/etc/supervisor/conf.d'):
                sudo('ln -sf %s/conf/rq%s.conf %s_worker%s.conf' % (
                    bundle_root, worker_id, bundle_name, worker_id,
                ))

        # Scale down workers if the number decreased
        names = '/etc/supervisor/conf.d/{0}_worker*.conf'.format(bundle_name)
        workers = run('ls {0}'.format(names))
        workers_conf = run('ls {0}/conf/rq*.conf'.format(bundle_root))
        to_delete = []
        for w in workers.split():
            if int(w.split('{0}_worker'.format(bundle_name),
                           1)[1][:-5]) >= env.rq['workers']:
                to_delete.append(w)
        for w in workers_conf.split():
            if int(w.split(bundle_name, 1)[1][8:-5]) >= env.rq['workers']:
                to_delete.append(w)
        if to_delete:
            sudo('rm {0}'.format(" ".join(to_delete)))

    if changed:
        sudo('supervisorctl update')
    run('kill -HUP `pgrep gunicorn`')

    # All set, user feedback
    ip = run('curl http://ifconfig.me/')
    dns = run('nslookup {0}'.format(env.http_host))
    if ip in dns:
        proto = 'https' if 'ssl_cert' in env else 'http'
        yay("Visit {0}://{1}".format(proto, env.http_host))
    else:
        err("Deployment successful but make sure {0} points to {1}".format(
            env.http_host, ip))


@task()
def destroy():
    """Destroys the current bundle"""
    pass


def manage_envdir(bundle_root):
    # Envdir configuration
    if not 'env' in env:
        env.env = {}
    if not 'MEDIA_ROOT' in env.env:
        env.env['MEDIA_ROOT'] = bundle_root + '/public/media'
    if not 'STATIC_ROOT' in env.env:
        env.env['STATIC_ROOT'] = bundle_root + '/public/static'

    envdir = bundle_root + '/envdir'
    run('mkdir -p {0}'.format(envdir))

    delete = set(run('ls {0}'.format(envdir)).split()) - set(env.env.keys())
    if delete:
        run('rm {0}'.format(
            ' '.join('{0}/{1}'.format(envdir, key) for key in delete)))

    for name, value in env.env.items():
        path = '{0}/{1}'.format(envdir, name)
        put(BytesIO(value), path)


def manage(command, noinput=True):
    """Runs a management command"""
    noinput = '--noinput' if noinput else ''
    run('envdir {bundle_root}/envdir {bundle_root}/env/bin/django-admin.py '
        '{command} {noinput}'.format(bundle_root=env.bundle_root,
                                     command=command, noinput=noinput))
