from __future__ import print_function
import sys

from tornado import gen
from tornado.httpserver import HTTPRequest
from tornado.ioloop import IOLoop

from tornado_inspector import TornadoContextInspector


def currentframe(level):
    # in Python 3.2, inspect.current_frame doesn't accept any argument
    if hasattr(sys, '_getframe'):
        return getattr(sys, '_getframe')(level)
    return None


def test_simple():
    inspector = TornadoContextInspector()
    r = HTTPRequest('GET', '/foo/bar')  # don't name this as request!

    def handle_req(request):
        try:
            inspector.inspect_frame(currentframe(1))
            # print(inspector.__dict__)
            assert inspector.found_req is request
            assert inspector.async_frames == []
            # currently async rows is empty
        finally:
            IOLoop.current().stop()

    IOLoop.current().add_callback(handle_req, r)
    IOLoop.current().start()


def test_simple_gen_engine():
    # in this test, the outer function has the request parameter
    inspector = TornadoContextInspector()
    r = HTTPRequest('GET', '/foo/bar')  # don't name this as request!

    # noinspection PyUnusedLocal
    def load_file(_file_id, callback):
        inspector.inspect_frame(currentframe(1))
        # print(inspector.__dict__)
        assert inspector.found_req is r
        assert len(inspector.async_frames) == 1
        assert 'yield gen.Task(load_file' in inspector.format_async_frames()[0]
        # currently result looks like:
        #    yield gen.Task(load_file, 1)
        IOLoop.current().add_callback(callback)

    # noinspection PyUnusedLocal
    @gen.engine
    def handle_req(request):
        try:
            yield gen.Task(load_file, 1)
        finally:
            IOLoop.current().stop()

    IOLoop.current().add_callback(handle_req, r)
    IOLoop.current().start()


def test_simple_gen_engine2():
    # in this test, both inner/outer function have the request parameter
    inspector = TornadoContextInspector()
    r = HTTPRequest('GET', '/foo/bar')  # don't name this as request!

    # noinspection PyUnusedLocal
    def load_file(request, callback):
        inspector.inspect_frame(currentframe(1))
        # print(inspector.__dict__)
        assert inspector.found_req is r
        assert len(inspector.async_frames) == 1
        assert 'yield gen.Task(load_file' in inspector.format_async_frames()[0]
        # currently result looks like:
        #    yield gen.Task(load_file, 1)
        IOLoop.current().add_callback(callback)

    @gen.engine
    def handle_req(request):
        try:
            yield gen.Task(load_file, request)
        finally:
            IOLoop.current().stop()

    IOLoop.current().add_callback(handle_req, r)
    IOLoop.current().start()


def test_simple_gen_engine3():
    # in this test, only inner function has the request parameter
    inspector = TornadoContextInspector()
    r = HTTPRequest('GET', '/foo/bar')  # don't name this as request!

    # noinspection PyUnusedLocal
    def load_file(request, callback):
        inspector.inspect_frame(currentframe(1))
        # print(inspector.__dict__)
        assert inspector.found_req is r
        assert len(inspector.async_frames) == 1
        assert 'yield gen.Task(load_file' in inspector.format_async_frames()[0]
        # currently result looks like:
        #    yield gen.Task(load_file, 1)
        IOLoop.current().add_callback(callback)

    @gen.engine
    def handle_req():
        try:
            yield gen.Task(load_file, r)
        finally:
            IOLoop.current().stop()

    IOLoop.current().add_callback(handle_req)
    IOLoop.current().start()


def test_simple_gen_engine_three_level():
    # in this test, only inner function has the request parameter
    inspector = TornadoContextInspector()
    r = HTTPRequest('GET', '/foo/bar')  # don't name this as request!

    def load_root(callback):
        inspector.inspect_frame(currentframe(1))
        # print(inspector.__dict__)
        assert inspector.found_req is r
        assert len(inspector.async_frames) == 3
        formatted = inspector.format_async_frames()
        assert 'yield gen.Task(load_sub_sub' in formatted[0]
        assert 'yield gen.Task(load_sub' in formatted[1]
        assert 'yield gen.Task(load_root' in formatted[2]
        # currently result looks like:
        #    yield gen.Task(load_sub_sub)
        #    yield gen.Task(load_sub)
        #    yield gen.Task(load_root, 1)
        IOLoop.current().add_callback(callback)

    @gen.engine
    def load_sub(callback):
        yield gen.Task(load_root)
        callback()

    @gen.engine
    def load_sub_sub(callback):
        yield gen.Task(load_sub)
        callback()

    # noinspection PyUnusedLocal
    @gen.engine
    def handle_req(request):
        try:
            yield gen.Task(load_sub_sub)
        finally:
            IOLoop.current().stop()

    IOLoop.current().add_callback(handle_req, r)
    IOLoop.current().start()


def test_dummy_gen_engine():
    # in this test, we used gen.engine in a way, that one balot version incorrectly prints one async row
    inspector = TornadoContextInspector()
    r = HTTPRequest('GET', '/foo/bar')  # don't name this as request!

    def load_root(callback):
        IOLoop.current().add_callback(callback)

    @gen.engine
    def load_sub(callback):
        yield gen.Task(load_root)
        callback()

    @gen.engine
    def gen_engine_process(request):
        try:
            yield gen.Task(load_sub)
            inspector.inspect_frame(currentframe(1))
            # print(inspector.__dict__)
            assert inspector.found_req is request
            assert len(inspector.async_frames) == 0, 'We doesnt have any async calls'
        finally:
            IOLoop.current().stop()

    IOLoop.current().add_callback(gen_engine_process, r)
    IOLoop.current().start()


if __name__ == '__main__':
    # This is file is actually a py.test file, but it's runnable py.test
    test_simple()
    test_simple_gen_engine()
    test_simple_gen_engine2()
    test_simple_gen_engine3()
    test_simple_gen_engine_three_level()
    test_dummy_gen_engine()
