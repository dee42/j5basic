# -*- coding: utf-8 -*-

"""Module for write locks to do with databases.  When this is no longer used, we're ready for multiprocess database writes"""

import threading
import logging
import time
from j5.OS import ThreadRaise

database_write_lock = threading.Condition()
thread_busy = {}
MAX_LOCK_WAIT_TIMEOUT = 30

def no_database_writes(f):
    f.does_database_writes = False
    return f

def get_db_lock(max_wait_for_exclusive_lock=MAX_LOCK_WAIT_TIMEOUT):
    with (database_write_lock):
        current_id = ThreadRaise.get_thread_id(threading.currentThread())
        busy_op = thread_busy.get(None, None)
        if busy_op and busy_op[0] == current_id:
            # Multi-entrant
            thread_busy[None][2] += 1
            return
        start_time = time.time()
        while busy_op:
            logging.info('Thread %s waiting for Thread %s to release database lock (maximum wait %ds)',
                current_id, busy_op[0], max_wait_for_exclusive_lock)
            database_write_lock.wait(max_wait_for_exclusive_lock - (time.time() - start_time))
            now_busy_op = thread_busy.get(None, None)
            # Make sure we've waited the timeout time, as the same thread can release and catch the lock multiple times
            if now_busy_op and busy_op[0] == now_busy_op[0] and (time.time() - start_time > max_wait_for_exclusive_lock): #same op is still busy
                logging.error('Thread %s timed out waiting for Thread %s to release database lock ... Killing blocking thread ...',
                    current_id, busy_op[0])
                ThreadRaise.thread_async_raise(busy_op[0], RuntimeError)
                busy_op = None
            else:
                busy_op = now_busy_op

        thread_busy[None] = [current_id, time.time(), 1]

def release_db_lock():
    with (database_write_lock):
        current_id = ThreadRaise.get_thread_id(threading.currentThread())
        busy_op = thread_busy.get(None, None)
        if busy_op and busy_op[0] == current_id:
            busy_op[2] -= 1
            if busy_op[2] <= 0:
                thread_busy.pop(None, None)
                database_write_lock.notify()

