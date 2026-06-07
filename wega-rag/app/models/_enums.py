"""
Shared enums used by both critical and non-critical document/chunk models.
Defined here to avoid circular imports between document.py and document_nc.py.
"""
import enum


class DocumentStatus(str, enum.Enum):
    PENDING    = "pending"
    PROCESSING = "processing"
    COMPLETED  = "completed"
    FAILED     = "failed"


class Classification(str, enum.Enum):
    CRITICAL     = "critical"
    NON_CRITICAL = "non_critical"


class SDLCPhase(str, enum.Enum):
    REQUIREMENTS = "requirements"
    DESIGN       = "design"
    DEVELOPMENT  = "development"
    TESTING      = "testing"
    DEPLOYMENT   = "deployment"
    SECURITY     = "security"
    GENERAL      = "general"


class SourceType(str, enum.Enum):
    UPLOAD       = "upload"
    GITHUB       = "github"
    HARNESS      = "harness"
    CICD         = "cicd"
    AGENT_OUTPUT = "agent_output"
    CONFLUENCE   = "confluence"
    SHAREPOINT   = "sharepoint"
    WEBSITE      = "website"
    FEEDBACK     = "feedback"
