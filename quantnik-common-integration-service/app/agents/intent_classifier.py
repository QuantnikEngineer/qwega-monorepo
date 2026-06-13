"""
Intent Classifier
=================
LLM-based intent classification for context enrichment operations.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
import json

from app.core.logging import get_logger
from app.core.config import settings
from app.models.requests import IntentType

logger = get_logger(__name__)

FILE_NAME = "intent_classifier.py"


class ClassifiedIntent(BaseModel):
    """Structured output from intent classification."""
    intent: IntentType = Field(..., description="Classified intent type")
    confidence: float = Field(..., ge=0, le=1)
    entities: Dict[str, Any] = Field(default_factory=dict)
    requires_clarification: bool = Field(default=False)
    clarification_question: Optional[str] = Field(default=None)
    reasoning: Optional[str] = Field(default=None)


INTENT_CLASSIFICATION_PROMPT = """You are an intent classifier for QUANTNIK Common Integration Service.
You need to understand what the user wants to do with knowledge base operations.

## Available Intents:

### Context Enrichment Operations:
- **context_enrich_upload** - Upload documents/files to the knowledge base
- **context_enrich_ingest** - Ingest content from websites, SharePoint, repositories, or agent outputs
- **context_enrich_feedback** - Submit feedback, ratings, reviews, suggestions, comments, or corrections. Keywords: "feedback", "rating", "rate", "review", "suggestion", "suggest", "comment", "correction", "improve", "recommendation", "opinion", "thoughts"
- **context_enrich_query** - Query/search the knowledge base for specific information, ask questions about content, or general information-seeking questions. This is a FALLBACK intent when no other specific intent matches.
- **context_enrich_list_documents** - View, list, display, show, get, fetch, or retrieve documents/files that exist in the knowledge base. Use this when user wants to SEE what documents are available.

### CRITICAL: context_enrich_feedback Examples
**ANY message about providing feedback, rating, review, suggestion, or correction = context_enrich_feedback**

Examples (ALL of these should be classified as context_enrich_feedback):
- "give feedback" → context_enrich_feedback
- "provide feedback" → context_enrich_feedback
- "submit feedback" → context_enrich_feedback
- "rate this" → context_enrich_feedback
- "give rating" → context_enrich_feedback
- "my rating is" → context_enrich_feedback
- "review the output" → context_enrich_feedback
- "give a review" → context_enrich_feedback
- "i have a suggestion" → context_enrich_feedback
- "my suggestion is" → context_enrich_feedback
- "suggest improvement" → context_enrich_feedback
- "add comment" → context_enrich_feedback
- "leave a comment" → context_enrich_feedback
- "correction needed" → context_enrich_feedback
- "make a correction" → context_enrich_feedback
- "i want to correct" → context_enrich_feedback
- "recommend changes" → context_enrich_feedback
- "my recommendation" → context_enrich_feedback
- "share my thoughts" → context_enrich_feedback
- "my opinion is" → context_enrich_feedback
- "domain preference" → context_enrich_feedback

### CRITICAL: context_enrich_list_documents Examples
**ANY message asking to see, view, show, list, get, fetch, or retrieve documents/files = context_enrich_list_documents**

Examples (ALL of these should be classified as context_enrich_list_documents):
- "show my files" → context_enrich_list_documents
- "fetch the documents" → context_enrich_list_documents
- "get the documents" → context_enrich_list_documents
- "list my documents" → context_enrich_list_documents
- "what files do I have" → context_enrich_list_documents
- "fetch documents" → context_enrich_list_documents
- "display uploaded files" → context_enrich_list_documents
- "what's in my knowledge base" → context_enrich_list_documents
- "show uploaded documents" → context_enrich_list_documents
- "view my files" → context_enrich_list_documents
- "what documents are available" → context_enrich_list_documents
- "retrieve my files" → context_enrich_list_documents
- "show all documents" → context_enrich_list_documents
- "my documents" → context_enrich_list_documents
- "the documents" → context_enrich_list_documents

### CRITICAL: context_enrich_query Examples (FALLBACK for information-seeking questions)
**Use context_enrich_query when user asks questions or seeks information:**

Question patterns (case-insensitive):
- "how to...", "how do I...", "how can I..."
- "what is...", "what are...", "what does..."
- "why is...", "why does...", "why should..."
- "when should...", "when to..."
- "where is...", "where can..."
- "which one...", "which is..."
- "can you explain...", "explain..."
- "tell me about...", "describe..."

