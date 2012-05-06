#!/usr/bin/env python
# -*- coding: utf-8 -*-
import datetime
import subprocess

KEEP = 7  # number od days to keep
BACKUP_DIR = '/home/{{ user }}/dbs'
IGNORE_DBS = (
    'template0',
    'template1',
    'template_postgis',
    'postgres',
)


def run(command):
    """
    Runs a command.
    Returns stdout if sucess, stderr if failure.
    """
    result = subprocess.Popen(command, shell=True,
                              stdout=subprocess.PIPE)
    out, err = result.communicate()
    if err is not None:
        return err
    return out


def dbs():
    yesterday = datetime.datetime.today() - datetime.timedelta(days=1)
    yesterday = yesterday.strftime('%Y-%m-%d')
    backup_dir = '%s/%s' % (BACKUP_DIR, yesterday)
    run('mkdir -p %s' % backup_dir)

    db_list = run('psql -U postgres -l')
    for line in db_list.split('\n')[3:-3]:
        line = line[1:]
        if line.startswith(' '):
            continue
        db_name = line.split()[0]
        if db_name in IGNORE_DBS:
            continue

        file_name = '%s-%s.sql.gz' % (db_name, yesterday)
        cmd = 'pg_dump -U postgres %s | gzip > %s/%s' % (db_name, backup_dir,
                                                         file_name)
        run(cmd)

    old_dirs = run('ls %s' % BACKUP_DIR).strip().split('\n')[:-KEEP]
    for old_dir in old_dirs:
        run('rm -rf %s/%s' % (BACKUP_DIR, old_dir))


if __name__ == '__main__':
    dbs()
