from __future__ import absolute_import, print_function
import inspect
import logging
import traceback
import types

from tornado.httpserver import HTTPRequest
from six import iteritems, get_method_self, get_function_closure, get_function_code, get_function_globals


function_module = lambda func: get_function_globals(func).get('__name__')
function_closure_dict = lambda func: dict(zip(get_function_code(func).co_freevars,
                                              (c.cell_contents for c in get_function_closure(func))))


class TornadoContextInspector(object):
    """
    Tool for inspect and found HTTRequest from callback functions or stack frames.
    This is useful for finding and logging the HTTPRequest object when an exception occur in async callback.
    This class also can be used to generate traceback-like string for calls withing `tornado.gen` framework
    Finding the actual request object in async callbacks is a pain, and this is can be done only by inspecting
        function closures, objects that owning methods, and ...

    The usage of `TornadoContextInspector` is simple
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
    """
    logger = None

    def __init__(self, debug_inspection=False, stop_on_request_find=False):
        """
        @param debug_inspection: if be True, debug log will be generated
        @param stop_on_request_find: stop when request found, (normally inspection is continued to find more
            async calls)
        """
        self.async_frames = []
        self.found_req = None
        self.marked_objects = set([])
        self.stop_on_request_find = stop_on_request_find
        if debug_inspection:
            self.logger = logging.getLogger('tornado.general.context_inspector')
            self.logger.setLevel(logging.DEBUG)

    def inspect_frame(self, frame):
        """
        Inspect then given frame recursively. (traverse all back frames)
        """
        while frame:
            self.inspect_single_frame(frame)
            frame = frame.f_back

    def format_async_frames(self):
        return [traceback.format_stack(frame, 1) for frame in reversed(self.async_frames)]

    def inspect_single_frame(self, frame):
        if self.logger:
            self.logger.debug('Trying frame %s' % traceback.format_stack(frame, 1)[0].strip())
        self.inspect_dict(frame.f_locals)

    def inspect_dict(self, find_dict):
        """
        @param find_dict: a dict of variables, local variables or closure variables
        """
        if self.found_req and self.stop_on_request_find:
            return
        for key, value in iteritems(find_dict):
            if self.found_req is None and key.endswith('request') and isinstance(value, HTTPRequest):
                # Known examples are `RequestHandler.request` and `HTTPConnection._request`
                self.found_req = value

            if key.endswith('callback') and inspect.isfunction(value):
                if self.logger:
                    self.logger.debug('Diving into callback from key `%s`' % key)
                self.inspect_callback(value)

        if 'self' in find_dict:
            if self.logger:
                self.logger.debug('Diving into `self` variable from find_dict (of type %s)' % type(find_dict['self']))
            self.inspect_object(find_dict['self'])

    def inspect_object(self, obj):
        """
        @type obj: any object, the __dict__ of object will be inspected. (It's safe to pass any value as obj)
        """
        if self.found_req and self.stop_on_request_find:
            return
        if id(obj) in self.marked_objects:
            if self.logger:
                self.logger.debug('Object already marked, skipping')
            return
        else:
            self.marked_objects.add(id(obj))

        if not self.found_req and isinstance(obj, HTTPRequest):
            self.found_req = obj

        if hasattr(obj, '__dict__'):
            # search for all `*callback` object variables. the known examples of this pattern is
            # `mongotor.connection.Connection._callback` and `BaseIOStream._[read|write|...]_callback`
            self.inspect_dict(obj.__dict__)

    def inspect_callback(self, callback_f):
        if self.found_req and self.stop_on_request_find:
            return
        if callback_f.__name__ == 'wrapped' and function_module(callback_f) == 'tornado.stack_context':
            # if this is a context wrapper, continue from wrapped function
            closures = function_closure_dict(callback_f)
            new_callback = closures['fn']  # wrapped function
            if self.logger:
                self.logger.debug('Unwrap function `%s` from stack_context wrapper' % new_callback)
        else:
            # unknown function for callback
            new_callback = callback_f
            if self.logger:
                self.logger.debug('cannot unwrap function `%s`, continuing' % new_callback)

        self.inspect_function_closures(new_callback)

        if isinstance(new_callback, types.MethodType):
            current_self = get_method_self(new_callback)
            if current_self is not None:  # not static method in python2
                if self.logger:
                    self.logger.debug('Diving into method owner (of type %s)' % type(current_self))
                self.inspect_object(current_self)

    def inspect_function_closures(self, func):
        if self.found_req and self.stop_on_request_find:
            return
        if not get_function_closure(func):
            if self.logger:
                self.logger.debug('Function does not have any closure, skipping')
            return
        closures = function_closure_dict(func)
        if func.__name__ == 'inner' and function_module(func) == 'tornado.gen':
            # We are inside tornado.gen.Runner.run, continue to actual wrapped generator
            generator_obj = closures['self'].gen
            gen_frame = generator_obj.gi_frame
            if gen_frame:  # frame may be empty
                if self.logger:
                    self.logger.debug('Found `tornado.gen` instance, running: %s, has_frame: %s'
                                      % (generator_obj.gi_running, bool(gen_frame)))
                # why? need test
                # if not generator_obj.gi_running:
                #     # only write this line as async calls if generator is NOT running, if it's running it's present
                #     # on the normal traceback
                self.async_frames.append(gen_frame)
                if self.logger:
                    self.logger.debug('Diving into `tornado.gen` frame: %s' % traceback.format_stack(gen_frame, 1)[0])
                self.inspect_dict(gen_frame.f_locals)
            elif self.logger:
                self.logger.debug('Found dead `tornado.gen` instance (without any frame), skipping')
            return  # it's a `tornado.gen` object, not need to dive into closures

        if self.logger:
            self.logger.debug('Cannot find generator, diving into closure variables')
        return self.inspect_dict(closures)