Information retrieval patterns (case-insensitive):
- "get me...", "fetch...", "retrieve..." (when NOT about listing documents)
- "find...", "search for...", "look for..."
- "give me...", "provide...", "show me..." (when asking for information, not document listing)

Examples (ALL of these should be classified as context_enrich_query):
- "how to create a login page" → context_enrich_query
- "what is microservices architecture" → context_enrich_query
- "why should we use REST API" → context_enrich_query
- "get me information about payment gateway" → context_enrich_query
- "fetch details about user authentication" → context_enrich_query
- "retrieve the requirements for checkout flow" → context_enrich_query
- "what does the BRD say about security" → context_enrich_query
- "explain the login flow" → context_enrich_query
- "tell me about the API endpoints" → context_enrich_query
- "find information about database schema" → context_enrich_query

### Other:
- **general_question** - General questions about the SYSTEM CAPABILITIES ONLY (e.g., "what can you do?", "help me understand this tool")
- **confirmation** - User confirming a previous suggestion (yes, ok, proceed)
- **unknown** - Cannot determine intent clearly

## PRIORITY ORDER FOR CLASSIFICATION (CRITICAL):
1. **FIRST**: Check if message is about uploading files/documents
2. **SECOND**: Check if message is about ingesting content (website, sharepoint, repo)
3. **THIRD**: Check if message is about feedback, rating, review, suggestion, or correction → context_enrich_feedback
4. **FOURTH**: Check if message is about document listing (list, show, fetch documents/files)
5. **LAST (FALLBACK)**: If message contains question words (how, what, why, when, where, which) OR information retrieval words (get me, fetch, retrieve, find, search) AND doesn't match above intents, classify as **context_enrich_query**

## Context Information:
{context}

## Conversation History:
{history}

## Current User Message:
{message}

## Instructions:
1. Analyze the user's message carefully (case-insensitive matching)
2. If user is confirming (yes, ok, proceed), classify as "confirmation"
3. **FEEDBACK CHECK**: If message contains feedback/rating/review/suggestion/correction keywords, classify as "context_enrich_feedback"
4. **DOCUMENT LISTING**: If user wants to VIEW, LIST, SHOW documents/files, classify as "context_enrich_list_documents"
5. **FALLBACK TO QUERY**: If message contains question words (how, what, why, when, where, which, can, explain, tell, describe) OR retrieval words (get me, fetch, retrieve, find, search, give me, provide) AND doesn't match other intents, classify as "context_enrich_query"
6. **NEVER classify information-seeking questions as "unknown"** - use context_enrich_query as fallback
7. Extract relevant entities (files, URLs, queries, feedback content)

