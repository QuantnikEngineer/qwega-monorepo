class SDLCKBException(Exception):
    def __init__(self, message: str, code: str = "SDLC_KB_ERROR"):
        self.message = message
        self.code    = code
        super().__init__(message)

class UnsupportedFileTypeError(SDLCKBException):
    def __init__(self, ext: str):
        super().__init__(f"Unsupported file type: {ext}", "UNSUPPORTED_FILE_TYPE")

class FileTooLargeError(SDLCKBException):
    def __init__(self, size_mb: float):
        super().__init__(f"File size {size_mb:.1f}MB exceeds limit", "FILE_TOO_LARGE")

class ParsingError(SDLCKBException):
    def __init__(self, filename: str, detail: str):
        super().__init__(f"Failed to parse {filename}: {detail}", "PARSING_ERROR")

class ClassificationError(SDLCKBException):
    def __init__(self, detail: str):
        super().__init__(f"Classification failed: {detail}", "CLASSIFICATION_ERROR")

class EmbeddingError(SDLCKBException):
    def __init__(self, detail: str):
        super().__init__(f"Embedding failed: {detail}", "EMBEDDING_ERROR")

class VectorStoreError(SDLCKBException):
    def __init__(self, detail: str):
        super().__init__(f"Vector store error: {detail}", "VECTOR_STORE_ERROR")

class GuardrailViolationError(SDLCKBException):
    def __init__(self, guard_type: str, detail: str):
        super().__init__(f"{guard_type} guardrail: {detail}", "GUARDRAIL_VIOLATION")

class DocumentNotFoundError(SDLCKBException):
    def __init__(self, doc_id: str):
        super().__init__(f"Document not found: {doc_id}", "DOCUMENT_NOT_FOUND")