import os
import random
import re
import string
import sys
import unicodedata

from fabric.api import env, run, sudo, task
from fabric.colors import red, green, blue
from fabric.utils import abort
from fabric.contrib.files import upload_template, exists


def fyi(msg):
    """Debug info"""
    print >>sys.stderr, msg


def btw(msg):
    """Standard info"""
    print >>sys.stderr, blue(msg)


def yay(msg):
    """Success"""
    print >>sys.stderr, green(msg)


def err(msg):
    """Error"""
    print >>sys.stderr, red(msg, bold=True)


def die(msg):
    """Serious error"""
    abort(red(msg, bold=True))


def slugify(value):
    """
    Normalizes string, converts to lowercase, removes non-alpha characters,
    and removes spaces.
    """
    value = unicodedata.normalize('NFKD', value).encode('ascii', 'ignore')
    value = unicode(re.sub('[^\w\s-]', '', value).strip().lower())
    return re.sub('[-\s]+', '-', value)


def mkdir(directory, use_sudo=False):
    """
    Creates a directory if it doesn't exist.
    """
    cmd = sudo if use_sudo else run
    cmd('mkdir -p ' + directory)


def template(source, destination, use_sudo=False):
    """
    Uploads a Jinja template with env as context, and returns True
    if the file has changed.
    """
    here = os.path.abspath(os.path.dirname(__file__))
    template_dir = os.path.join(here, 'templates')

    new_file = not exists(destination, use_sudo=use_sudo)

    if not new_file:
        chars = [random.choice(string.ascii_letters) for i in range(5)]
        final_destination = destination
        destination = '/tmp/%s' % "".join(chars)
    upload_template(source, destination, context=env, backup=False,
                    use_jinja=True, template_dir=template_dir,
                    use_sudo=use_sudo)
    if new_file:
        return True

    cmd = sudo if use_sudo else run
    out = cmd('diff -u %s %s || true' % (final_destination, destination))
    if out:
        cmd('mv %s %s' % (destination, final_destination))
        return True

    assert destination.startswith('/tmp')
    cmd('rm %s' % destination)
    return False


@task()
def ssh():
    """Opens an SSH session"""
    run('bash')
