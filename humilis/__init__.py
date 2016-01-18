# -*- coding: utf-8 -*-

import os
import inspect
import humilis.metadata as metadata


__version__ = metadata.version
__dir__ = os.path.dirname(inspect.getfile(inspect.currentframe()))
