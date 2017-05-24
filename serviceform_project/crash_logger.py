from logging import Handler

class LogException(Exception):
    pass

class CrashHandler(Handler):
    """
    This is being used for tests to crash on error level log events.
    """
    def emit(self, record):
        msg = self.format(record)
        raise LogException(msg)