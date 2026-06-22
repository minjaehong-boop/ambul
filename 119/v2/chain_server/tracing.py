"""Simplified tracing module.

OpenTelemetry tracing is optional. Set ENABLE_TRACING=true to activate.
Without it, a no-op LangChain callback handler is used.
"""

import os
from functools import wraps

from langchain_core.callbacks.base import BaseCallbackHandler as _LangchainBaseHandler

# ── Optional OpenTelemetry setup ──────────────────────────────────────────────
_ENABLE_TRACING = os.environ.get("ENABLE_TRACING", "false").lower() == "true"

if _ENABLE_TRACING:
    try:
        from opentelemetry import context, trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.propagate import get_global_textmap, set_global_textmap
        from opentelemetry.propagators.composite import CompositePropagator
        from opentelemetry.sdk.resources import SERVICE_NAME, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import SimpleSpanProcessor
        from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

        resource = Resource.create({SERVICE_NAME: "chain-server"})
        provider = TracerProvider(resource=resource)
        processor = SimpleSpanProcessor(OTLPSpanExporter())
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)

        propagator = TraceContextTextMapPropagator()
        set_global_textmap(propagator)

        # Try to load custom LangChain OTLP callback (optional)
        try:
            import sys, importlib.util
            _here = os.path.dirname(__file__)
            _cb_path = os.path.join(_here, "..", "tools", "observability", "langchain", "opentelemetry_callback.py")
            if os.path.exists(_cb_path):
                spec = importlib.util.spec_from_file_location("otel_cb", _cb_path)
                mod = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(mod)
                tracer = trace.get_tracer("chain-server")
                langchain_cb_handler = mod.OpenTelemetryCallbackHandler(tracer)
            else:
                langchain_cb_handler = _LangchainBaseHandler()
        except Exception:
            langchain_cb_handler = _LangchainBaseHandler()

    except ImportError:
        langchain_cb_handler = _LangchainBaseHandler()
else:
    langchain_cb_handler = _LangchainBaseHandler()


# ── Class decorator ───────────────────────────────────────────────────────────
def langchain_instrumentation_class_wrapper(func):
    """Decorator that injects a LangChain callback handler as self.cb_handler."""
    class WrapperClass(func):
        def __init__(self, *args, **kwargs):
            self.cb_handler = langchain_cb_handler
            super().__init__(*args, **kwargs)
    WrapperClass.__name__ = func.__name__
    WrapperClass.__qualname__ = func.__qualname__
    return WrapperClass
