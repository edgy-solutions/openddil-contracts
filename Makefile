# =============================================================================
# OpenDDIL Contracts — Protobuf Compilation Makefile
# =============================================================================
# Compiles .proto files into Python and C# classes.
#
# Prerequisites:
#   - protoc (Protocol Buffers compiler) installed
#     macOS:   brew install protobuf
#     Windows: choco install protoc
#     Linux:   apt install -y protobuf-compiler
#
#   - For Python: grpcio-tools (pip install grpcio-tools)
#   - For C#: Grpc.Tools NuGet package (or protoc with grpc_csharp_plugin)
#
# Usage:
#   make all        # Compile for both Python and C#
#   make python     # Compile for Python only
#   make csharp     # Compile for C# only
#   make clean      # Remove generated files
# =============================================================================

PROTO_DIR    := proto
PROTO_FILES  := $(shell find $(PROTO_DIR) -name '*.proto')

# Output directories for generated code
PYTHON_OUT   := gen/python
CSHARP_OUT   := gen/csharp

# Protoc include path (for google/protobuf well-known types)
PROTO_PATH   := $(PROTO_DIR)

.PHONY: all python csharp clean dirs

# ---------------------------------------------------------------------------
# Default target
# ---------------------------------------------------------------------------
all: python csharp

# ---------------------------------------------------------------------------
# Create output directories
# ---------------------------------------------------------------------------
dirs:
	@mkdir -p $(PYTHON_OUT)
	@mkdir -p $(CSHARP_OUT)

# ---------------------------------------------------------------------------
# Python — generates *_pb2.py files
# ---------------------------------------------------------------------------
python: dirs
	@echo "==> Compiling Protobufs → Python..."
	protoc \
		--proto_path=$(PROTO_PATH) \
		--python_out=$(PYTHON_OUT) \
		$(PROTO_FILES)
	@echo "==> Python classes generated in $(PYTHON_OUT)/"

# ---------------------------------------------------------------------------
# C# — generates *.cs files
# ---------------------------------------------------------------------------
csharp: dirs
	@echo "==> Compiling Protobufs → C#..."
	protoc \
		--proto_path=$(PROTO_PATH) \
		--csharp_out=$(CSHARP_OUT) \
		$(PROTO_FILES)
	@echo "==> C# classes generated in $(CSHARP_OUT)/"

# ---------------------------------------------------------------------------
# Clean generated files
# ---------------------------------------------------------------------------
clean:
	@echo "==> Cleaning generated files..."
	rm -rf gen/
	@echo "==> Done."
