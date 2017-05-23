from logging import Handler

class LogException(Exception):
    pass

class CrashHandler(Handler):
    def emit(self, record):
        msg = self.format(record)
        raise LogException(msg)