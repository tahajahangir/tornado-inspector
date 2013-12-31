Tornado Inspector
=================

Tornado tool for inspect and found request object from callback functions or stack frames.

This is useful for finding and logging the `HTTPRequest` object when an exception occur in async callback.
This class also can be used to generate traceback-like string for calls withing `tornado.gen` framework

Finding the actual request object in async callbacks is a pain, and this is can be done only by inspecting
function closures, objects that owning methods, and ...

usage of `TornadoContextInspector` is simple:

    >>> import sys
    >>> inspector = TornadoContextInspector()
    >>> inspector.inspect_frame(sys.exc_info()[2].tb_frame)
    >>> print(inspector.found_req)  # may be None
    HTTPRequest(protocol='http', ...)
    >>> print(''.join(inspector.format_async_frames()))
      File "file.py", line 32, in func_1
        result = yield gen.Task(self.func_2, foo)
      File "file.py", line 84, in func_2
        yield gen.Task(some_task, bar)



Requirements
-----------------
- six

Running tests
-----------------
Install `pytest` then run:

    $ py.test

[![Build Status](https://travis-ci.org/tahajahangir/tornado-inspector.png?branch=master)](https://travis-ci.org/tahajahangir/tornado-inspector)
