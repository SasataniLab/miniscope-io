import os
import logging
import re
import multiprocessing as mp
import inspect
from pathlib import Path
from logging.handlers import RotatingFileHandler
from threading import Lock
import warnings
from rich.logging import RichHandler

from miniscope_io.config import Config

_LOGGERS = [] # type: list
"""
List of instantiated loggers, used in :func:`.init_logger` to return existing loggers without modification
"""

_INIT_LOCK = Lock() # type: Lock

def init_logger(instance=None, module_name=None, class_name=None, object_name=None, config:Config=Config()) -> logging.Logger:
    """
    Initialize a logger

    Loggers are created such that...

    * There is one logger per module (eg. all gpio objects will log to hardware.gpio)
    * If the passed object has a ``name`` attribute, that name will be prefixed to its log messages in the file
    * Logs are stored in the log directory configured by the :class:`.miniscope_io.config.Config` object - see its documentation for usage.

    Logs are stored in ``prefs.get('LOGDIR')``, and are formatted like::

        "%(asctime)s - %(name)s - %(levelname)s : %(message)s"

    Loggers can be initialized either by passing an object to the first ``instance`` argument, or
    by specifying any of ``module_name`` , ``class_name`` , or ``object_name`` (at least one must be specified)
    which are combined with periods like ``module.class_name.object_name``

    Args:
        instance: The object that we are creating a logger for! if None, at least one of ``module, class_name, or object_name`` must be passed
        module_name (None, str): If no ``instance`` passed, the module name to create a logger for
        class_name (None, str): If no ``instance`` passed, the class name to create a logger for
        object_name (None, str): If no ``instance`` passed, the object name/id to create a logger for
        config (:class:`~.config.Config`) : Configuration used for deciding the logging directory

    Returns:
        :class:`logging.logger`
    """

    # --------------------------------------------------
    # gather variables
    # --------------------------------------------------

    if instance is not None:
        # get name of module_name without prefixed miniscope_io
        # eg passed miniscope_io.hardware.gpio.Digital_In -> hardware.gpio
        # filtering leading 'miniscope_io' from string

        module_name = instance.__module__
        if "__main__" in module_name:
            # awkward workaround to get module name of __main__ run objects
            mod_obj = inspect.getmodule(instance)
            try:
                mod_suffix  = inspect.getmodulename(inspect.getmodule(instance).__file__)
                module_name = '.'.join([mod_obj.__package__, mod_suffix])
            except AttributeError:
                # when running interactively or from a plugin, __main__ does not have __file__
                module_name = "__main__"


        module_name = re.sub('^miniscope_io.', '', module_name)

        class_name = instance.__class__.__name__

        # if object is running in separate process, give it its own file
        if issubclass(instance.__class__, mp.Process):
            # it should be at least 2 (in case its first spawned in its module)
            # but otherwise nocollide
            p_num = 2
            _module_name = module_name
            module_name = f"{_module_name}_{str(p_num).zfill(2)}"
            if module_name in globals()['_LOGGERS']:
                for existing_mod in globals()['_LOGGERS']:
                    if module_name in existing_mod and re.match(r'\d$', existing_mod):
                        p_num += 1

                module_name = f"{_module_name}_{str(p_num).zfill(2)}"

        # get name of object if it has one
        if hasattr(instance, 'id'):
            object_name = str(instance.id)
        elif hasattr(instance, 'name'):
            object_name = str(instance.name)
        else:
            object_name = None

        # --------------------------------------------------
        # check if logger needs to be made, or exists already
        # --------------------------------------------------
    elif not any((module_name, class_name, object_name)):
        raise ValueError('Need to either give an object to create a logger for, or one of module_name, class_name, or object_name')


    # get name of logger to get
    logger_name_pieces = [v for v in (module_name, class_name, object_name) if v is not None]
    logger_name = '.'.join(logger_name_pieces)

    # trim __ from logger names, linux don't like to make things like that
    # re.sub(r"^\_\_")

    # --------------------------------------------------
    # if new logger must be made, make it, otherwise just return existing logger
    # --------------------------------------------------

    # use a lock to prevent loggers from being double-created, just to be extra careful
    with globals()['_INIT_LOCK']:

        # check if something starting with module_name already exists in loggers
        MAKE_NEW = False
        if not any([test_logger == module_name for test_logger in globals()['_LOGGERS']]):
            MAKE_NEW = True

        if MAKE_NEW:
            parent_logger = logging.getLogger(module_name)
            loglevel = 'DEBUG'
            parent_logger.setLevel(loglevel)

            # make formatter that includes name
            log_formatter = logging.Formatter("[%(asctime)s] %(levelname)s [%(name)s]: %(message)s")

            ## file handler
            # base filename is the module_name + '.log
            base_filename = config.BASE_DIR / config.LOG_DIR / (module_name + '.log')

            fh = _file_handler(base_filename)
            fh.setLevel(loglevel)
            fh.setFormatter(log_formatter)
            parent_logger.addHandler(fh)

            # rich logging handler for stdout
            parent_logger.addHandler(_rich_handler())

            # if our parent is the rootlogger, disable propagation to avoid printing to stdout
            if isinstance(parent_logger.parent, logging.RootLogger):
                parent_logger.propagate = False

            ## log creation
            globals()['_LOGGERS'].append(module_name)
            parent_logger.debug(f'parent, module-level logger created: {module_name}')

        logger = logging.getLogger(logger_name)
        if logger_name not in globals()['_LOGGERS']:
        # logger.addHandler(_rich_handler())
            logger.debug(f"Logger created: {logger_name}")
            globals()['_LOGGERS'].append(logger_name)

    return logger


def _rich_handler() -> RichHandler:
    rich_handler = RichHandler(rich_tracebacks=True, markup=True)
    rich_formatter = logging.Formatter(
        "[bold green]\[%(name)s][/bold green] %(message)s",
        datefmt='[%y-%m-%dT%H:%M:%S]'
    )
    rich_handler.setFormatter(rich_formatter)
    return rich_handler

def _file_handler(base_filename: Path) -> RotatingFileHandler:
    # if directory doesn't exist, try to make it
    if not base_filename.parent.exists():
        base_filename.parent.mkdir(parents=True, exist_ok=True)

    try:
        fh = RotatingFileHandler(
            str(base_filename),
            mode='a',
            maxBytes=int(5000),
            backupCount=int(5)
        )
    except PermissionError as e:
        # catch permissions errors, try to chmod our way out of it
        try:
            for mod_file in Path(base_filename).parent.glob(f"{Path(base_filename).stem}*"):
                os.chmod(mod_file, 0o777)
                warnings.warn(f'Couldnt access {mod_file}, changed permissions to 0o777')

            fh = RotatingFileHandler(
                base_filename,
                mode='a',
                maxBytes=int(5000),
                backupCount=int(5)
            )
        except Exception as f:
            raise PermissionError(
                f'Couldnt open logfile {base_filename}, and couldnt chmod our way out of it.\n' + '-' * 20 + f'\ngot errors:\n{e}\n\n{f}\n' + '-' * 20)

    return fh