Respond with JSON:
{{
    "intent": "one of the intent types",
    "confidence": 0.0-1.0,
    "entities": {{}},
    "requires_clarification": false,
    "clarification_question": null,
    "reasoning": "brief explanation"
}}
"""


class IntentClassifier:
    """LLM-based intent classifier."""
    
    def __init__(self, llm_client=None):
        logger.info(f"[{FILE_NAME}] IntentClassifier.__init__: ENTRY")
        self._llm = llm_client
        self._initialize_llm()
        logger.info(f"[{FILE_NAME}] IntentClassifier.__init__: EXIT")
    
    def _initialize_llm(self):
        """Initialize the LLM client."""
        logger.debug(f"[{FILE_NAME}] _initialize_llm: ENTRY")
        if self._llm is not None:
            logger.debug(f"[{FILE_NAME}] _initialize_llm: EXIT - LLM already provided")
            return
            
        if settings.google_api_key:
            try:
                logger.debug(f"[{FILE_NAME}] _initialize_llm: Attempting Google GenAI initialization")
                from google import genai
                import httpx
                import certifi
                
                ssl_verify = certifi.where() if settings.ssl_verify else False
                http_client = httpx.Client(verify=ssl_verify, timeout=900)
                
                self._llm = genai.Client(
                    api_key=settings.google_api_key,
                    http_options={"client": http_client}
                )
                self._llm_type = "google"
                logger.info(f"[{FILE_NAME}] _initialize_llm: EXIT - Initialized Google GenAI")
                return
            except Exception as e:
                logger.warning(
                    f"[{FILE_NAME}] _initialize_llm: Failed Google GenAI",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        if settings.google_cloud_project:
            try:
                logger.debug(f"[{FILE_NAME}] _initialize_llm: Attempting Vertex AI initialization")
                from langchain_google_vertexai import ChatVertexAI
                self._llm = ChatVertexAI(
                    model="gemini-1.5-flash",
                    temperature=settings.llm_temperature,
                    project=settings.google_cloud_project,
                    location=settings.google_cloud_location
                )
                self._llm_type = "vertexai"
                logger.info(f"[{FILE_NAME}] _initialize_llm: EXIT - Initialized Vertex AI")
                return
            except Exception as e:
                logger.warning(
                    f"[{FILE_NAME}] _initialize_llm: Failed Vertex AI",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        if settings.openai_api_key:
            try:
                logger.debug(f"[{FILE_NAME}] _initialize_llm: Attempting OpenAI initialization")
                from langchain_openai import ChatOpenAI
                self._llm = ChatOpenAI(
                    model=settings.openai_model,
                    temperature=settings.llm_temperature,
                    api_key=settings.openai_api_key,
                    max_tokens=settings.llm_max_tokens
                )
                self._llm_type = "openai"
                logger.info(f"[{FILE_NAME}] _initialize_llm: EXIT - Initialized OpenAI")
                return
            except Exception as e:
                logger.warning(
                    f"[{FILE_NAME}] _initialize_llm: Failed OpenAI",
                    error=str(e),
                    error_type=type(e).__name__
                )
        
        self._llm_type = "fallback"
        logger.warning(f"[{FILE_NAME}] _initialize_llm: EXIT - Using keyword-based fallback")
    
    async def classify(
        self,
        message: str,
        history: Optional[List[Dict[str, str]]] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> ClassifiedIntent:
        """Classify user intent."""
        logger.info(
            f"[{FILE_NAME}] classify: ENTRY",
            message_length=len(message),
            message_preview=message[:100],
            history_count=len(history) if history else 0,
            has_context=context is not None,
            llm_type=self._llm_type
        )
        
        history = history or []
        context = context or {}
        
        history_str = "\n".join([
            f"{m['role'].capitalize()}: {m['content']}"
            for m in history[-5:]
        ]) if history else "No previous conversation"
        
        context_str = json.dumps(context, indent=2) if context else "No additional context"
        
        prompt = INTENT_CLASSIFICATION_PROMPT.format(
            context=context_str,
            history=history_str,
            message=message
        )
        
        try:
            if self._llm_type == "google":
                result = await self._classify_with_google(prompt)
            elif self._llm_type == "vertexai":
                result = await self._classify_with_langchain(prompt)
            elif self._llm_type == "openai":
                result = await self._classify_with_langchain(prompt)
            else:
                result = self._classify_with_keywords(message, context)
            
            logger.info(
                f"[{FILE_NAME}] classify: EXIT",
                intent=result.intent.value,
                confidence=result.confidence,
                requires_clarification=result.requires_clarification,
                reasoning=result.reasoning
            )
            return result
            
        except Exception as e:
            logger.error(
                f"[{FILE_NAME}] classify: LLM failed, falling back to keywords",
                error=str(e),
                error_type=type(e).__name__
            )
            result = self._classify_with_keywords(message, context)
            result.reasoning = f"Keyword fallback (LLM error: {str(e)[:50]})"
            logger.info(f"[{FILE_NAME}] classify: EXIT - Keyword fallback", intent=result.intent.value)
            return result
    
    async def _classify_with_google(self, prompt: str) -> ClassifiedIntent:
        """Classify using Google GenAI."""
        logger.debug(f"[{FILE_NAME}] _classify_with_google: ENTRY")
        from google.genai import types
        
        response = self._llm.models.generate_content(
            model="gemini-2.0-flash",
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json"
            )
        )
        
        result_json = json.loads(response.text)
        logger.debug(f"[{FILE_NAME}] _classify_with_google: EXIT", result=result_json)
        return self._parse_result(result_json)
    
    async def _classify_with_langchain(self, prompt: str) -> ClassifiedIntent:
        """Classify using LangChain."""
        logger.debug(f"[{FILE_NAME}] _classify_with_langchain: ENTRY")
        from langchain_core.messages import HumanMessage
        
        response = await self._llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content
        
        start = content.find('{')
        end = content.rfind('}') + 1
        if start >= 0 and end > start:
            result_json = json.loads(content[start:end])
            logger.debug(f"[{FILE_NAME}] _classify_with_langchain: EXIT", result=result_json)
            return self._parse_result(result_json)
        
        logger.error(f"[{FILE_NAME}] _classify_with_langchain: No JSON found in response")
        raise ValueError("No JSON found in response")
    
    def _classify_with_keywords(
        self, 
        message: str, 
        context: Optional[Dict[str, Any]] = None
    ) -> ClassifiedIntent:
        """Fallback keyword-based classification.
        
        Priority order:
        1. Confirmation words
        2. Upload keywords
        3. Ingest keywords
        4. Feedback keywords (rating, review, suggestion, correction)
        5. List documents keywords
        6. FALLBACK: Question/query patterns -> context_enrich_query
        """
        logger.debug(f"[{FILE_NAME}] _classify_with_keywords: ENTRY", message=message)
        message_lower = message.lower().strip()
        context = context or {}
        
        # PRIORITY 1: Confirmation words
        confirmation_words = [
            "yes", "yeah", "yep", "sure", "ok", "okay", "proceed", 
            "continue", "go ahead", "do it", "confirm", "confirmed"
        ]
        
        if message_lower in confirmation_words or any(
            message_lower == word or message_lower.startswith(word + " ")
            for word in confirmation_words
        ):
            logger.debug(f"[{FILE_NAME}] _classify_with_keywords: Matched confirmation")
            return ClassifiedIntent(
                intent=IntentType.CONFIRMATION,
                confidence=0.9,
                reasoning="User confirmed/agreed to proceed"
            )
        
        # PRIORITY 2: Upload keywords
        upload_keywords = ["upload", "upload file", "upload document", "add file", "add document"]
        if any(kw in message_lower for kw in upload_keywords):
            logger.debug(f"[{FILE_NAME}] _classify_with_keywords: Matched upload")
            return ClassifiedIntent(
                intent=IntentType.CONTEXT_ENRICH_UPLOAD,
                confidence=0.8,
                reasoning="Matched upload keywords"
            )
        
        # PRIORITY 3: Ingest keywords
        ingest_keywords = ["ingest", "crawl", "scrape", "import", "index website", "index repo", "sharepoint", "repository"]
        if any(kw in message_lower for kw in ingest_keywords):
            logger.debug(f"[{FILE_NAME}] _classify_with_keywords: Matched ingest")
            return ClassifiedIntent(
                intent=IntentType.CONTEXT_ENRICH_INGEST,
                confidence=0.8,
                reasoning="Matched ingest keywords"
            )
        
        # PRIORITY 4: Feedback keywords (comprehensive list)
        feedback_keywords = [
            "feedback", "give feedback", "provide feedback", "submit feedback", "send feedback",
            "rating", "rate", "rate this", "give rating", "my rating", "star rating",
            "review", "give review", "provide review", "submit review", "my review",
            "suggestion", "suggest", "my suggestion", "make suggestion", "give suggestion",
            "comment", "add comment", "leave comment", "my comment", "comments",
            "correction", "correct", "make correction", "need correction", "corrections",
            "improve", "improvement", "improvements", "recommend", "recommendation", "recommendations",
            "opinion", "my opinion", "share opinion", "thoughts", "my thoughts", "share thoughts",
            "preference", "domain preference", "set preference", "my preference",
        ]
        if any(kw in message_lower for kw in feedback_keywords):
            logger.debug(f"[{FILE_NAME}] _classify_with_keywords: Matched feedback")
            return ClassifiedIntent(
                intent=IntentType.CONTEXT_ENRICH_FEEDBACK,
                confidence=0.8,
                reasoning="Matched feedback/rating/review/suggestion keywords"
            )
        
        # PRIORITY 5: List documents keywords
        list_doc_keywords = [
            "get the document", "get the documents", "fetch the document", "fetch the documents",
            "get document", "get documents", "fetch document", "fetch documents",
            "list document", "list documents", "show document", "show documents",
            "retrieve document", "retrieve documents", "get the file", "get the files",
            "fetch the file", "fetch the files", "list the file", "list the files",
            "show the file", "show the files", "get all document", "list all document",
            "show all document", "fetch all document", "get my document", "show my document",
            "list my document", "my documents", "the documents", "all documents",
            "show my files", "get my files", "list my files", "fetch my files",
            "my files", "all files", "list files", "show files", "get files",
            "view documents", "view files", "display documents", "display files"
        ]
        if any(kw in message_lower for kw in list_doc_keywords):
            logger.debug(f"[{FILE_NAME}] _classify_with_keywords: Matched list documents")
            return ClassifiedIntent(
                intent=IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS,
                confidence=0.8,
                reasoning="Matched list documents keywords"
            )
        
        # PRIORITY 6 (FALLBACK): Question patterns and information retrieval -> context_enrich_query
        question_patterns = [
            "how to", "how do", "how can", "how is", "how does", "how should", "how would",
            "what is", "what are", "what does", "what do", "what should", "what would", "what can",
            "why is", "why does", "why do", "why should", "why would", "why are",
            "when to", "when should", "when do", "when does", "when is", "when can",
            "where is", "where are", "where can", "where do", "where does",
            "which is", "which are", "which one", "which should", "which would",
            "can you explain", "can you tell", "can you describe", "can you help",
            "could you explain", "could you tell", "could you describe",
            "explain", "describe", "tell me", "tell us",
            "who is", "who are", "who can", "who should",
        ]
        
        retrieval_patterns = [
            "get me", "get the", "get information", "get details", "get info",
            "fetch me", "fetch the", "fetch information", "fetch details",
            "retrieve", "retrieve the", "retrieve information",
            "find", "find me", "find the", "find information", "find details",
            "search for", "search the", "look for", "look up",
            "give me", "give the", "provide", "provide me", "provide the",
            "show me", "show the",
            "i need", "i want", "i would like",
            "help me with", "help me understand", "help with",
            "knowledge base", "query knowledge", "search knowledge", "find in knowledge",
        ]
        
        is_question = any(message_lower.startswith(qp) or f" {qp}" in f" {message_lower}" for qp in question_patterns)
        is_retrieval = any(rp in message_lower for rp in retrieval_patterns)
        has_question_mark = message.strip().endswith("?")
        
        if is_question or is_retrieval or has_question_mark:
            logger.debug(
                f"[{FILE_NAME}] _classify_with_keywords: Matched query/question pattern (fallback)",
                is_question=is_question,
                is_retrieval=is_retrieval,
                has_question_mark=has_question_mark
            )
            return ClassifiedIntent(
                intent=IntentType.CONTEXT_ENRICH_QUERY,
                confidence=0.6,
                reasoning="Matched question/query pattern - routing to knowledge base query"
            )
        
        # Check for system help questions only
        system_help_keywords = ["what can you do", "help me understand this tool", "system capabilities", "what features"]
        if any(kw in message_lower for kw in system_help_keywords):
            logger.debug(f"[{FILE_NAME}] _classify_with_keywords: Matched system help")
            return ClassifiedIntent(
                intent=IntentType.GENERAL_QUESTION,
                confidence=0.6,
                reasoning="General system question detected"
            )
        
        # Final fallback: Default to context_enrich_query for any remaining queries
        logger.debug(f"[{FILE_NAME}] _classify_with_keywords: No specific match, defaulting to query")
        return ClassifiedIntent(
            intent=IntentType.CONTEXT_ENRICH_QUERY,
            confidence=0.4,
            reasoning="No specific intent matched - routing to knowledge base query as fallback"
        )
    
    def _parse_result(self, result: Dict[str, Any]) -> ClassifiedIntent:
        """Parse LLM response into ClassifiedIntent."""
        logger.debug(f"[{FILE_NAME}] _parse_result: ENTRY", raw_result=result)
        intent_str = result.get("intent", "unknown").lower()
        
        intent_mapping = {
            "context_enrich_upload": IntentType.CONTEXT_ENRICH_UPLOAD,
            "context_enrich_ingest": IntentType.CONTEXT_ENRICH_INGEST,
            "context_enrich_feedback": IntentType.CONTEXT_ENRICH_FEEDBACK,
            "context_enrich_query": IntentType.CONTEXT_ENRICH_QUERY,
            "context_enrich_list_documents": IntentType.CONTEXT_ENRICH_LIST_DOCUMENTS,
            "general_question": IntentType.GENERAL_QUESTION,
            "confirmation": IntentType.CONFIRMATION,
        }
        
        intent = intent_mapping.get(intent_str, IntentType.UNKNOWN)
        
        parsed = ClassifiedIntent(
            intent=intent,
            confidence=result.get("confidence", 0.5),
            entities=result.get("entities", {}),
            requires_clarification=result.get("requires_clarification", False),
            clarification_question=result.get("clarification_question"),
            reasoning=result.get("reasoning")
        )
        
        logger.debug(f"[{FILE_NAME}] _parse_result: EXIT", intent=parsed.intent.value, confidence=parsed.confidence)
        return parsed


_classifier_instance: Optional[IntentClassifier] = None


def get_classifier() -> IntentClassifier:
    """Get the global classifier instance."""
    global _classifier_instance
    if _classifier_instance is None:
        logger.info(f"[{FILE_NAME}] get_classifier: Creating new IntentClassifier instance")
        _classifier_instance = IntentClassifier()
    return _classifier_instance
