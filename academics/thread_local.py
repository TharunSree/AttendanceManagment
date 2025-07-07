# In academics/thread_local.py
import threading

_thread_locals = threading.local()


def set_current_session(session):
    _thread_locals.current_session = session


def get_current_session():
    return getattr(_thread_locals, 'current_session', None)
