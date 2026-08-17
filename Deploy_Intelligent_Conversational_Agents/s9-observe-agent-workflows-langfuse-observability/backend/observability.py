"""
Observability setup using Langfuse @observe decorator and OpenTelemetry.
"""
from langfuse import observe, get_client
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


## Task 1: Setup OpenTelemetry Tracer Provider and add ConsoleSpanExporter

# Create tracer provider
provider = TracerProvider()

# Create console exporter (prints spans in terminal)
console_exporter = ConsoleSpanExporter()

# Add span processor
span_processor = BatchSpanProcessor(console_exporter)
provider.add_span_processor(span_processor)

# Set global tracer provider
trace.set_tracer_provider(provider)

# Get tracer (can be used anywhere if needed)
tracer = trace.get_tracer(__name__)

# -----------------------------------------
# Langfuse client (for flushing traces)
# -----------------------------------------
langfuse_client = get_client()


def flush_langfuse():
    """
    Flush Langfuse traces (important for streaming apps).
    """
    if langfuse_client:
        langfuse_client.flush()