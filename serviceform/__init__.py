import pkg_resources
import os

try:
    __version__ = pkg_resources.get_distribution("serviceform").version
except pkg_resources.DistributionNotFound:
    __version__ = os.getenv('SERVICEFORM_VERSION', '')
