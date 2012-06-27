"""
Provisioning tasks
"""
from textwrap import dedent

from fabric.api import env, run, sudo, task, cd
from fabric.context_managers import settings
from fabric.contrib.files import exists

from .utils import template, mkdir, die, err, btw, yay


@task
def bootstrap():
    """Sets up a server to be a bundle container"""
    if env.user == 'root':
        run('apt-get update')
        run('apt-get install sudo')
        err("Please don't use root. I'll create a user for you.")
        name = raw_input("username: ")
        existing = run('cat /etc/passwd|cut -d":" -f1').split()
        if name not in existing:
            run('adduser --shell /bin/bash --home /home/%(user)s %(user)s' % {
                'user': name,
            })
        run('gpasswd -a %s sudo' % name)
        run('mkdir -p /home/%s/.ssh' % name)
        run('cp /root/.ssh/authorized_keys /home/%s/.ssh' % name)
        run('chown -R %s:%s /home/%s/.ssh' % (name, name, name))
        die("""Now please use %s as username and run the bootstrap task again.""" % name)

    btw("Configuring firewal...")
    iptables()
    btw("Installing and upgrading packages...")
    packages()
    pip()
    btw("Setting up postgres...")
    postgres()
    btw("Installing maintenance cron jobs")
    cron()
    btw("Enabling nginx and supervisor")
    nginx()
    supervisor()
    ip = run('curl http://ifconfig.me/')
    yay("Bundle container up and running at %s." % ip)


def iptables():
    """
    Makes sure only HTTP, HTTPS and SSH are available from the outside.
    """
    conf = '/home/%(user)s/conf' % env
    mkdir(conf)
    iptables_conf = conf + '/iptables.rules'
    changed = template('iptables.rules', iptables_conf)
    if changed:
        sudo('/sbin/iptables-restore --table=nat < %s' % iptables_conf)

    # Automate for reboots
    pre_up = '/etc/network/if-pre-up.d/iptables'
    if not exists(pre_up):
        template('iptables', pre_up, use_sudo=True)
    sudo('chmod +x %s' % pre_up)


def packages():
    """
    Installs all the required debian packages.
    """
    sudo('apt-get update')
    sudo('apt-get -y upgrade')
    if not 'pg_version' in env:
        env.pg_version = '9.1'
    packages = [
        'build-essential',
        'libjpeg62-dev',
        'libjpeg8',
        'libfreetype6',
        'libfreetype6-dev',
        'python-dev',
        'python-virtualenv',
        'libxml2-dev',
        'libxslt-dev',
        'libplist-utils',
        'dnsutils',
        'libevent-dev',

        'nginx',

        'supervisor',

        'libpq-dev',
        'postgresql',
        'postgresql-server-dev-%s' % env.pg_version,

        'redis-server',

        'curl',
    ]
    if 'gis' not in env or env.gis is not False:
        packages += [
            'postgis',
            'postgresql-%s-postgis' % env.pg_version,
            'gdal-bin',
            'libproj-dev',
            'libgeos-dev',
        ]
    sudo('apt-get -y install %s' % ' '.join(packages))

    # Fixes so that PIL recognizes the correct libraries. f7u12.
    for lib in ['libz', 'libjpeg', 'libfreetype']:
        if not exists('/usr/lib/%s.so' % lib):
            for source in ('/usr/lib/i386-linux-gnu/%s.so' % lib,
                           '/usr/lib/x86_64-linux-gnu/%s.so' % lib):
                if exists(source):
                    with cd('/usr/lib'):
                        sudo('ln -s %s .' % source)
                    break


def pip():
    run('mkdir -p .pip')
    template('pip.conf', '.pip/pip.conf')


def postgres():
    """
    Configures Postgres.
    """
    # Set up daily DB dumps
    run('mkdir -p dbs')
    run('mkdir -p bin')
    backup = '/home/%(user)s/bin/backup_dbs.py' % env
    template('backup_dbs.py', backup)
    run('chmod +x %s' % backup)

    pg_version = run('ls /etc/postgresql').split()[0]
    pg_hba = '/etc/postgresql/%s/main/pg_hba.conf' % pg_version

    changed = template('pg_hba.conf', pg_hba, use_sudo=True)
    if changed:
        btw("Updated pg_hba.conf, reloading postgres...")
        template('pg_hba.conf', pg_hba, use_sudo=True)
        sudo('/etc/init.d/postgresql restart')
    if 'gis' in env and env.gis is False:
        return
    templates = run('psql -U postgres -l|grep template')
    if 'template_postgis' in templates:
        return
    btw("Creating a spatial template...")
    path = run('pg_config --sharedir') + '/contrib/postgis-1.5'

    run('createdb -U postgres -E UTF8 template_postgis')
    run('createlang -U postgres -d template_postgis plpgsql || true')
    run('psql -U postgres -d postgres -c "UPDATE pg_database SET datistemplate=\'true\' WHERE datname=\'template_postgis\';"')
    run('psql -U postgres -d template_postgis -f %s/postgis.sql' % path)
    run('psql -U postgres -d template_postgis -f %s/spatial_ref_sys.sql' % path)
    run('psql -U postgres -d template_postgis -c "GRANT ALL ON geometry_columns TO PUBLIC;"')
    run('psql -U postgres -d template_postgis -c "GRANT ALL ON geography_columns TO PUBLIC;"')
    run('psql -U postgres -d template_postgis -c "GRANT ALL ON spatial_ref_sys TO PUBLIC;"')


def nginx():
    """
    Make sure nginx is started by default.
    """
    with settings(warn_only=True):
        res = sudo('/etc/init.d/nginx status')
        if 'could not access PID file' in res:
            sudo('/etc/init.d/nginx start')


def supervisor():
    """
    Make sure supervisor is started by default.
    """
    res = sudo('/etc/init.d/supervisor status || true')
    if 'not running' in res:
        sudo('/etc/init.d/supervisor start')


def cron():
    health_check = '/home/%(user)s/bin/check.py' % env
    template('check.py', health_check)
    run('chmod +x %s' % health_check)

    target = '/etc/cron.d/fabbundle'
    template('admincron', target, use_sudo=True)
    sudo('chown root:root %s' % target)
    sudo('chmod 644 %s' % target)
