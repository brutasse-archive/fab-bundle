# -*- coding: utf-8 -*-

__title__ = 'fab_bundle'
__version__ = '0.1'
__author__ = 'Bruno Renie'


try:
    from fabric.api import env, task
    from .bundle import deploy, destroy
    from .provisioning import bootstrap
    from .utils import ssh
except ImportError:
    pass  # don't break installation, fabric is in install_requires anyway
